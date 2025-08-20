from flask import Flask
from main import app, db

# Suppression des dépendances liées à SQLAlchemy et Flask-Migrate
# Le fichier est maintenant nettoyé pour éviter les conflits.

def create_tables():
    """Crée toutes les tables manquantes dans la base de données."""
    with app.app_context():
        db.create_all()
        print("Toutes les tables ont été créées avec succès.")

def reset_db():
    """Réinitialise la base de données en supprimant et recréant toutes les tables."""
    with app.app_context():
        db.drop_all()
        db.create_all()
        print("La base de données a été réinitialisée avec succès.")

@app.cli.command('list_models')
def list_models():
    """Liste tous les modèles détectés par SQLAlchemy."""
    with app.app_context():
        for table in db.metadata.tables.keys():
            print(table)

@app.cli.command('list_tables')
def list_tables():
    """Liste toutes les tables dans la base de données."""
    with app.app_context():
        tables = db.engine.table_names()
        print("Tables in the database:", tables)

@app.cli.command('create_missing_tables')
def create_missing_tables():
    """Crée manuellement les tables manquantes dans la base de données."""
    with app.app_context():
        db.create_all()
        print("Toutes les tables manquantes ont été créées avec succès.")

@app.cli.command('init_db')
def init_db():
    """Initialise la base de données avec les tables nécessaires."""
    with app.app_context():
        db.create_all()
        print("Base de données initialisée avec succès.")

class Module(db.Model):
    __tablename__ = 'modules'

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    prix = db.Column(db.Float, nullable=False)
    competences = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(200), nullable=True)

    def __repr__(self):
        return f"<Module {self.nom}>"

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python manage_db.py [create_tables|reset_db|init_migrations|generate_migrations|apply_migrations]")
    else:
        command = sys.argv[1]
        if command == "create_tables":
            create_tables()
        elif command == "reset_db":
            reset_db()
        else:
            print(f"Commande inconnue : {command}")
    create_tables()