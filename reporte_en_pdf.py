
from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)
from reportlab.lib.enums import TA_LEFT


# Colores institucionales (mismos que la app)
AZUL_OSCURO  = colors.HexColor("#16335c")
AZUL_MEDIO   = colors.HexColor("#1f4a82")
GRIS_BORDE   = colors.HexColor("#c3cad6")
GRIS_TEXTO   = colors.HexColor("#5a6a85")
GRIS_FILA    = colors.HexColor("#f4f5f7")
ROJO_SUAVE = colors.HexColor("#b65454")


def _estilos():
    base = getSampleStyleSheet()
    estilos = {}

    estilos["titulo"] = ParagraphStyle(
        "titulo", parent=base["Title"],
        fontName="Helvetica-Bold", fontSize=16, textColor=colors.white,
        spaceAfter=2, alignment=TA_LEFT,
    )
    estilos["subtitulo"] = ParagraphStyle(
        "subtitulo", parent=base["Normal"],
        fontName="Helvetica", fontSize=8, textColor=colors.white,
        alignment=TA_LEFT,
    )
    estilos["titular"] = ParagraphStyle(
        "titular", parent=base["Normal"],
        fontName="Helvetica-Bold", fontSize=13, textColor=AZUL_OSCURO,
        spaceBefore=6, spaceAfter=2,
    )
    estilos["titular_id"] = ParagraphStyle(
        "titular_id", parent=base["Normal"],
        fontName="Helvetica", fontSize=9, textColor=GRIS_TEXTO,
        spaceAfter=4,
    )
    estilos["seccion"] = ParagraphStyle(
        "seccion", parent=base["Normal"],
        fontName="Helvetica-Bold", fontSize=10, textColor=colors.white,
        spaceBefore=8, spaceAfter=4, leftIndent=4,
    )
    estilos["dato"] = ParagraphStyle(
        "dato", parent=base["Normal"],
        fontName="Helvetica", fontSize=9, textColor=colors.black,
        spaceAfter=1,
    )
    estilos["celda"] = ParagraphStyle(
        "celda", parent=base["Normal"],
        fontName="Helvetica", fontSize=8, textColor=colors.black,
    )
    estilos["celda_head"] = ParagraphStyle(
        "celda_head", parent=base["Normal"],
        fontName="Helvetica-Bold", fontSize=8, textColor=colors.white,
    )
    estilos["sin_datos"] = ParagraphStyle(
        "sin_datos", parent=base["Normal"],
        fontName="Helvetica-Oblique", fontSize=8, textColor=GRIS_TEXTO,
        spaceAfter=4,
    )
    return estilos


def _barra_seccion(texto, estilos):
    p = Paragraph(texto, estilos["seccion"])
    fondo = ROJO_SUAVE if "alerta" in texto.lower() else AZUL_MEDIO
    t = Table([[p]], colWidths=[17 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), fondo),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def _tabla_datos(filas, estilos):
    if not filas:
        return Paragraph("Sin registros", estilos["sin_datos"])

    columnas = list(filas[0].keys())
    # Encabezado
    data = [[Paragraph(col, estilos["celda_head"]) for col in columnas]]
    # Filas
    for fila in filas:
        data.append([Paragraph(str(fila.get(col, "")), estilos["celda"]) for col in columnas])

    ancho_total = 17 * cm
    ancho_col = ancho_total / len(columnas)
    t = Table(data, colWidths=[ancho_col] * len(columnas), repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL_OSCURO),
        ("GRID", (0, 0), (-1, -1), 0.4, GRIS_BORDE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS_FILA]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t

    
def generar_pdf(titulo, subtitulo, datos_generales, secciones, foto_url=None):
    estilos = _estilos()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        title=titulo,
    )

    elementos = []

    # ---- ENCABEZADO (barra azul oscuro con foto) 
    from reportlab.platypus import Image as RLImage
    import urllib.request


    texto_cab = [
        [Paragraph(titulo, estilos["titulo"])],
        [Paragraph("Servicio Penitenciario Federal — Documento de uso interno", estilos["subtitulo"])],
    ]
    foto_obj = None
    if foto_url:
        try:
            req = urllib.request.Request(foto_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as r:
                img_bytes = r.read()
            foto_obj = RLImage(BytesIO(img_bytes), width=2.2*cm, height=2.8*cm)
        except Exception:
            foto_obj = Paragraph("", estilos["subtitulo"])
            

    tabla_texto = Table(texto_cab, colWidths=[14 * cm])
    tabla_texto.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (0, 0), 0),
        ("BOTTOMPADDING", (0, 1), (0, 1), 0),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    cab = Table(
        [[tabla_texto, foto_obj]],
        colWidths=[14 * cm, 3 * cm]
    )
    cab.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), AZUL_OSCURO),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
    ]))
    elementos.append(cab)

    # ---- TITULAR ----
    elementos.append(Paragraph(subtitulo, estilos["titular"]))
    elementos.append(Spacer(1, 6))

    # ---- DATOS GENERALES (dos columnas) ----
    elementos.append(_barra_seccion("Datos generales", estilos))
    elementos.append(Spacer(1, 4))

    # Armar pares en dos columnas
    filas_dg = []
    for etiqueta, valor in datos_generales:
        filas_dg.append(Paragraph(f"<b>{etiqueta}:</b> {valor}", estilos["dato"]))

    # Distribuir en 2 columnas
    mitad = (len(filas_dg) + 1) // 2
    col_izq = filas_dg[:mitad]
    col_der = filas_dg[mitad:]
    while len(col_der) < len(col_izq):
        col_der.append(Paragraph("", estilos["dato"]))

    tabla_dg = Table(
        list(zip(col_izq, col_der)),
        colWidths=[8.5 * cm, 8.5 * cm]
    )
    tabla_dg.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elementos.append(tabla_dg)
    elementos.append(Spacer(1, 4))

    # ---- SECCIONES CRUZADAS ----
    for titulo_sec, filas in secciones:
        elementos.append(_barra_seccion(titulo_sec, estilos))
        elementos.append(Spacer(1, 4))
        elementos.append(_tabla_datos(filas, estilos))
        elementos.append(Spacer(1, 6))

    # ---- PIE ----
    elementos.append(Spacer(1, 10))
    pie = Paragraph(
        f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')} — Sistema de Consultas SPF",
        estilos["sin_datos"]
    )
    elementos.append(pie)

    doc.build(elementos)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf