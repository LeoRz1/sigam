"""Carga datos de ejemplo. Uso:  python seed.py

Crea (si no existen) un usuario por rol, productos, proveedores, clientes y vehículos.
Es seguro ejecutarlo varias veces: no duplica los datos.
"""
from datetime import date, timedelta
from decimal import Decimal

from app import app
from extensions import db
from models import Cliente, Producto, Proveedor, User, Vehiculo
from utils import recomendar_aceite

USUARIOS = [
    ("Administrador", "admin@aceites.com", "admin"),
    ("Valentina Vendedora", "vendedor@aceites.com", "vendedor"),
    ("Alberto Almacén", "almacen@aceites.com", "almacenista"),
    ("Camila Compras", "comprador@aceites.com", "comprador"),
    ("Cliente Demo", "cliente@aceites.com", "cliente"),
]
PASSWORD_DEMO = "Demo1234"

# referencia, nombre, viscosidad, norma, presentación, precio sin IVA, stock, mínimo, reorden
PRODUCTOS = [
    ("MOT-5W30-Q", "Aceite Sintético 5W-30", "5W-30", "API SP", "Cuarto", 38000, 40, 10, 20),
    ("MOT-5W30-G", "Aceite Sintético 5W-30", "5W-30", "API SP", "Galón", 135000, 4, 5, 10),
    ("MOT-10W30-Q", "Aceite Semisintético 10W-30", "10W-30", "API SN", "Cuarto", 29000, 60, 10, 20),
    ("MOT-10W30-G", "Aceite Semisintético 10W-30", "10W-30", "API SN", "Galón", 105000, 15, 5, 10),
    ("MOT-15W40-G", "Aceite Diésel 15W-40", "15W-40", "API CK-4", "Galón", 98000, 22, 5, 10),
    ("MOT-15W40-C", "Aceite Diésel 15W-40", "15W-40", "API CK-4", "Caneca", 420000, 2, 2, 4),
    ("MOT-20W50-Q", "Aceite Mineral 20W-50", "20W-50", "API SL", "Cuarto", 22000, 35, 10, 20),
    ("MOT-10W40-Q", "Aceite Moto 4T 10W-40", "10W-40", "API SN / JASO MA2", "Cuarto", 32000, 0, 8, 15),
    ("MOT-0W20-Q", "Aceite Híbridos 0W-20", "0W-20", "API SP", "Cuarto", 52000, 18, 5, 10),
]

PROVEEDORES = [
    ("Lubricantes del Caribe S.A.S.", "900123456-1", "Mariana Pérez", "3001112233",
     "ventas@lubricaribe.example", "Pago a 30 días. Despacho en 3 días hábiles."),
    ("Distribuidora Andina de Aceites", "800765432-9", "Jorge Ríos", "3109998877",
     "pedidos@andinaaceites.example", "Pago de contado con 3% de descuento."),
]


def run():
    with app.app_context():
        for nombre, email, rol in USUARIOS:
            if not User.query.filter_by(email=email).first():
                u = User(nombre=nombre, email=email, rol=rol)
                u.set_password(PASSWORD_DEMO)
                db.session.add(u)
        db.session.flush()

        for ref, nombre, visc, norma, pres, precio, stock, minimo, reorden in PRODUCTOS:
            if not Producto.query.filter_by(referencia=ref).first():
                db.session.add(Producto(referencia=ref, nombre=nombre, viscosidad=visc, norma=norma,
                                        presentacion=pres, precio=Decimal(precio), stock_actual=stock,
                                        stock_minimo=minimo, punto_reorden=reorden))

        for nombre, nit, contacto, tel, email, cond in PROVEEDORES:
            if not Proveedor.query.filter_by(nombre=nombre).first():
                db.session.add(Proveedor(nombre=nombre, nit=nit, contacto=contacto, telefono=tel,
                                         email=email, condiciones=cond))

        demo = User.query.filter_by(email="cliente@aceites.com").first()
        if demo and not demo.cliente:
            db.session.add(Cliente(nombre=demo.nombre, email=demo.email, user_id=demo.id,
                                   telefono="3015550101", ciudad="Santa Marta", tipo="Particular"))

        if not Cliente.query.filter_by(nombre="Taller El Pistón").first():
            taller = Cliente(nombre="Taller El Pistón", tipo="Taller", telefono="3205550202", ciudad="Riohacha")
            db.session.add(taller)
            db.session.flush()
            hoy = date.today()
            for marca, modelo, anio, motor, dias in [
                ("Chevrolet", "Spark", 2018, "Gasolina", 200),   # cambio vencido
                ("Toyota", "Hilux", 2012, "Diésel", 170),        # próximo a vencer
                ("Yamaha", "FZ 150", 2021, "Moto 4T", 30),       # al día
            ]:
                db.session.add(Vehiculo(cliente_id=taller.id, marca=marca, modelo=modelo, anio=anio,
                                        tipo_motor=motor, aceite_recomendado=recomendar_aceite(anio, motor),
                                        fecha_ultimo_cambio=hoy - timedelta(days=dias), intervalo_dias=180))
        db.session.commit()
        print("Datos de ejemplo cargados. Contraseña de todos los usuarios demo:", PASSWORD_DEMO)
        for _, email, rol in USUARIOS:
            print(f"  {rol:12s} {email}")


if __name__ == "__main__":
    run()
