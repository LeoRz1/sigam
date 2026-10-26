from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from extensions import db
from models import ROLES, Cliente, User
from utils import roles_required

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(request.form.get("password", "")):
            if not user.activo:
                flash("Tu cuenta está desactivada. Contacta al administrador.", "danger")
            else:
                login_user(user)
                siguiente = request.args.get("next")
                return redirect(siguiente if siguiente and siguiente.startswith("/") else url_for("main.index"))
        else:
            flash("Correo o contraseña incorrectos.", "danger")
    return render_template("login.html")


@bp.route("/registro", methods=["GET", "POST"])
def registro():
    """Autoregistro: crea un usuario con rol cliente y su ficha en el CRM."""
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not nombre or not email or len(password) < 6:
            flash("Completa todos los campos (contraseña de mínimo 6 caracteres).", "danger")
        elif User.query.filter_by(email=email).first():
            flash("Ese correo ya está registrado.", "danger")
        else:
            user = User(nombre=nombre, email=email, rol="cliente")
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            db.session.add(Cliente(
                nombre=nombre, email=email, user_id=user.id,
                telefono=request.form.get("telefono", "").strip(),
                ciudad=request.form.get("ciudad", "").strip(), tipo="Particular",
            ))
            db.session.commit()
            flash("Cuenta creada. Ya puedes iniciar sesión.", "success")
            return redirect(url_for("auth.login"))
    return render_template("registro.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("auth.login"))


# ------------------------------------------------ Gestión de usuarios (RF-02)
@bp.route("/usuarios", methods=["GET", "POST"])
@roles_required()  # solo admin
def usuarios():
    if request.method == "POST":  # crear usuario interno
        email = request.form.get("email", "").strip().lower()
        rol = request.form.get("rol")
        password = request.form.get("password", "")
        if rol not in ROLES or not email or len(password) < 6:
            flash("Datos inválidos (contraseña de mínimo 6 caracteres).", "danger")
        elif User.query.filter_by(email=email).first():
            flash("Ese correo ya existe.", "danger")
        else:
            u = User(nombre=request.form.get("nombre", "").strip(), email=email, rol=rol)
            u.set_password(password)
            db.session.add(u)
            db.session.commit()
            flash("Usuario creado.", "success")
        return redirect(url_for("auth.usuarios"))
    return render_template("usuarios.html", usuarios=User.query.order_by(User.id).all(), roles=ROLES)


@bp.route("/usuarios/<int:uid>/actualizar", methods=["POST"])
@roles_required()
def usuario_actualizar(uid):
    u = db.get_or_404(User, uid)
    rol = request.form.get("rol")
    if u.id == current_user.id:
        flash("No puedes cambiar tu propio rol ni desactivarte.", "warning")
    else:
        if rol in ROLES:
            u.rol = rol
        u.activo = request.form.get("activo") == "1"
        db.session.commit()
        flash("Usuario actualizado.", "success")
    return redirect(url_for("auth.usuarios"))
