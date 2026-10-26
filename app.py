from flask import Flask, render_template

from config import Config
from extensions import bcrypt, db, login_manager
from utils import crear_base_si_no_existe


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    crear_base_si_no_existe(app.config["SQLALCHEMY_DATABASE_URI"])

    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Inicia sesión para continuar."
    login_manager.login_message_category = "warning"

    # Blueprints (RNF-18: arquitectura modular)
    from routes.auth import bp as auth_bp
    from routes.main import bp as main_bp
    from routes.crm import bp as crm_bp
    from routes.erp import bp as erp_bp
    from routes.scm import bp as scm_bp
    for bp in (auth_bp, main_bp, crm_bp, erp_bp, scm_bp):
        app.register_blueprint(bp)

    @app.template_filter("moneda")
    def moneda(valor):
        valor = float(valor or 0)
        return "$" + f"{valor:,.0f}".replace(",", ".")

    @app.template_filter("fecha")
    def fecha(valor, formato="%d/%m/%Y"):
        return valor.strftime(formato) if valor else "—"

    @app.errorhandler(403)
    def prohibido(_):
        return render_template("error.html", codigo=403,
                               mensaje="No tienes permisos para ver esta página."), 403

    @app.errorhandler(404)
    def no_encontrado(_):
        return render_template("error.html", codigo=404,
                               mensaje="La página que buscas no existe."), 404

    with app.app_context():
        import models  # noqa: F401  (registra las tablas)
        db.create_all()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
