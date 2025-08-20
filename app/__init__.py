from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Initialize Flask app
app = Flask(__name__)
app.config.from_object('config.Config')

# Initialize extensions
db = SQLAlchemy(app)

# Suppression de Flask-Migrate
# Enregistrement des commandes CLI pour Flask-Migrate supprimé

# Suppression de l'importation de 'models' car models.py a été supprimé
from app import routes