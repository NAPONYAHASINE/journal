import os

class Config:
    SECRET_KEY = 'aZ#2@9z!$?~1lkhQw'
    # Correction du chemin de la base de données pour utiliser un chemin absolu
    basedir = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(basedir, "instance", "trading_journal.db")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
