# LubriGest · Sistema integrado CRM + ERP + SCM (aceites y lubricantes)

Aplicación web en **Flask + Flask-SQLAlchemy + MySQL (XAMPP) + Bootstrap 5**.

## Puesta en marcha (Windows + XAMPP)

1. Abre **XAMPP** e inicia **MySQL** (no hace falta crear la base de datos a mano; la app la crea).
2. En una terminal, dentro de la carpeta `sistema_aceites/`:

```bash
python -m venv venv
venv\Scripts\activate          # Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
python seed.py                 # crea tablas y datos de ejemplo
python app.py                  # http://127.0.0.1:5000
```

Conexión por defecto: `mysql+pymysql://root:@localhost:3306/sistema_aceites`.
Si tu MySQL tiene contraseña u otro puerto, define la variable de entorno antes de arrancar:

```bash
set DATABASE_URL=mysql+pymysql://root:TU_CLAVE@localhost:3306/sistema_aceites?charset=utf8mb4
```

Para probar rápido con SQLite: `set DATABASE_URL=sqlite:///database.db`.

## Usuarios de ejemplo (contraseña `Demo1234`)

| Rol | Correo | Qué puede hacer |
|---|---|---|
| Administrador | admin@aceites.com | Todo, incluida la gestión de usuarios y roles |
| Vendedor | vendedor@aceites.com | CRM, recordatorios, ventas de mostrador, confirmar pedidos en línea |
| Almacenista | almacen@aceites.com | Catálogo, inventario, ajustes, recepción de mercancía |
| Comprador | comprador@aceites.com | Proveedores, órdenes de compra, vista de inventario |
| Cliente | cliente@aceites.com | Tienda, carrito, pedidos propios, sus vehículos |

## Cobertura de requerimientos

| RF / RNF | Dónde |
|---|---|
| RF-01 registro e inicio de sesión | `routes/auth.py` (`/login`, `/registro`) |
| RF-02 / RF-03 roles y permisos | `utils.roles_required`, menú por rol en `layout.html`, `/usuarios` |
| RF-06 clientes (particular, taller, flota) | `routes/crm.py` |
| RF-09 vehículo y aceite sugerido | `utils.recomendar_aceite` + `routes/crm.py` |
| RF-11 recordatorios de cambio | `/recordatorios`, dashboard, estado en cada vehículo |
| RF-15 a RF-17 catálogo y carrito en línea | `routes/erp.py` (`/productos`, `/tienda`, `/carrito`) |
| RF-20 / RF-21 ventas y factura con IVA | `/ventas/nueva`, `/ventas/<id>` (IVA 19 %) |
| RF-25 / RF-29 existencias y descuento automático | `utils.confirmar_venta`, `MovimientoInventario` |
| RF-27 stock mínimo y punto de reorden | `/inventario` y dashboard |
| RF-31 / RF-32 proveedores y órdenes de compra | `routes/scm.py` |
| RNF-04 bcrypt | `models.User.set_password` |
| RNF-15 responsive | Bootstrap 5, tema oscuro/claro |
| RNF-18 arquitectura modular | un *blueprint* por módulo en `routes/` |

## Decisiones que conviene revisar

- **IVA 19 %** (`config.py`). Los precios del catálogo se guardan **sin IVA**; el IVA se suma en carrito y factura.
- **Pedidos en línea** quedan *Pendientes*: el inventario se descuenta cuando el vendedor los confirma. Las ventas de mostrador se confirman al registrarse.
- **Sugerencia de aceite**: reglas simples por tipo de motor y año en `utils.recomendar_aceite`. Son de ejemplo; ajústalas con el manual del fabricante o una tabla por marca/modelo.
- **Intervalo de recordatorio**: 180 días por defecto, editable por vehículo.
- La «factura» es un comprobante básico, **no** una factura electrónica DIAN.

## Mejoras sugeridas

Protección CSRF (Flask-WTF), migraciones (Flask-Migrate), paginación, reportes en PDF/Excel, envío de recordatorios por correo o WhatsApp y pruebas automatizadas.

## Estructura

```
sistema_aceites/
├── app.py            # fábrica de la app y registro de módulos
├── config.py  extensions.py  models.py  utils.py  seed.py
├── routes/           # auth, main, crm, erp, scm
├── templates/        # Jinja2 (layout + una vista por pantalla)
└── static/           # css, js (POS y órdenes de compra), img
```
