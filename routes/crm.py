from datetime import date, datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from models import TIPOS_CLIENTE, TIPOS_MOTOR, Cliente, Producto, Vehiculo, Venta
from utils import recomendar_aceite, roles_required, viscosidad_de

bp = Blueprint("crm", __name__)


def _puede_gestionar(cliente):
    """Admin y vendedor gestionan todo; el cliente solo lo suyo."""
    if current_user.rol in ("admin", "vendedor"):
        return True
    return current_user.rol == "cliente" and current_user.cliente and current_user.cliente.id == cliente.id


def _campos_cliente():
    return [
        {"name": "nombre", "label": "Nombre / Razón social", "required": True},
        {"name": "tipo", "label": "Tipo de cliente", "type": "select", "options": TIPOS_CLIENTE},
        {"name": "telefono", "label": "Teléfono"},
        {"name": "email", "label": "Correo", "type": "email"},
        {"name": "ciudad", "label": "Ciudad"},
    ]


def _campos_vehiculo():
    return [
        {"name": "placa", "label": "Placa"},
        {"name": "marca", "label": "Marca", "required": True},
        {"name": "modelo", "label": "Modelo", "required": True},
        {"name": "anio", "label": "Año", "type": "number", "required": True},
        {"name": "tipo_motor", "label": "Tipo de motor", "type": "select", "options": TIPOS_MOTOR},
        {"name": "fecha_ultimo_cambio", "label": "Fecha del último cambio de aceite", "type": "date"},
        {"name": "km_ultimo_cambio", "label": "Kilometraje del último cambio", "type": "number"},
        {"name": "intervalo_dias", "label": "Recordar cada (días)", "type": "number",
         "help": "Por defecto 180 días."},
    ]


# --------------------------------------------------------------- Clientes
@bp.route("/clientes")
@roles_required("vendedor")
def clientes():
    q = request.args.get("q", "").strip()
    consulta = Cliente.query
    if q:
        consulta = consulta.filter(Cliente.nombre.ilike(f"%{q}%") | Cliente.telefono.ilike(f"%{q}%"))
    return render_template("crm_clientes.html", clientes=consulta.order_by(Cliente.nombre).all(), q=q)


@bp.route("/clientes/nuevo", methods=["GET", "POST"])
@roles_required("vendedor")
def cliente_nuevo():
    if request.method == "POST":
        if not request.form.get("nombre", "").strip():
            flash("El nombre es obligatorio.", "danger")
        else:
            c = Cliente(**{k: request.form.get(k, "").strip() or None
                           for k in ("nombre", "tipo", "telefono", "email", "ciudad")})
            c.tipo = c.tipo or "Particular"
            db.session.add(c)
            db.session.commit()
            flash("Cliente registrado.", "success")
            return redirect(url_for("crm.cliente_detalle", cid=c.id))
    return render_template("form_generico.html", titulo="Nuevo cliente", campos=_campos_cliente(),
                           valores=request.form, volver=url_for("crm.clientes"))


@bp.route("/clientes/<int:cid>/editar", methods=["GET", "POST"])
@roles_required("vendedor")
def cliente_editar(cid):
    c = db.get_or_404(Cliente, cid)
    if request.method == "POST":
        for k in ("nombre", "tipo", "telefono", "email", "ciudad"):
            setattr(c, k, request.form.get(k, "").strip() or None)
        c.tipo = c.tipo or "Particular"
        db.session.commit()
        flash("Cliente actualizado.", "success")
        return redirect(url_for("crm.cliente_detalle", cid=c.id))
    return render_template("form_generico.html", titulo=f"Editar cliente: {c.nombre}",
                           campos=_campos_cliente(), valores=c, volver=url_for("crm.cliente_detalle", cid=c.id))


@bp.route("/clientes/<int:cid>")
@roles_required("vendedor")
def cliente_detalle(cid):
    c = db.get_or_404(Cliente, cid)
    ventas = Venta.query.filter_by(cliente_id=c.id).order_by(Venta.fecha.desc()).limit(10).all()
    return render_template("crm_cliente_detalle.html", c=c, ventas=ventas, sugerencias=_sugerencias(c))


def _sugerencias(cliente):
    """Productos disponibles que coinciden con la viscosidad recomendada de cada vehículo."""
    res = {}
    for v in cliente.vehiculos:
        visc = viscosidad_de(v.aceite_recomendado)
        if visc:
            res[v.id] = (Producto.query.filter(Producto.activo.is_(True), Producto.viscosidad == visc,
                                               Producto.stock_actual > 0).limit(4).all())
    return res


# -------------------------------------------------------------- Vehículos
def _leer_vehiculo(v, form):
    v.placa = form.get("placa", "").strip().upper() or None
    v.marca = form.get("marca", "").strip()
    v.modelo = form.get("modelo", "").strip()
    v.anio = int(form.get("anio") or 0)
    v.tipo_motor = form.get("tipo_motor") if form.get("tipo_motor") in TIPOS_MOTOR else "Gasolina"
    v.fecha_ultimo_cambio = (datetime.strptime(form["fecha_ultimo_cambio"], "%Y-%m-%d").date()
                             if form.get("fecha_ultimo_cambio") else None)
    v.km_ultimo_cambio = int(form["km_ultimo_cambio"]) if form.get("km_ultimo_cambio") else None
    v.intervalo_dias = int(form.get("intervalo_dias") or 180)
    # RF-09: sugerir el aceite ideal según año y tipo de motor
    v.aceite_recomendado = recomendar_aceite(v.anio, v.tipo_motor)


def _volver_cliente(c):
    if current_user.rol == "cliente":
        return url_for("crm.mi_cuenta")
    return url_for("crm.cliente_detalle", cid=c.id)


@bp.route("/clientes/<int:cid>/vehiculos/nuevo", methods=["GET", "POST"])
@login_required
def vehiculo_nuevo(cid):
    c = db.get_or_404(Cliente, cid)
    if not _puede_gestionar(c):
        abort(403)
    if request.method == "POST":
        try:
            v = Vehiculo(cliente_id=c.id, marca="", modelo="", anio=0, tipo_motor="Gasolina")
            _leer_vehiculo(v, request.form)
            if not v.marca or not v.modelo or v.anio < 1950:
                raise ValueError
            db.session.add(v)
            db.session.commit()
            flash(f"Vehículo registrado. Aceite sugerido: {v.aceite_recomendado}", "success")
            return redirect(_volver_cliente(c))
        except ValueError:
            db.session.rollback()
            flash("Revisa los datos del vehículo (marca, modelo y año válido).", "danger")
    return render_template("form_generico.html", titulo=f"Nuevo vehículo de {c.nombre}",
                           campos=_campos_vehiculo(), valores=request.form, volver=_volver_cliente(c))


@bp.route("/vehiculos/<int:vid>/editar", methods=["GET", "POST"])
@login_required
def vehiculo_editar(vid):
    v = db.get_or_404(Vehiculo, vid)
    if not _puede_gestionar(v.cliente):
        abort(403)
    if request.method == "POST":
        try:
            _leer_vehiculo(v, request.form)
            if not v.marca or not v.modelo or v.anio < 1950:
                raise ValueError
            db.session.commit()
            flash("Vehículo actualizado.", "success")
            return redirect(_volver_cliente(v.cliente))
        except ValueError:
            db.session.rollback()
            flash("Revisa los datos del vehículo.", "danger")
    return render_template("form_generico.html", titulo=f"Editar vehículo {v.descripcion}",
                           campos=_campos_vehiculo(), valores=v, volver=_volver_cliente(v.cliente))


@bp.route("/vehiculos/<int:vid>/cambio", methods=["POST"])
@roles_required("vendedor")
def vehiculo_cambio(vid):
    """Registra que hoy se hizo el cambio de aceite (reinicia el recordatorio)."""
    v = db.get_or_404(Vehiculo, vid)
    v.fecha_ultimo_cambio = date.today()
    if request.form.get("km"):
        v.km_ultimo_cambio = int(request.form["km"])
    db.session.commit()
    flash(f"Cambio registrado. Próximo recordatorio: {v.proximo_cambio:%d/%m/%Y}.", "success")
    return redirect(request.referrer or url_for("crm.recordatorios"))


# ---------------------------------------------- Recordatorios (RF-11)
@bp.route("/recordatorios")
@roles_required("vendedor")
def recordatorios():
    lista = [v for v in Vehiculo.query.all() if v.estado_alerta in ("vencido", "proximo")]
    lista.sort(key=lambda v: v.proximo_cambio)
    return render_template("crm_recordatorios.html", vehiculos=lista)


# ------------------------------------------------- Portal del cliente
@bp.route("/mi-cuenta")
@roles_required("cliente")
def mi_cuenta():
    c = current_user.cliente
    if not c:
        abort(404)
    pedidos = Venta.query.filter_by(cliente_id=c.id).order_by(Venta.fecha.desc()).all()
    return render_template("mi_cuenta.html", c=c, pedidos=pedidos, sugerencias=_sugerencias(c))
