from datetime import datetime
from functools import wraps

from flask import abort, redirect, url_for
from flask_login import current_user
from sqlalchemy.engine import make_url

from extensions import db
from models import MovimientoInventario


# ------------------------------------------------------------ Permisos (RF-03)
def roles_required(*roles):
    """Permite el acceso a los roles indicados. El administrador siempre puede entrar."""
    def decorador(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))
            if current_user.rol != "admin" and current_user.rol not in roles:
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorador


# ----------------------------------------------------- Base de datos (MySQL)
def crear_base_si_no_existe(uri):
    """En MySQL/XAMPP crea la base de datos si todavía no existe."""
    url = make_url(uri)
    if not url.drivername.startswith("mysql"):
        return
    import pymysql
    conn = pymysql.connect(
        host=url.host or "localhost", port=url.port or 3306,
        user=url.username or "root", password=url.password or "",
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{url.database}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
    finally:
        conn.close()


# ------------------------------------------ Sugerencia de aceite (RF-09)
# Reglas de ejemplo para el MVP. Para producción conviene validar con el
# manual del fabricante o con una tabla de referencias por marca/modelo.
def recomendar_aceite(anio, tipo_motor):
    anio = int(anio or 0)
    if tipo_motor == "Moto 4T":
        return "10W-40 · API SN · JASO MA2"
    if tipo_motor == "Híbrido":
        return "0W-20 · API SP · ILSAC GF-6A"
    if tipo_motor == "Diésel":
        return "15W-40 · API CK-4" if anio < 2015 else "5W-30 · API CK-4 · ACEA C3"
    # Gasolina
    if anio < 2000:
        return "20W-50 · API SL"
    if anio < 2015:
        return "10W-30 · API SN"
    return "5W-30 · API SP"


def viscosidad_de(recomendado):
    return recomendado.split("·")[0].strip() if recomendado else None


# --------------------------------------------- Inventario (RF-25, RF-29)
def mover_stock(producto, cantidad, tipo, referencia=None, usuario_id=None):
    """Aplica un movimiento (cantidad positiva = entrada, negativa = salida)."""
    producto.stock_actual += cantidad
    db.session.add(MovimientoInventario(
        producto_id=producto.id, cantidad=cantidad, tipo=tipo,
        referencia=referencia, usuario_id=usuario_id,
    ))


def confirmar_venta(venta, usuario_id=None):
    """Descuenta inventario y marca la venta como Completada."""
    for d in venta.detalles:
        if d.producto.stock_actual < d.cantidad:
            raise ValueError(
                f"Stock insuficiente de «{d.producto.nombre}» "
                f"(disponible: {d.producto.stock_actual}, solicitado: {d.cantidad})."
            )
    for d in venta.detalles:
        mover_stock(d.producto, -d.cantidad, "venta", venta.numero, usuario_id)
    venta.estado = "Completada"


def anular_venta(venta, usuario_id=None):
    """Anula la venta; si estaba completada devuelve el inventario."""
    if venta.estado == "Completada":
        for d in venta.detalles:
            mover_stock(d.producto, d.cantidad, "anulacion", venta.numero, usuario_id)
    venta.estado = "Anulada"


def recibir_orden(orden, usuario_id=None):
    """Registra la recepción de mercancía y aumenta el inventario."""
    for d in orden.detalles:
        mover_stock(d.producto, d.cantidad, "compra", orden.numero, usuario_id)
    orden.estado = "Recibido"
    orden.fecha_recepcion = datetime.now()
