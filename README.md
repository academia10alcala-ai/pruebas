# Gestión

Programa de gestión para una pequeña empresa: **facturación**, **gastos** y **CRM con embudo de ventas**.
Python + FastAPI + SQLite, interfaz web sencilla (plantillas Jinja, sin build de frontend).

## Funciones

- **Facturas y presupuestos**: líneas con descuento, IVA por línea, retención IRPF, series y numeración
  correlativa por año (se asigna al emitir), PDF, marcar cobrada, vencidas.
  Un presupuesto se convierte en factura con un clic. Las facturas emitidas no se editan ni se borran.
- **Gastos**: proveedor, categoría, base/IVA/IRPF, pagado o pendiente, filtros y totales por categoría.
- **CRM**: tablero Kanban (Nuevo → Contactado → Propuesta → Negociación → Ganado/Perdido) con arrastrar y soltar,
  seguimiento de actividad y creación de presupuesto desde una oportunidad.
- **Panel**: ingresos, gastos, resultado, IVA repercutido/soportado por año o trimestre, pendiente de cobro y vencido.
- **Contactos**: clientes y proveedores con su historial.

## Puesta en marcha

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Abre http://localhost:8000 y rellena los datos de tu empresa en **Empresa** (aparecen en el PDF).

## Configuración (variables de entorno)

| Variable | Descripción |
|---|---|
| `DATABASE_URL` | Por defecto `sqlite:///./gestion.db` |
| `APP_USER` / `APP_PASSWORD` | Si se definen ambas, se exige usuario y contraseña (HTTP Basic). **Actívalas si lo expones en internet.** |

## Pruebas

```bash
python -m pytest
```

## Fuera de alcance (por ahora)

Verifactu/TicketBAI, modelos de la AEAT, multiempresa y usuarios con permisos, facturas rectificativas,
adjuntar tickets, conciliación bancaria. Los datos están en un único fichero SQLite: haz copias de seguridad.
