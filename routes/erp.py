from decimal import Decimal, InvalidOperation

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from extensions import db
from models import PRESENTACIONES, Cliente, DetalleVenta, Producto, Venta
from utils import anular_venta, confirmar_venta, roles_required

bp = Blueprint("erp", __name__)


def _campos_producto():
    return [
        {"name": "referencia", "label": "Referencia / SKU", "required": True},
        {"name": "nombre", "label": "Nombre", "required": True},
        {"name": "viscosidad", "label": "Viscosidad (ej. 10W-30)"},
        {"name": "norma", "label": "Norma (API / ACEA)"},
        {"name": "presentacion", "label": "Presentación", "type": "select", "options": PRESENTACIONES},
        {"name": "precio", "label": "Precio sin IVA (COP)", "type": "number", "required": True},
        {"name": "stock_actual", "label": "Stock actual", "type": "number"},
        {"name": "stock_minimo", "label": "Stock mínimo", "type": "number"},
        {"name": "punto_reorden", "label": "Punto de reorden", "type": "number"},
    ]


# --------------------------------------------------- Catálogo (RF-15, 16)
@bp.route("/productos")
@roles_required("vendedor", "almacenista", "comprador")
def productos():
    q = request.args.get("q", "").strip()
    consulta = Producto.query
    if q:
        consulta = consulta.filter(Producto.nombre.ilike(f"%{q}%") | Producto.referencia.ilike(f"%{q}%")
                                   | Producto.viscosidad.ilike(f"%{q}%"))
    return render_template("erp_productos.html", productos=consulta.order_by(Producto.nombre).all(), q=q)


def _guardar_producto(p, form):
    p.referencia = form.get("referencia", "").strip()
    p.nombre = form.get("nombre", "").strip()
    p.viscosidad = form.get("viscosidad", "").strip() or None
    p.norma = form.get("norma", "").strip() or None
    p.presentacion = form.get("presentacion") if form.get("presentacion") in PRESENTACIONES else "Cuarto"
    p.precio = Decimal(form.get("precio") or "0")
    p.stock_actual = int(form.get("stock_actual") or 0)
    p.stock_minimo = int(form.get("stock_minimo") or 5)
    p.punto_reorden = int(form.get("punto_reorden") or 10)
    if not p.referencia or not p.nombre or p.precio <= 0 or p.stock_actual < 0:
        raise ValueError


@bp.route("/productos/nuevo", methods=["GET", "POST"])
@roles_required("almacenista")
def producto_nuevo():
    if request.method == "POST":
        try:
            p = Producto(referencia="", nombre="", presentacion="Cuarto", precio=0)
            _guardar_producto(p, request.form)
            if Producto.query.filter_by(referencia=p.referencia).first():
                raise ValueError("duplicada")
            db.session.add(p)
            db.session.commit()
            flash("Producto creado.", "success")
            return redirect(url_for("erp.productos"))
        except (ValueError, InvalidOperation) as e:
            db.session.rollback()
            flash("La referencia ya existe." if str(e) == "duplicada"
                  else "Revisa los datos (nombre, referencia y precio mayor a 0).", "danger")
    return render_template("form_generico.html", titulo="Nuevo producto", campos=_campos_producto(),
                           valores=request.form, volver=url_for("erp.productos"))


@bp.route("/productos/<int:pid>/editar", methods=["GET", "POST"])
@roles_required("almacenista")
def producto_editar(pid):
    p = db.get_or_404(Producto, pid)
    if request.method == "POST":
        try:
            _guardar_producto(p, request.form)
            db.session.commit()
            flash("Producto actualizado.", "success")
            return redirect(url_for("erp.productos"))
        except (ValueError, InvalidOperation):
            db.session.rollback()
            flash("Revisa los datos del producto.", "danger")
        except Exception:
            db.session.rollback()
            flash("No se pudo guardar (¿referencia repetida?).", "danger")
    return render_template("form_generico.html", titulo=f"Editar: {p.nombre}", campos=_campos_producto(),
                           valores=p, volver=url_for("erp.productos"))


@bp.route("/productos/<int:pid>/activo", methods=["POST"])
@roles_required("almacenista")
def producto_activo(pid):
    p = db.get_or_404(Producto, pid)
    p.activo = not p.activo
    db.session.commit()
    flash("Producto " + ("activado." if p.activo else "desactivado."), "info")
    return redirect(url_for("erp.productos"))


# ------------------------------------------- Tienda en línea y carrito (RF-17)
@bp.route("/tienda")
@login_required
def tienda():
    q = request.args.get("q", "").strip()
    consulta = Producto.query.filter(Producto.activo.is_(True))
    if q:
        consulta = consulta.filter(Producto.nombre.ilike(f"%{q}%") | Producto.viscosidad.ilike(f"%{q}%"))
    return render_template("erp_tienda.html", productos=consulta.order_by(Producto.nombre).all(), q=q)


def _carrito():
    return session.setdefault("carrito", {})


@bp.route("/carrito/agregar/<int:pid>", methods=["POST"])
@roles_required("cliente")
def carrito_agregar(pid):
    p = db.get_or_404(Producto, pid)
    cant = max(1, int(request.form.get("cantidad") or 1))
    carrito = _carrito()
    nueva = carrito.get(str(pid), 0) + cant
    if nueva > p.stock_actual:
        flash(f"Solo hay {p.stock_actual} unidades de «{p.nombre}».", "warning")
    else:
        carrito[str(pid)] = nueva
        session.modified = True
        flash(f"«{p.nombre}» agregado al carrito.", "success")
    return redirect(request.referrer or url_for("erp.tienda"))


@bp.route("/carrito/quitar/<int:pid>", methods=["POST"])
@roles_required("cliente")
def carrito_quitar(pid):
    _carrito().pop(str(pid), None)
    session.modified = True
    return redirect(url_for("erp.carrito"))


def _items_carrito():
    items = []
    for pid, cant in _carrito().items():
        p = db.session.get(Producto, int(pid))
        if p and p.activo:
            items.append((p, cant))
    return items


@bp.route("/carrito")
@roles_required("cliente")
def carrito():
    from flask import current_app
    items = _items_carrito()
    subtotal = sum((p.precio * c for p, c in items), Decimal("0"))
    iva = (subtotal * current_app.config["IVA"]).quantize(Decimal("0.01"))
    return render_template("erp_carrito.html", items=items, subtotal=subtotal, iva=iva, total=subtotal + iva)


@bp.route("/carrito/confirmar", methods=["POST"])
@roles_required("cliente")
def carrito_confirmar():
    """El pedido en línea queda Pendiente; el inventario se descuenta al confirmarlo el vendedor."""
    items = _items_carrito()
    if not items or not current_user.cliente:
        flash("Tu carrito está vacío.", "warning")
        return redirect(url_for("erp.tienda"))
    venta = Venta(cliente_id=current_user.cliente.id, canal="en_linea", estado="Pendiente")
    for p, cant in items:
        if cant > p.stock_actual:
            flash(f"Stock insuficiente de «{p.nombre}».", "danger")
            return redirect(url_for("erp.carrito"))
        venta.detalles.append(DetalleVenta(producto_id=p.id, cantidad=cant, precio_unitario=p.precio))
    venta.recalcular()
    db.session.add(venta)
    db.session.commit()
    session.pop("carrito", None)
    flash(f"Pedido {venta.numero} enviado. Te confirmaremos en breve.", "success")
    return redirect(url_for("erp.factura", vid=venta.id))


# ------------------------------------------------ Ventas y factura (RF-20, 21)
@bp.route("/ventas")
@roles_required("vendedor")
def ventas():
    estado = request.args.get("estado", "")
    consulta = Venta.query
    if estado:
        consulta = consulta.filter_by(estado=estado)
    return render_template("erp_ventas.html", ventas=consulta.order_by(Venta.fecha.desc()).limit(200).all(),
                           estado=estado)


@bp.route("/ventas/nueva", methods=["GET", "POST"])
@roles_required("vendedor")
def venta_nueva():
    if request.method == "POST":
        ids = request.form.getlist("producto_id")
        cants = request.form.getlist("cantidad")
        venta = Venta(vendedor_id=current_user.id, canal="mostrador", estado="Pendiente",
                      cliente_id=int(request.form["cliente_id"]) if request.form.get("cliente_id") else None)
        acumulado = {}
        for pid, cant in zip(ids, cants):
            if pid and cant and int(cant) > 0:
                acumulado[int(pid)] = acumulado.get(int(pid), 0) + int(cant)
        if not acumulado:
            flash("Agrega al menos un producto.", "warning")
        else:
            for pid, cant in acumulado.items():
                p = db.get_or_404(Producto, pid)
                venta.detalles.append(DetalleVenta(producto_id=p.id, cantidad=cant, precio_unitario=p.precio))
            venta.recalcular()
            db.session.add(venta)
            db.session.flush()
            try:
                confirmar_venta(venta, current_user.id)  # descuenta inventario (RF-29)
                db.session.commit()
                flash(f"Venta {venta.numero} registrada.", "success")
                return redirect(url_for("erp.factura", vid=venta.id))
            except ValueError as e:
                db.session.rollback()
                flash(str(e), "danger")
    return render_template("erp_venta_nueva.html",
                           productos=Producto.query.filter(Producto.activo.is_(True), Producto.stock_actual > 0)
                           .order_by(Producto.nombre).all(),
                           clientes=Cliente.query.order_by(Cliente.nombre).all())


@bp.route("/ventas/<int:vid>")
@login_required
def factura(vid):
    v = db.get_or_404(Venta, vid)
    if current_user.rol == "cliente" and (not current_user.cliente or v.cliente_id != current_user.cliente.id):
        abort(403)
    if current_user.rol not in ("admin", "vendedor", "cliente"):
        abort(403)
    return render_template("erp_factura.html", v=v)


@bp.route("/ventas/<int:vid>/confirmar", methods=["POST"])
@roles_required("vendedor")
def venta_confirmar(vid):
    v = db.get_or_404(Venta, vid)
    if v.estado != "Pendiente":
        flash("Solo se pueden confirmar pedidos pendientes.", "warning")
    else:
        try:
            v.vendedor_id = current_user.id
            confirmar_venta(v, current_user.id)
            db.session.commit()
            flash(f"Pedido {v.numero} confirmado y descontado del inventario.", "success")
        except ValueError as e:
            db.session.rollback()
            flash(str(e), "danger")
    return redirect(url_for("erp.factura", vid=v.id))


@bp.route("/ventas/<int:vid>/anular", methods=["POST"])
@roles_required("vendedor")
def venta_anular(vid):
    v = db.get_or_404(Venta, vid)
    if v.estado == "Anulada":
        flash("La venta ya estaba anulada.", "warning")
    else:
        estaba_completada = v.estado == "Completada"
        anular_venta(v, current_user.id)
        db.session.commit()
        flash(f"{v.numero} anulada" + (" y el inventario fue restituido." if estaba_completada else "."), "info")
    return redirect(url_for("erp.factura", vid=v.id))
