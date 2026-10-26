from datetime import date, datetime

from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from extensions import db
from models import Cliente, OrdenCompra, Producto, Vehiculo, Venta

bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def index():
    if current_user.rol == "cliente":
        return redirect(url_for("erp.tienda"))

    inicio_mes = datetime.combine(date.today().replace(day=1), datetime.min.time())
    ventas_mes = db.session.query(func.coalesce(func.sum(Venta.total), 0)).filter(
        Venta.estado == "Completada", Venta.fecha >= inicio_mes).scalar()

    bajos = (Producto.query.filter(Producto.activo.is_(True),
                                   Producto.stock_actual <= Producto.punto_reorden)
             .order_by(Producto.stock_actual).all())
    alertas = [v for v in Vehiculo.query.all() if v.estado_alerta in ("vencido", "proximo")]
    alertas.sort(key=lambda v: v.proximo_cambio)

    datos = {
        "clientes": Cliente.query.count(),
        "productos": Producto.query.filter_by(activo=True).count(),
        "ventas_mes": ventas_mes,
        "pedidos_pendientes": Venta.query.filter_by(estado="Pendiente").count(),
        "ordenes_pendientes": OrdenCompra.query.filter_by(estado="Pendiente").count(),
        "bajos": bajos,
        "alertas": alertas[:8],
        "ultimas_ventas": Venta.query.order_by(Venta.fecha.desc()).limit(6).all(),
    }
    return render_template("index.html", **datos)
