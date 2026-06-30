# SPF API

Backend del Sistema de Consultas del Servicio Penitenciario Federal (SPF), desarrollado como proyecto personal para gestión interna de internos, ciudadanos vinculados y gestión de alertas.

> El frontend del sistema (Streamlit) consume esta API. Este repositorio contiene únicamente el backend.

 Stack

- FastAPI — framework del backend
- Supabase / PostgreSQL** — base de datos
- JWT** — autenticación
- RBAC (Role-Based Access Control) — permisos por rol (admin / consultor)
- ReportLab — generación de reportes en PDF
- Render — deploy del backend

Funcionalidades principales

- Gestión de fichas de internos*(alojamiento, causa, situación legal, salidas extramuros, sanciones)
- Gestión de ciudadanos vinculados (visitas, transferencias de dinero)
- Autenticación JWT con roles diferenciados (admin / consultor)
- Auditoría automática: registro de cada consulta realizada al sistema, con usuario, fecha y ficha consultada
- Gestión de usuarios con soft-delete (baja lógica, no se elimina el registro)
- Alertas de inteligencia financiera:
  - Detección de pitufeo / smurfing (3 o más internos distintos recibiendo dinero del mismo ciudadano en un período de 30 días)
  - Alertas por tope de depósitos
  - Detección de múltiples visitantes
- Generación de reportes en PDF con el detalle completo de cada ficha

#Estructura del proyecto

```
spf-api/
L> main.py              # Endpoints y lógica principal
L> config.py             # Configuración de conexión a Supabase
L> reporte_en_pdf.py      # Generación de pdf (ReportLab)
L> requirements.txt       # Dependencias del proyecto
L> render.yaml             # Configuración de deploy en Render
L> .gitignore
L> .env.example            # Plantilla de variables de entorno 
```

Endpoints principales

> Completar/ajustar esta tabla según el listado real en Swagger UI (`/docs`).

| Método | Endpoint | Descripción | Requiere rol |
|--------|----------|-------------|--------------|
| POST   | `/login` | Autenticación, devuelve JWT | — |
| GET    | `/internos/{lpu}` | Ficha completa de un interno | consultor / admin |
| GET    | `/ciudadanos/{id}` | Ficha de un ciudadano vinculado | consultor / admin |
| GET    | `/alertas` | Listado de alertas financieras activas | admin |
| GET    | `/auditoria` | Historial de consultas realizadas | admin |
| POST   | `/usuarios` | Alta de usuario | admin |
| DELETE | `/usuarios/{id}` | Baja lógica de usuario (soft-delete) | admin |
| GET    | `/reporte/{lpu}` | Genera y descarga el reporte en PDF | consultor / admin |

Variables de entorno

Crear un archivo `.env` en la raíz con:

```
SUPABASE_URL=
SUPABASE_KEY=
JWT_SECRET=
```


Cómo correr el proyecto localmente

1. Clonar el repositorio:
   ```
   git clone https://github.com/ailinpersincola-svg/spf-api.git
   cd spf-api
   ```
2. Crear y activar un entorno virtual:
   ```
   python -m venv venv
   venv\Scripts\activate   # Windows
   ```
3. Instalar dependencias:
   ```
   pip install -r requirements.txt
   ```
4. Configurar el archivo `.env` (ver sección anterior).
5. Levantar el servidor:
   ```
   uvicorn main:app --reload
   ```
6. Acceder a la documentación interactiva (Swagger UI) en:
   ```
   http://localhost:8000/docs
   ```

Notas de seguridad / arquitectura

- Row Level Security (RLS) de Supabase está deshabilitado; el control de acceso se maneja a nivel de aplicación mediante JWT + RBAC.
- Cada consulta a fichas de internos o ciudadanos queda registrada automáticamente en la tabla de auditoría.


Ailín Persíncola, estudiante de tecnicatura superior en programación, UTN
