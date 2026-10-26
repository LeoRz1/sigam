from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from extensions import db
from models import (DetalleOrden, MovimientoInventario, OrdenCompra, Producto, Proveedor)
from utils import mover_stock, recibir_orden, roles_required

bp = Blueprint("scm", __name__)


# ---------------------------------------- Inventario y alertas (RF-25, 27)
@bp.route("/inventario")
@roles_required("almacenista", "comprador")
def inventario():
    productos = Producto.query.filter_by(activo=True).order_by(Producto.nombre).all()
    alertas = [p for p in productos if p.estado_stock != "ok"]
    return render_template("scm_inventario.html", productos=productos, alertas=alertas)


@bp.route("/inventario/<int:pid>/ajustar", methods=["POST"])
@roles_required("almacenista")
def inventario_ajustar(pid):
    p = db.get_or_404(Producto, pid)
    try:
        delta = int(request.form.get("cantidad", "0"))
    except ValueError:
        delta = 0
    motivo = request.form.get("motivo", "").strip() or "Ajuste manual"
    if delta == 0:
        flash("Indica una cantidad distinta de 0 (negativa para restar).", "warning")
    elif p.stock_actual + delta < 0:
        flash("El ajuste dejaría el stock en negativo.", "danger")
    else:
        mover_stock(p, delta, "ajuste", motivo[:60], current_user.id)
        db.session.commit()
        flash(f"Stock de «{p.nombre}» ajustado a {p.stock_actual}.", "success")
    return redirect(url_for("scm.inventario"))


@bp.route("/inventario/movimientos")
@roles_required("almacenista", "comprador")
def movimientos():
    movs = MovimientoInventario.query.order_by(MovimientoInventario.fecha.desc()).limit(200).all()
    return render_template("scm_movimientos.html", movs=movs)


# -------------------------------------------------- Proveedores (RF-31)
def _campos_proveedor():
    return [
        {"name": "nombre", "label": "Nombre / Razón social", "required": True},
        {"name": "nit", "label": "NIT"},
        {"name": "contacto", "label": "Persona de contacto"},
        {"name": "telefono", "label": "Teléfono"},
        {"name": "email", "label": "Correo", "type": "email"},
        {"name": "condiciones", "label": "Condiciones comerciales",
         "help": "Ej.: pago a 30 días, despacho en 3 días hábiles."},
    ]


@bp.route("/proveedores")
@roles_required("comprador")
def proveedores():
    return render_template("scm_proveedores.html", proveedores=Proveedor.query.order_by(Proveedor.nombre).all())


@bp.route("/proveedores/nuevo", methods=["GET", "POST"])
@roles_required("comprador")
def proveedor_nuevo():
    if request.method == "POST":
        if not request.form.get("nombre", "").strip():
            flash("El nombre es obligatorio.", "danger")
        else:
            db.session.add(Proveedor(**{k: request.form.get(k, "").strip() or None
                                        for k in ("nombre", "nit", "contacto", "telefono", "email", "condiciones")}))
            db.session.commit()
            flash("Proveedor registrado.", "success")
            return redirect(url_for("scm.proveedores"))
    return render_template("form_generico.html", titulo="Nuevo proveedor", campos=_campos_proveedor(),
                           valores=request.form, volver=url_for("scm.proveedores"))


@bp.route("/proveedores/<int:pid>/editar", methods=["GET", "POST"])
@roles_required("comprador")
def proveedor_editar(pid):
    p = db.get_or_404(Proveedor, pid)
    if request.method == "POST":
        for k in ("nombre", "nit", "contacto", "telefono", "email", "condiciones"):
            setattr(p, k, request.form.get(k, "").strip() or None)
        if not p.nombre:
            db.session.rollback()
            flash("El nombre es obligatorio.", "danger")
        else:
            db.session.commit()
            flash("Proveedor actualizado.", "success")
            return redirect(url_for("scm.proveedores"))
    return render_template("form_generico.html", titulo=f"Editar proveedor: {p.nombre}",
                           campos=_campos_proveedor(), valores=p, volver=url_for("scm.proveedores"))


# ----------------------------------------------- Órdenes de compra (RF-32)
@bp.route("/ordenes")
@roles_required("comprador", "almacenista")
def ordenes():
    return render_template("scm_ordenes.html",
                           ordenes=OrdenCompra.query.order_by(OrdenCompra.fecha_emision.desc()).all())


@bp.route("/ordenes/nueva", methods=["GET", "POST"])
@roles_required("comprador")
def orden_nueva():
    if request.method == "POST":
        ids = request.form.getlist("producto_id")
        cants = request.form.getlist("cantidad")
        costos = request.form.getlist("costo")
        try:
            orden = OrdenCompra(proveedor_id=int(request.form["proveedor_id"]), comprador_id=current_user.id)
            for pid, cant, costo in zip(ids, cants, costos):
                if pid and cant and int(cant) > 0:
                    orden.detalles.append(DetalleOrden(producto_id=int(pid), cantidad=int(cant),
                                                       costo_unitario=Decimal(costo or "0")))
            if not orden.detalles:
                raise ValueError
            db.session.add(orden)
            db.session.commit()
            flash(f"Orden {orden.numero} creada.", "success")
            return redirect(url_for("scm.orden_detalle", oid=orden.id))
        except (ValueError, KeyError, InvalidOperation):
            db.session.rollback()
            flash("Selecciona un proveedor y al menos un producto con cantidad válida.", "danger")
    sugerido = request.args.get("producto_id", type=int)
    return render_template("scm_orden_form.html",
                           proveedores=Proveedor.query.filter_by(activo=True).order_by(Proveedor.nombre).all(),
                           productos=Producto.query.filter_by(activo=True).order_by(Producto.nombre).all(),
                           sugerido=sugerido)


@bp.route("/ordenes/<int:oid>")
@roles_required("comprador", "almacenista")
def orden_detalle(oid):
    return render_template("scm_orden_detalle.html", o=db.get_or_404(OrdenCompra, oid))


@bp.route("/ordenes/<int:oid>/recibir", methods=["POST"])
@roles_required("almacenista", "comprador")
def orden_recibir(oid):
    o = db.get_or_404(OrdenCompra, oid)
    if o.estado != "Pendiente":
        flash("Esta orden ya no está pendiente.", "warning")
    else:
        recibir_orden(o, current_user.id)
        db.session.commit()
        flash(f"{o.numero} recibida: inventario actualizado.", "success")
    return redirect(url_for("scm.orden_detalle", oid=o.id))


@bp.route("/ordenes/<int:oid>/cancelar", methods=["POST"])
@roles_required("comprador")
def orden_cancelar(oid):
    o = db.get_or_404(OrdenCompra, oid)
    if o.estado == "Pendiente":
        o.estado = "Cancelado"
        db.session.commit()
        flash(f"{o.numero} cancelada.", "info")
    else:
        flash("Solo se pueden cancelar órdenes pendientes.", "warning")
    return redirect(url_for("scm.orden_detalle", oid=o.id))
