from datetime import date, datetime, timedelta
from decimal import Decimal

from flask import current_app
from flask_login import UserMixin

from extensions import bcrypt, db, login_manager

ROLES = ["admin", "vendedor", "almacenista", "comprador", "cliente"]
TIPOS_CLIENTE = ["Particular", "Taller", "Flota"]
TIPOS_MOTOR = ["Gasolina", "Diésel", "Híbrido", "Moto 4T"]
PRESENTACIONES = ["Cuarto", "Galón", "Caneca"]


# ---------------------------------------------------------------- Usuarios
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    rol = db.Column(db.String(20), nullable=False, default="cliente")
    activo = db.Column(db.Boolean, default=True, nullable=False)

    cliente = db.relationship("Cliente", back_populates="user", uselist=False)

    @property
    def is_active(self):
        return self.activo

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# --------------------------------------------------------------------- CRM
class Cliente(db.Model):
    __tablename__ = "clientes"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    telefono = db.Column(db.String(30))
    email = db.Column(db.String(120))
    tipo = db.Column(db.String(20), nullable=False, default="Particular")
    ciudad = db.Column(db.String(80))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=True)

    user = db.relationship("User", back_populates="cliente")
    vehiculos = db.relationship("Vehiculo", back_populates="cliente", cascade="all, delete-orphan")
    ventas = db.relationship("Venta", back_populates="cliente")


class Vehiculo(db.Model):
    __tablename__ = "vehiculos"
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False)
    placa = db.Column(db.String(10))
    marca = db.Column(db.String(50), nullable=False)
    modelo = db.Column(db.String(50), nullable=False)
    anio = db.Column(db.Integer, nullable=False)
    tipo_motor = db.Column(db.String(20), nullable=False)
    aceite_recomendado = db.Column(db.String(120))
    fecha_ultimo_cambio = db.Column(db.Date)
    km_ultimo_cambio = db.Column(db.Integer)
    intervalo_dias = db.Column(db.Integer, default=180, nullable=False)

    cliente = db.relationship("Cliente", back_populates="vehiculos")

    @property
    def proximo_cambio(self):
        if not self.fecha_ultimo_cambio:
            return None
        return self.fecha_ultimo_cambio + timedelta(days=self.intervalo_dias)

    @property
    def estado_alerta(self):
        """'sin_datos' | 'vencido' | 'proximo' | 'ok'"""
        prox = self.proximo_cambio
        if prox is None:
            return "sin_datos"
        hoy = date.today()
        if prox < hoy:
            return "vencido"
        if prox <= hoy + timedelta(days=current_app.config["DIAS_ALERTA_CAMBIO"]):
            return "proximo"
        return "ok"

    @property
    def descripcion(self):
        return f"{self.marca} {self.modelo} {self.anio}" + (f" · {self.placa}" if self.placa else "")


# --------------------------------------------------------------------- ERP
class Producto(db.Model):
    __tablename__ = "productos"
    id = db.Column(db.Integer, primary_key=True)
    referencia = db.Column(db.String(40), unique=True, nullable=False)
    nombre = db.Column(db.String(120), nullable=False)
    viscosidad = db.Column(db.String(20))           # Ej: 10W-30
    norma = db.Column(db.String(40))                # Ej: API SN / ACEA C3
    presentacion = db.Column(db.String(20), nullable=False)
    precio = db.Column(db.Numeric(12, 2), nullable=False)   # sin IVA
    stock_actual = db.Column(db.Integer, nullable=False, default=0)
    stock_minimo = db.Column(db.Integer, nullable=False, default=5)
    punto_reorden = db.Column(db.Integer, nullable=False, default=10)
    activo = db.Column(db.Boolean, default=True, nullable=False)

    @property
    def estado_stock(self):
        if self.stock_actual <= 0:
            return "agotado"
        if self.stock_actual <= self.stock_minimo:
            return "minimo"
        if self.stock_actual <= self.punto_reorden:
            return "reorden"
        return "ok"


class Venta(db.Model):
    __tablename__ = "ventas"
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=True)
    vendedor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    fecha = db.Column(db.DateTime, default=datetime.now, nullable=False)
    canal = db.Column(db.String(20), default="mostrador", nullable=False)   # mostrador | en_linea
    estado = db.Column(db.String(20), default="Completada", nullable=False)  # Pendiente | Completada | Anulada
    subtotal = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    iva = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    total = db.Column(db.Numeric(12, 2), default=0, nullable=False)

    cliente = db.relationship("Cliente", back_populates="ventas")
    vendedor = db.relationship("User")
    detalles = db.relationship("DetalleVenta", back_populates="venta", cascade="all, delete-orphan")

    @property
    def numero(self):
        return f"F-{self.id:06d}"

    def recalcular(self):
        iva_tasa = current_app.config["IVA"]
        self.subtotal = sum((d.subtotal for d in self.detalles), Decimal("0"))
        self.iva = (self.subtotal * iva_tasa).quantize(Decimal("0.01"))
        self.total = self.subtotal + self.iva


class DetalleVenta(db.Model):
    __tablename__ = "detalle_venta"
    id = db.Column(db.Integer, primary_key=True)
    venta_id = db.Column(db.Integer, db.ForeignKey("ventas.id"), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey("productos.id"), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    precio_unitario = db.Column(db.Numeric(12, 2), nullable=False)

    venta = db.relationship("Venta", back_populates="detalles")
    producto = db.relationship("Producto")

    @property
    def subtotal(self):
        return self.precio_unitario * self.cantidad


# --------------------------------------------------------------------- SCM
class Proveedor(db.Model):
    __tablename__ = "proveedores"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    nit = db.Column(db.String(30))
    contacto = db.Column(db.String(120))
    telefono = db.Column(db.String(30))
    email = db.Column(db.String(120))
    condiciones = db.Column(db.String(255))
    activo = db.Column(db.Boolean, default=True, nullable=False)


class OrdenCompra(db.Model):
    __tablename__ = "ordenes_compra"
    id = db.Column(db.Integer, primary_key=True)
    proveedor_id = db.Column(db.Integer, db.ForeignKey("proveedores.id"), nullable=False)
    comprador_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    fecha_emision = db.Column(db.DateTime, default=datetime.now, nullable=False)
    fecha_recepcion = db.Column(db.DateTime)
    estado = db.Column(db.String(20), default="Pendiente", nullable=False)  # Pendiente | Recibido | Cancelado

    proveedor = db.relationship("Proveedor")
    comprador = db.relationship("User")
    detalles = db.relationship("DetalleOrden", back_populates="orden", cascade="all, delete-orphan")

    @property
    def numero(self):
        return f"OC-{self.id:05d}"

    @property
    def total(self):
        return sum((d.subtotal for d in self.detalles), Decimal("0"))


class DetalleOrden(db.Model):
    __tablename__ = "detalle_orden"
    id = db.Column(db.Integer, primary_key=True)
    orden_id = db.Column(db.Integer, db.ForeignKey("ordenes_compra.id"), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey("productos.id"), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    costo_unitario = db.Column(db.Numeric(12, 2), nullable=False)

    orden = db.relationship("OrdenCompra", back_populates="detalles")
    producto = db.relationship("Producto")

    @property
    def subtotal(self):
        return self.costo_unitario * self.cantidad


class MovimientoInventario(db.Model):
    """Bitácora de entradas y salidas de inventario."""
    __tablename__ = "movimientos_inventario"
    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey("productos.id"), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.now, nullable=False)
    tipo = db.Column(db.String(20), nullable=False)   # venta | compra | ajuste | anulacion
    cantidad = db.Column(db.Integer, nullable=False)  # positiva entra, negativa sale
    referencia = db.Column(db.String(60))
    usuario_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    producto = db.relationship("Producto")
    usuario = db.relationship("User")
