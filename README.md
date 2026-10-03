# Gestión

Programa de gestión para una pequeña empresa: **facturación**, **gastos** y **CRM con embudo de ventas**.
Python + FastAPI + SQLite, interfaz web sencilla (plantillas Jinja, sin build de frontend).

## Funciones

- **Facturas, rectificativas y presupuestos**: líneas con descuento, IVA por línea, retención IRPF, series y numeración
  correlativa por año (se asigna al emitir), PDF, marcar cobrada, vencidas.
  Un presupuesto se convierte en factura con un clic. Las facturas emitidas no se editan ni se borran.
- **Gastos**: proveedor, categoría, base/IVA/IRPF, pagado o pendiente, filtros y totales por categoría.
- **CRM**: tablero Kanban (Nuevo → Contactado → Propuesta → Negociación → Ganado/Perdido) con arrastrar y soltar,
  seguimiento de actividad y creación de presupuesto desde una oportunidad.
- **Panel**: ingresos, gastos, resultado, IVA repercutido/soportado por año o trimestre, pendiente de cobro y vencido.
- **Contactos**: clientes y proveedores con su historial.

## Puesta en marcha en Windows, sin Docker (la opción más fácil)

1. Instala [Python 3.12](https://www.python.org/downloads/windows/) marcando *Add python.exe to PATH*.
2. Haz doble clic en `iniciar.bat`. La primera vez instala lo necesario y te pide usuario y contraseña.
3. Se abre el navegador en http://localhost:8000. Los datos quedan en la carpeta `datos/` (haz copias de ella).

Desde el móvil, en la misma wifi, usa la dirección que muestra la ventana negra.

## Puesta en marcha con Docker (para servidor)

Necesitas [Docker](https://docs.docker.com/get-docker/) en el equipo o servidor donde vaya a correr.

```bash
cp .env.example .env      # edita .env y cambia APP_PASSWORD
./start.sh                # en Windows: start.bat
```

Abre http://localhost:8000, entra con `APP_USER` / `APP_PASSWORD` y rellena **Empresa** (datos fiscales, logo y colores).
Los datos se guardan en el volumen `gestion-data`, que sobrevive a reinicios y actualizaciones.

### Abrirlo desde cualquier dispositivo

| Situación | Cómo |
|---|---|
| Misma wifi/oficina | Abre `http://IP-DEL-EQUIPO:8000` desde el móvil o el portátil. |
| Desde internet (recomendado) | Un servidor (VPS) con Docker y un dominio apuntando a él. Pon `DOMAIN=gestion.tudominio.com` en `.env` y ejecuta `./start.sh https`. Caddy obtiene y renueva el certificado HTTPS solo. |

**Importante:** si lo expones a internet usa siempre HTTPS (el perfil `https` lo da hecho) y una contraseña larga.
Sin HTTPS la contraseña viaja sin cifrar.

En el móvil o tablet puedes **instalarlo como app** (Chrome: *Añadir a pantalla de inicio*; Safari: *Compartir → Añadir a pantalla de inicio*).

### Copias de seguridad

```bash
./backup.sh     # guarda una copia consistente de la base de datos en ./backups
```

### Sin Docker

```bash
pip install -r requirements.txt
APP_PASSWORD=tu-clave uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Marca (logo y colores)

En **Empresa**: sube tu logo (PNG o JPG) y elige color principal (botones, enlaces) y secundario (cabeceras, PDF).
Por defecto usa azul `#2b4975` y rojo `#e6354f` sobre fondo blanco. El logo aparece en la barra superior, en el icono de la app y en el PDF de facturas y presupuestos.

## Facturas rectificativas

En una factura emitida, **Rectificar** crea un borrador con serie propia (`R-2026-0001`), enlazado a la original,
con las líneas en negativo (rectificación por diferencias) y un motivo que sale en el PDF. Puedes ajustar las líneas
antes de emitirla. Las rectificativas restan automáticamente en el panel (ingresos e IVA).

## Configuración (variables de entorno)

| Variable | Descripción |
|---|---|
| `APP_USER` / `APP_PASSWORD` | Usuario y contraseña (HTTP Basic). Obligatoria con Docker Compose. |
| `DATABASE_URL` | Por defecto `sqlite:///./gestion.db` (`/data/gestion.db` en Docker). |
| `PORT` | Puerto local en Docker (8000). |
| `DOMAIN` | Dominio para el perfil `https`. |

## Pruebas

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## Fuera de alcance (por ahora)

Verifactu/TicketBAI, modelos de la AEAT, multiempresa y usuarios con permisos, facturas rectificativas,
adjuntar tickets, conciliación bancaria. Los datos están en un único fichero SQLite: haz copias de seguridad.
