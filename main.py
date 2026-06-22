# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import supabase
from fastapi import HTTPException
from pydantic import BaseModel
from datetime import datetime, timedelta
from fastapi.responses import Response
from reporte_en_pdf import generar_pdf

app = FastAPI(
    title="SPF API",
    description="API del Sistema de Consultas del Servicio Penitenciario Federal",
    version="0.1.0",
)

# ── CORS: permite que FlutterFlow llame a esta API ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class LoginRequest(BaseModel):
    nombre_usuario: str
    password: str


# ── Endpoint : login ──
@app.post("/login")
def log_pagina(datos: LoginRequest):
    try:
        resp = supabase.table("usuarios") \
            .select("*") \
            .eq("nombre_usuario", datos.nombre_usuario.strip()) \
            .eq("password", datos.password) \
            .eq("activo", True) \
            .execute()

        if not resp.data:
            raise HTTPException(
                status_code=401,
                detail="Usuario o contraseña incorrectos"
            )

        usuario = resp.data[0]

        supabase.table("usuarios").update(
            {"ultimo_acceso": "now()"}
        ).eq("id_usuario", usuario["id_usuario"]).execute()

        return {
            "ok": True,
            "nombre_usuario": usuario["nombre_usuario"],
            "nombre_completo": usuario.get("nombre_completo", ""),
            "rol": usuario["rol"],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# end point : busqueda del interno LPU O DNI
@app.get("/interno/{campo}/{valor}")
def buscar_interno(campo: str, valor: str):
    # Validar que el campo sea LPU o DNI
    if campo not in ("lpu", "dni"):
        raise HTTPException(
            status_code=400,
            detail="Seleccionar por LPU O DNI'"
        )
    try:
        # ── Datos principales del interno ──
        resultado = supabase.table("internos") \
            .select("*") \
            .eq(campo, valor.strip()) \
            .execute()

        if not resultado.data:
            raise HTTPException(
                status_code=404,
                detail="No se encontró ningún interno con ese LPU/DNI"
            )

        interno = resultado.data[0]
        lpu = str(interno.get("lpu"))

        # ── Nombre de la unidad penal ──
        unidad_nombre = "—"
        if interno.get("id_unidad"):
            u = supabase.table("unidades_penales") \
                .select("nombre") \
                .eq("id_unidad", interno["id_unidad"]) \
                .execute()
            if u.data:
                unidad_nombre = u.data[0]["nombre"]

        # ── Alertas activas ──
        alertas = supabase.table("alertas_internos") \
            .select("*") \
            .eq("lpu", lpu) \
            .eq("activa", True) \
            .execute()

        # ── Sanciones ──
        sanciones = supabase.table("sanciones_internos") \
            .select("*") \
            .eq("lpu", lpu) \
            .execute()

        # ── Visitantes autorizados ──
        visitantes_auth = supabase.table("ciudadano_visita_interno") \
            .select("*") \
            .eq("lpu", lpu) \
            .execute()

        # ── Visitas recibidas ──
        visitas = supabase.table("visitas_registradas") \
            .select("*") \
            .eq("lpu", lpu) \
            .execute()

        # ── Visitas intercarcelarias ──
        visitas_inter_recibidas = supabase.table("visitas_intercarcelarias") \
            .select("*") \
            .eq("lpu_receptor", lpu) \
            .execute()
        visitas_inter_enviadas = supabase.table("visitas_intercarcelarias") \
            .select("*") \
            .eq("lpu_visitante", lpu) \
            .execute()

        # ── Videollamadas ──
        videollamadas = supabase.table("videollamadas") \
            .select("*") \
            .eq("lpu", lpu) \
            .execute()

        # ── Autorizados a depósito ──
        autorizados_deposito = supabase.table("ciudadano_deposito_interno") \
            .select("*") \
            .eq("lpu", lpu) \
            .execute()

        # ── Depósitos recibidos ──
        depositos = supabase.table("depositos_efectuados") \
            .select("*") \
            .eq("lpu", lpu) \
            .execute()

        # ── Transferencias recibidas (de familiares) ──
        transf_recibidas = supabase.table("transferencias") \
            .select("*") \
            .eq("lpu", lpu) \
            .eq("sentido_transferencia", "ciudadano_a_interno") \
            .execute()

        # ── Transferencias enviadas (a familiares) ──
        transf_enviadas = supabase.table("transferencias") \
            .select("*") \
            .eq("lpu", lpu) \
            .eq("sentido_transferencia", "interno_a_ciudadano") \
            .execute()

        # ── Salidas extramuros ──
        salidas = supabase.table("salidas_extramuros") \
            .select("*") \
            .eq("lpu", lpu) \
            .order("fecha_salida", desc=True) \
            .execute()

        # ── Compañeros de pabellón ──
        compas_query = supabase.table("internos").select("*")
        if interno.get("id_unidad"):
            compas_query = compas_query.eq("id_unidad", interno["id_unidad"])
        if interno.get("modulo"):
            compas_query = compas_query.eq("modulo", interno["modulo"])
        if interno.get("celda"):
            compas_query = compas_query.eq("celda", interno["celda"])
        compas_query = compas_query.neq("lpu", lpu)
        compas = compas_query.execute()

        # ── Sanciones recientes del pabellón (últimos 15 días) ──
        fecha_limite = (datetime.now() - timedelta(days=15)).strftime("%Y-%m-%d")
        lpus_compas = [str(c.get("lpu")) for c in (compas.data or [])]

        sanc_pabellon = []
        if lpus_compas:
            sanc_pabellon = supabase.table("sanciones_internos") \
                .select("*") \
                .in_("lpu", lpus_compas) \
                .gte("fecha_sancion", fecha_limite) \
                .execute()
            sanc_pabellon = sanc_pabellon.data or []

        # respuesta completa ──
        return {
            "ok": True,
            "interno": {
                **interno,
                "unidad_nombre": unidad_nombre,
            },
            "alertas": alertas.data or [],
            "sanciones": sanciones.data or [],
            "visitantes_autorizados": visitantes_auth.data or [],
            "visitas_recibidas": visitas.data or [],
            "visitas_intercarcelarias": {
                "recibidas": visitas_inter_recibidas.data or [],
                "enviadas": visitas_inter_enviadas.data or [],
            },
            "videollamadas": videollamadas.data or [],
            "autorizados_deposito": autorizados_deposito.data or [],
            "depositos_recibidos": depositos.data or [],
            "transferencias_recibidas": transf_recibidas.data or [],
            "transferencias_enviadas": transf_enviadas.data or [],
            "salidas_extramuros": salidas.data or [],
            "companieros_pabellon": compas.data or [],
            "sanciones_pabellon_recientes": sanc_pabellon,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
#endoint busqueda del ciudadano por DNI
@app.get("/ciudadano/{dni}")
def buscar_ciudadano(dni: str):
    try:
        # ── Datos principales del ciudadano ──
        resultado = supabase.table("ciudadanos") \
            .select("*") \
            .eq("dni", dni.strip()) \
            .execute()

        if not resultado.data:
            raise HTTPException(
                status_code=404,
                detail="No se encontró ningún ciudadano con ese DNI"
            )

        c = resultado.data[0]
        id_ciudadano = c.get("id_ciudadano")

        # ── Alertas activas ──
        alertas = supabase.table("alertas_ciudadanos") \
            .select("*") \
            .eq("id_ciudadano", id_ciudadano) \
            .eq("activa", True) \
            .execute()

        # ── Sanciones de visita ──
        sanciones = supabase.table("sanciones_visitas") \
            .select("*") \
            .eq("id_ciudadano", id_ciudadano) \
            .execute()

        # ── Internos que puede visitar ──
        internos_habilitados = supabase.table("ciudadano_visita_interno") \
            .select("*") \
            .eq("id_ciudadano", id_ciudadano) \
            .execute()

        # ── Visitas realizadas ──
        visitas = supabase.table("visitas_registradas") \
            .select("*") \
            .eq("id_ciudadano", id_ciudadano) \
            .execute()

        # ── Videollamadas recibidas ──
        videollamadas = supabase.table("videollamadas") \
            .select("*") \
            .eq("id_ciudadano", id_ciudadano) \
            .execute()

        # ── Internos a los que puede hacer depósito ──
        deposito_habilitados = supabase.table("ciudadano_deposito_interno") \
            .select("*") \
            .eq("id_ciudadano", id_ciudadano) \
            .execute()

        # ── Depósitos realizados ──
        depositos = supabase.table("depositos_efectuados") \
            .select("*") \
            .eq("id_ciudadano", id_ciudadano) \
            .execute()

        # ── Dinero enviado a internos ──
        transf_enviadas = supabase.table("transferencias") \
            .select("*") \
            .eq("id_ciudadano", id_ciudadano) \
            .eq("sentido_transferencia", "ciudadano_a_interno") \
            .execute()

        # ── Dinero recibido de internos ──
        transf_recibidas = supabase.table("transferencias") \
            .select("*") \
            .eq("id_ciudadano", id_ciudadano) \
            .eq("sentido_transferencia", "interno_a_ciudadano") \
            .execute()

        # ── Calcular si tiene sanción vigente ──
        from datetime import datetime, timedelta
        hoy = datetime.now().date()
        sancion_vigente = None

        for s in (sanciones.data or []):
            if not s.get("resuelto"):
                f_sanc = s.get("fecha_sancion")
                dias = s.get("dias_suspension") or 0
                if f_sanc:
                    try:
                        f_inicio = datetime.strptime(f_sanc, "%Y-%m-%d").date()
                        f_fin = f_inicio + timedelta(days=int(dias))
                        if f_fin > hoy:
                            sancion_vigente = {
                                "vigente": True,
                                "hasta": f_fin.strftime("%Y-%m-%d"),
                                "motivo": s.get("motivo", "—"),
                            }
                    except Exception:
                        pass

        return {
            "ok": True,
            "ciudadano": c,
            "alertas": alertas.data or [],
            "sancion_vigente": sancion_vigente,
            "sanciones_visita": sanciones.data or [],
            "internos_habilitados_visita": internos_habilitados.data or [],
            "visitas_realizadas": visitas.data or [],
            "videollamadas": videollamadas.data or [],
            "internos_habilitados_deposito": deposito_habilitados.data or [],
            "depositos_realizados": depositos.data or [],
            "transferencias_enviadas": transf_enviadas.data or [],
            "transferencias_recibidas": transf_recibidas.data or [],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

#endpoint generar el pdf del interno 
@app.get("/interno/pdf/{lpu}/")
def pdf_interno(lpu: str):
    try:
        # ── Datos principales ──
        resultado = supabase.table("internos") \
            .select("*") \
            .eq("lpu", lpu.strip()) \
            .execute()

        if not resultado.data:
            raise HTTPException(
                status_code=404,
                detail="No se encontró ningún interno con ese LPU"
            )

        interno = resultado.data[0]
        lpu_str = str(interno.get("lpu"))

        # ── Nombre de unidad ──
        unidad_nombre = "—"
        if interno.get("id_unidad"):
            u = supabase.table("unidades_penales") \
                .select("nombre") \
                .eq("id_unidad", interno["id_unidad"]) \
                .execute()
            if u.data:
                unidad_nombre = u.data[0]["nombre"]

        # ── Secciones para el PDF (igual que en Streamlit) ──
        secciones_pdf = []

        # ── Helpers para buscar nombres ──
        def nombre_ciudadano(id_ciud):
            if not id_ciud:
                return "—", "—"
            r = supabase.table("ciudadanos").select("nombre, apellido, dni").eq("id_ciudadano", id_ciud).execute()
            if r.data:
                cc = r.data[0]
                return f"{cc.get('nombre','')} {cc.get('apellido','')}".strip(), str(cc.get("dni", "—"))
            return "Desconocido", "—"

        def nombre_otro_interno(lpu_otro):
            if not lpu_otro:
                return "—"
            r = supabase.table("internos").select("nombre, apellido").eq("lpu", str(lpu_otro)).execute()
            if r.data:
                i = r.data[0]
                return f"{i.get('nombre','')} {i.get('apellido','')}".strip()
            return "Desconocido"

        # ── Secciones para el PDF ──
        secciones_pdf = []

        # Alertas
        alertas = supabase.table("alertas_internos").select("*").eq("lpu", lpu_str).eq("activa", True).execute()
        if alertas.data:
            secciones_pdf.append(("Alertas activas", [
                {"Tipo": (a.get("tipo_alerta") or "").upper(),
                 "Descripción": a.get("descripcion") or "—"}
                for a in alertas.data
            ]))

        # Sanciones
        sanciones = supabase.table("sanciones_internos").select("*").eq("lpu", lpu_str).execute()
        secciones_pdf.append(("Sanciones disciplinarias", [
            {"Fecha": s.get("fecha_sancion", "—"),
             "Motivo": s.get("motivo", "—"),
             "Tipo": (s.get("tipo_sancion") or "—").capitalize(),
             "Días": s.get("dias_sancion", "—"),
             "Resuelto": "Sí" if s.get("resuelto") else "No"}
            for s in (sanciones.data or [])
        ]))

        # Visitantes autorizados
        visitantes_auth = supabase.table("ciudadano_visita_interno").select("*").eq("lpu", lpu_str).execute()
        filas_vis = []
        for v in (visitantes_auth.data or []):
            nom, dni = nombre_ciudadano(v.get("id_ciudadano"))
            filas_vis.append({
                "Persona": nom, "DNI": dni,
                "Número de tarjeta": str(v.get("id_ciudadano", "—")),
                "Vínculo": v.get("vinculo", "—"),
                "Habilitado": "Sí" if v.get("habilitado") else "No"
            })
        secciones_pdf.append(("Visitantes autorizados", filas_vis))

        # Visitas recibidas
        visitas = supabase.table("visitas_registradas").select("*").eq("lpu", lpu_str).execute()
        filas_vr = []
        for v in (visitas.data or []):
            nom, dni = nombre_ciudadano(v.get("id_ciudadano"))
            filas_vr.append({"Visitante": nom, "DNI": dni,
                             "Fecha": v.get("fecha_visita", "—"), "Estado": v.get("estado", "—")})
        secciones_pdf.append(("Visitas recibidas", filas_vr))

        # Visitas intercarcelarias
        vi_rec = supabase.table("visitas_intercarcelarias").select("*").eq("lpu_receptor", lpu_str).execute()
        vi_env = supabase.table("visitas_intercarcelarias").select("*").eq("lpu_visitante", lpu_str).execute()
        filas_inter = []
        for v in (vi_rec.data or []):
            filas_inter.append({"Rol": "Recibió visita de",
                                "Otro interno": nombre_otro_interno(v.get("lpu_visitante")),
                                "LPU": str(v.get("lpu_visitante", "—")),
                                "Fecha": v.get("fecha_visita", "—"),
                                "Vínculo": v.get("vinculo", "—")})
        for v in (vi_env.data or []):
            filas_inter.append({"Rol": "Visitó a",
                                "Otro interno": nombre_otro_interno(v.get("lpu_receptor")),
                                "LPU": str(v.get("lpu_receptor", "—")),
                                "Fecha": v.get("fecha_visita", "—"),
                                "Vínculo": v.get("vinculo", "—")})
        secciones_pdf.append(("Visitas intercarcelarias (entre internos)", filas_inter))

        # Videollamadas
        videollamadas = supabase.table("videollamadas").select("*").eq("lpu", lpu_str).execute()
        filas_vid = []
        for v in (videollamadas.data or []):
            nom, dni = nombre_ciudadano(v.get("id_ciudadano"))
            filas_vid.append({"Ciudadano receptor": nom, "DNI": dni,
                              "Fecha": v.get("fecha", "—"), "Estado": v.get("estado", "—")})
        secciones_pdf.append(("Videollamadas realizadas", filas_vid))

        # Autorizados a depósito
        aut_dep = supabase.table("ciudadano_deposito_interno").select("*").eq("lpu", lpu_str).execute()
        filas_ad = []
        for d in (aut_dep.data or []):
            nom, dni = nombre_ciudadano(d.get("id_ciudadano"))
            filas_ad.append({"Persona": nom, "DNI": dni,
                             "Habilitado": "Sí" if d.get("habilitado") else "No"})
        secciones_pdf.append(("Autorizados a efectuar depósito", filas_ad))

        # Depósitos recibidos
        depositos = supabase.table("depositos_efectuados").select("*").eq("lpu", lpu_str).execute()
        filas_dep = []
        for d in (depositos.data or []):
            nom, dni = nombre_ciudadano(d.get("id_ciudadano"))
            filas_dep.append({"Entregó": nom, "DNI": dni,
                              "Fecha": d.get("fecha", "—"),
                              "Tipo": d.get("tipo_de_deposito", "—"),
                              "Estado": d.get("estado", "—")})
        secciones_pdf.append(("Depósitos recibidos", filas_dep))

        # Transferencias recibidas
        transf_rec = supabase.table("transferencias").select("*").eq("lpu", lpu_str).eq("sentido_transferencia", "ciudadano_a_interno").execute()
        filas_tr = []
        for t in (transf_rec.data or []):
            nom, dni = nombre_ciudadano(t.get("id_ciudadano"))
            filas_tr.append({"Remitente": nom, "DNI": dni,
                             "Fecha": t.get("fecha", "—"),
                             "Monto": f"${float(t.get('monto', 0) or 0):,.2f}",
                             "Medio": t.get("medio_pago", "—")})
        secciones_pdf.append(("Transferencias de dinero recibidas (de familiares)", filas_tr))

        # Transferencias enviadas
        transf_env = supabase.table("transferencias").select("*").eq("lpu", lpu_str).eq("sentido_transferencia", "interno_a_ciudadano").execute()
        filas_te = []
        for t in (transf_env.data or []):
            nom, dni = nombre_ciudadano(t.get("id_ciudadano"))
            filas_te.append({"Destinatario": nom, "DNI": dni,
                             "Fecha": t.get("fecha", "—"),
                             "Monto": f"${float(t.get('monto', 0) or 0):,.2f}",
                             "Medio": t.get("medio_pago", "—")})
        secciones_pdf.append(("Transferencias de dinero enviadas (a familiares)", filas_te))

        # Salidas extramuros
        salidas = supabase.table("salidas_extramuros").select("*").eq("lpu", lpu_str).order("fecha_salida", desc=True).execute()
        filas_sal = []
        for s in (salidas.data or []):
            filas_sal.append({
                "Fecha salida": s.get("fecha_salida", "—"),
                "Regreso est.": s.get("fecha_regreso_estimada", "—") or "—",
                "Regreso real": s.get("fecha_regreso_real", "—") or "—",
                "Motivo": (s.get("motivo") or "—").capitalize(),
                "Destino": s.get("destino", "—").title(),
                "Acompañante": (s.get("acompanado_por") or "—").capitalize(),
                "Estado": (s.get("estado") or "—").upper(),
                "Autorizada por": s.get("autorizada_por", "—").capitalize(),
            })
        secciones_pdf.append(("Salidas extramuros", filas_sal))

        # Compañeros de pabellón
        compas_query = supabase.table("internos").select("*")
        if interno.get("id_unidad"):
            compas_query = compas_query.eq("id_unidad", interno["id_unidad"])
        if interno.get("modulo"):
            compas_query = compas_query.eq("modulo", interno["modulo"])
        if interno.get("celda"):
            compas_query = compas_query.eq("celda", interno["celda"])
        compas = compas_query.neq("lpu", lpu_str).execute()
        filas_comp = []
        for c in (compas.data or []):
            filas_comp.append({
                "Interno": f"{(c.get('nombre') or '').title()} {(c.get('apellido') or '').title()}".strip(),
                "LPU": str(c.get("lpu", "—")),
                "Causa": c.get("causa", "—"),
                "Situación legal": c.get("situacion_legal", "—"),
            })
        secciones_pdf.append(("Compañeros de pabellón (misma unidad, módulo y celda)", filas_comp))

        # Sanciones recientes del pabellón
        from datetime import datetime, timedelta
        fecha_limite_pab = (datetime.now() - timedelta(days=15)).strftime("%Y-%m-%d")
        lpus_compas = [str(c.get("lpu")) for c in (compas.data or [])]
        filas_sanc_pab = []
        if lpus_compas:
            sanc_pab = supabase.table("sanciones_internos").select("*") \
                .in_("lpu", lpus_compas).gte("fecha_sancion", fecha_limite_pab).execute()
            for s in (sanc_pab.data or []):
                filas_sanc_pab.append({
                    "Compañero": nombre_otro_interno(s.get("lpu")),
                    "LPU": str(s.get("lpu", "—")),
                    "Fecha": s.get("fecha_sancion", "—"),
                    "Motivo": s.get("motivo", "—"),
                    "Tipo": (s.get("tipo_sancion") or "—").capitalize(),
                    "Días": s.get("dias_sancion", "—"),
                    "Resuelto": "Sí" if s.get("resuelto") else "No",
                })
        secciones_pdf.append(("Sanciones recientes en el pabellón (últimos 15 días)", filas_sanc_pab))

        # ── Datos generales para el encabezado del PDF ──
        from datetime import datetime
        edad = "—"
        fnac = interno.get("fecha_nacimiento")
        if fnac:
            try:
                nacimiento = datetime.strptime(fnac, "%Y-%m-%d")
                hoy = datetime.now()
                edad = hoy.year - nacimiento.year - (
                    (hoy.month, hoy.day) < (nacimiento.month, nacimiento.day)
                )
            except Exception:
                edad = "—"

        datos_generales = [
            ("Fecha de nacimiento", interno.get("fecha_nacimiento", "—")),
            ("Edad", edad),
            ("Nacionalidad", interno.get("nacionalidad", "—").capitalize()),
            ("Género", interno.get("genero", "—").capitalize()),
            ("Unidad", unidad_nombre.upper()),
            ("Módulo", interno.get("modulo", "—").upper()),
            ("Celda", interno.get("celda", "—").upper()),
            ("Causa", interno.get("causa", "—").capitalize()),
            ("Fecha de ingreso", interno.get("fecha_ingreso", "—")),
            ("Situación legal", interno.get("situacion_legal", "—")),
        ]

        subtitulo = f"{interno.get('nombre','').capitalize()} {interno.get('apellido','').capitalize()} — LPU {lpu_str}"

        #  Generar el PDF 
        pdf_bytes = generar_pdf(
            "Reporte de Interno",
            subtitulo,
            datos_generales,
            secciones_pdf,
            foto_url=interno.get("foto_url"),
        )

        # ── Devolver el PDF como archivo descargable ──
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=reporte_interno_{lpu_str}.pdf"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
#endpoint de generar pdf CIUDADANO
@app.get("/ciudadano/pdf/{dni}/")
def pdf_ciudadano(dni: str):
    try:
        # ── Datos principales ──
        resultado = supabase.table("ciudadanos") \
            .select("*") \
            .eq("dni", dni.strip()) \
            .execute()

        if not resultado.data:
            raise HTTPException(
                status_code=404,
                detail="No se encontró ningún ciudadano con ese DNI"
            )   
        c = resultado.data[0]
        id_ciudadano = c.get("id_ciudadano")

        # ── Helper para buscar nombre de interno ──
        def nombre_interno(lpu):
            if not lpu:
                return "—"
            r = supabase.table("internos").select("nombre, apellido") \
                .eq("lpu", str(lpu)).execute()
            if r.data:
                i = r.data[0]
                return f"{i.get('nombre','').title()} {i.get('apellido','').title()}".strip()
            return "Desconocido"

        # ── Secciones del PDF ──
        secciones_pdf = []

        # Alertas activas
        alertas = supabase.table("alertas_ciudadanos").select("*") \
            .eq("id_ciudadano", id_ciudadano).eq("activa", True).execute()
        if alertas.data:
            secciones_pdf.append(("Alertas activas", [
                {"Tipo": (a.get("tipo_alerta") or "").upper(),
                "Descripción": a.get("descripcion") or "—"}
                for a in alertas.data
            ]))

        # Sanciones de visita
        sanciones = supabase.table("sanciones_visitas").select("*") \
            .eq("id_ciudadano", id_ciudadano).execute()
        secciones_pdf.append(("Sanciones de visita recibidas", [
            {"Fecha": s.get("fecha_sancion", "—"),
            "Motivo": s.get("motivo", "—"),
            "Días suspensión": s.get("dias_suspension", "—"),
            "Resuelto": "Sí" if s.get("resuelto") else "No",
            "Aplicada al visitar a": nombre_interno(s.get("lpu"))}
            for s in (sanciones.data or [])
        ]))

        # Internos habilitados a visitar
        internos_hab = supabase.table("ciudadano_visita_interno").select("*") \
            .eq("id_ciudadano", id_ciudadano).execute()
        secciones_pdf.append(("Internos que está habilitado a visitar", [
            {"Interno": nombre_interno(v.get("lpu")),
            "LPU": str(v.get("lpu", "—")),
            "Vínculo": v.get("vinculo", "—"),
            "Habilitado": "Sí" if v.get("habilitado") else "No"}
            for v in (internos_hab.data or [])
        ]))

        # Visitas realizadas
        visitas = supabase.table("visitas_registradas").select("*") \
            .eq("id_ciudadano", id_ciudadano).execute()
        secciones_pdf.append(("Visitas realizadas", [
            {"Interno": nombre_interno(v.get("lpu")),
            "LPU": str(v.get("lpu", "—")),
            "Fecha": v.get("fecha_visita", "—"),
            "Estado": v.get("estado", "—")}
            for v in (visitas.data or [])
        ]))

        # Videollamadas recibidas
        videollamadas = supabase.table("videollamadas").select("*") \
            .eq("id_ciudadano", id_ciudadano).execute()
        secciones_pdf.append(("Videollamadas recibidas (del interno)", [
            {"Interno": nombre_interno(v.get("lpu")),
            "LPU": str(v.get("lpu", "—")),
            "Fecha": v.get("fecha", "—"),
            "Estado": v.get("estado", "—")}
            for v in (videollamadas.data or [])
        ]))

        # Internos a los que puede hacer depósito
        dep_hab = supabase.table("ciudadano_deposito_interno").select("*") \
            .eq("id_ciudadano", id_ciudadano).execute()
        secciones_pdf.append(("Internos a los que puede hacer depósito", [
            {"Interno": nombre_interno(d.get("lpu")),
            "LPU": str(d.get("lpu", "—")),
            "Habilitado": "Sí" if d.get("habilitado") else "No"}
            for d in (dep_hab.data or [])
        ]))

        # Depósitos realizados
        depositos = supabase.table("depositos_efectuados").select("*") \
            .eq("id_ciudadano", id_ciudadano).execute()
        secciones_pdf.append(("Depósitos realizados", [
            {"Interno": nombre_interno(d.get("lpu")),
            "LPU": str(d.get("lpu", "—")),
            "Fecha": d.get("fecha", "—"),
            "Tipo": d.get("tipo_de_deposito", "—"),
            "Estado": d.get("estado", "—")}
            for d in (depositos.data or [])
        ]))

        # Dinero enviado a internos
        transf_env = supabase.table("transferencias").select("*") \
            .eq("id_ciudadano", id_ciudadano) \
            .eq("sentido_transferencia", "ciudadano_a_interno").execute()
        secciones_pdf.append(("Dinero enviado a internos", [
            {"Interno": nombre_interno(t.get("lpu")),
            "LPU": str(t.get("lpu", "—")),
            "Fecha": t.get("fecha", "—"),
            "Monto": f"${float(t.get('monto', 0) or 0):,.2f}",
            "Medio": t.get("medio_pago", "—")}
            for t in (transf_env.data or [])
        ]))

        # Dinero recibido de internos
        transf_rec = supabase.table("transferencias").select("*") \
            .eq("id_ciudadano", id_ciudadano) \
            .eq("sentido_transferencia", "interno_a_ciudadano").execute()
        secciones_pdf.append(("Dinero recibido de internos", [
            {"Interno": nombre_interno(t.get("lpu")),
            "LPU": str(t.get("lpu", "—")),
            "Fecha": t.get("fecha", "—"),
            "Monto": f"${float(t.get('monto', 0) or 0):,.2f}",
            "Medio": t.get("medio_pago", "—")}
            for t in (transf_rec.data or [])
        ]))

        # ── Datos generales para el encabezado ──
        from datetime import datetime
        edad = "—"
        fnac = c.get("fecha_nacimiento")
        if fnac:
            try:
                nacimiento = datetime.strptime(fnac, "%Y-%m-%d")
                hoy = datetime.now()
                edad = hoy.year - nacimiento.year - (
                    (hoy.month, hoy.day) < (nacimiento.month, nacimiento.day)
                )
            except Exception:
                edad = "—"

        datos_generales = [
            ("Fecha de nacimiento", c.get("fecha_nacimiento", "—")),
            ("Edad", edad),
            ("Nacionalidad", c.get("nacionalidad", "—").capitalize()),
            ("Género", c.get("genero", "—").capitalize()),
            ("Teléfono", c.get("telefono", "—")),
            ("Domicilio", f"{c.get('domicilio','—').title()}, {c.get('localidad','').title()}, {c.get('provincia','').title()}"),
            ("¿Ex detenido?", "SÍ" if c.get("es_ex_detenido") else "NO"),
            ("¿Actualmente detenido?", "SÍ" if c.get("esta_detenido") else "NO"),
            ("LPU actual", str(c.get("lpu_actual")) if c.get("lpu_actual") else "—"),
            ("Observaciones", c.get("observaciones", "—").capitalize() or "—"),
        ]

        subtitulo = f"{c.get('nombre','').title()} {c.get('apellido','').title()} — DNI {dni}"

        # ── Generar el PDF ──
        pdf_bytes = generar_pdf(
            "Reporte de Ciudadano",
            subtitulo,
            datos_generales,
            secciones_pdf,
            foto_url=c.get("foto_url"),
        )

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=reporte_ciudadano_{dni}.pdf"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

#endpoint auditoria 
class ConsultaAuditoria(BaseModel):
    nombre_usuario: str
    rol: str
    tipo_consulta: str
    valor_buscado: str
    encontrado: bool

class FiltrosAuditoria(BaseModel):
    usuario: str = ""
    tipo: str = "todos"
    limite: int = 100

@app.post("/auditoria/registrar")
def registrar_auditoria(datos: ConsultaAuditoria):
    try:
        supabase.table("auditoria_consultas").insert({
            "nombre_usuario": datos.nombre_usuario,
            "rol":            datos.rol,
            "tipo_consulta":  datos.tipo_consulta,
            "valor_buscado":  datos.valor_buscado,
            "encontrado":     datos.encontrado,
            "direccion_ip":   "0.0.0.0",
        }).execute()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Endpoint: listar registros de auditoría (solo admin) ──
@app.post("/auditoria/listar")
def listar_auditoria(filtros: FiltrosAuditoria):
    try:
        query = supabase.table("auditoria_consultas") \
            .select("*") \
            .order("fecha_hora", desc=True) \
            .limit(filtros.limite)

        if filtros.usuario:
            query = query.eq("nombre_usuario", filtros.usuario)
        if filtros.tipo != "todos":
            query = query.eq("tipo_consulta", filtros.tipo)

        resp = query.execute()
        data = resp.data or []

        total = len(data)
        encontrados = sum(1 for r in data if r.get("encontrado"))

        return {
            "ok": True,
            "total": total,
            "encontrados": encontrados,
            "no_encontrados": total - encontrados,
            "registros": data,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# ── Modelos ──
class NuevoUsuario(BaseModel):
    nombre_usuario: str
    password: str
    nombre_completo: str = ""
    rol: str = "consultor"

class CambioRol(BaseModel):
    id_usuario: int
    nuevo_rol: str


# ── Endpoint: listar usuarios (solo admin) ──
@app.get("/usuarios")
def listar_usuarios():
    try:
        resp = supabase.table("usuarios") \
            .select("id_usuario, nombre_usuario, nombre_completo, rol, activo, ultimo_acceso") \
            .order("id_usuario") \
            .execute()
        return {"ok": True, "usuarios": resp.data or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Endpoint: crear usuario nuevo ──
@app.post("/usuarios/crear")
def crear_usuario(datos: NuevoUsuario):
    try:
        supabase.table("usuarios").insert({
            "nombre_usuario":  datos.nombre_usuario.strip(),
            "password":        datos.password,
            "nombre_completo": datos.nombre_completo.strip() or None,
            "rol":             datos.rol,
            "activo":          True,
        }).execute()
        return {"ok": True, "mensaje": f"Usuario '{datos.nombre_usuario}' creado correctamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Endpoint: dar de baja usuario ──
@app.patch("/usuarios/{id_usuario}/baja")
def dar_baja_usuario(id_usuario: int):
    try:
        # Verificar que no sea el último admin activo
        admins = supabase.table("usuarios") \
            .select("id_usuario") \
            .eq("rol", "admin") \
            .eq("activo", True) \
            .execute()

        usuario = supabase.table("usuarios") \
            .select("rol") \
            .eq("id_usuario", id_usuario) \
            .execute()

        if usuario.data and usuario.data[0]["rol"] == "admin" and len(admins.data) <= 1:
            raise HTTPException(
                status_code=400,
                detail="No se puede dar de baja al último admin activo"
            )

        supabase.table("usuarios").update(
            {"activo": False}
        ).eq("id_usuario", id_usuario).execute()

        return {"ok": True, "mensaje": "Usuario dado de baja correctamente"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Endpoint: reactivar usuario ──
@app.patch("/usuarios/{id_usuario}/reactivar")
def reactivar_usuario(id_usuario: int):
    try:
        supabase.table("usuarios").update(
            {"activo": True}
        ).eq("id_usuario", id_usuario).execute()
        return {"ok": True, "mensaje": "Usuario reactivado correctamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Endpoint: cambiar rol ──
@app.patch("/usuarios/rol")
def cambiar_rol(datos: CambioRol):
    try:
        if datos.nuevo_rol not in ("admin", "consultor"):
            raise HTTPException(
                status_code=400,
                detail="Rol inválido. Debe ser 'admin' o 'consultor'"
            )
        supabase.table("usuarios").update(
            {"rol": datos.nuevo_rol}
        ).eq("id_usuario", datos.id_usuario).execute()
        return {"ok": True, "mensaje": f"Rol actualizado a '{datos.nuevo_rol}'"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))