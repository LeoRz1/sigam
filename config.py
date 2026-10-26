import os
from decimal import Decimal


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "cambia-esta-clave-en-produccion")

    # MySQL en XAMPP: usuario root sin contraseña por defecto.
    # Para usar SQLite en desarrollo: set DATABASE_URL=sqlite:///database.db
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "mysql+pymysql://root:@localhost:3306/sistema_aceites?charset=utf8mb4",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    IVA = Decimal("0.19")          # IVA general en Colombia (los precios se guardan SIN IVA)
    DIAS_ALERTA_CAMBIO = 15        # días de anticipación para recordar cambio de aceite
    INTERVALO_CAMBIO_DIAS = 180    # intervalo por defecto entre cambios de aceite
