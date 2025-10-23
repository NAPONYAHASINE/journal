import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_paginate import Pagination, get_page_parameter
from pytz import timezone
from apscheduler.schedulers.background import BackgroundScheduler
import logging
import sqlite3
import atexit
from flask_sqlalchemy import SQLAlchemy
from validators import is_valid_email, is_valid_password, sanitize_string, parse_float, parse_datetime

# Placeholder for fetch_economic_events if not defined elsewhere
def fetch_economic_events():
    logging.info("Fetching economic events... (placeholder function)")
# Initialize Flask app
app = Flask(__name__)
app.config.from_object('config.Config')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/trading_journal.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialisation de SQLAlchemy
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(basedir, "instance", "trading_journal.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Suppression des références à Flask-Migrate

import os

# Correction du chemin de la base de données pour utiliser un chemin absolu
basedir = os.path.abspath(os.path.dirname(__file__))
def get_db_connection():
    return sqlite3.connect(os.path.join(basedir, 'instance', 'trading_journal.db'))

# Exemple de requête brute pour récupérer les analyses
def get_analyses(journal_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM analyses WHERE journal_id = ?', (journal_id,))
    analyses = cursor.fetchall()
    conn.close()
    return analyses

# Ajout d'une commande CLI pour tester l'application Flask
@app.cli.command('test_app')
def test_app():
    """Test si l'application Flask est correctement chargée."""
    print("L'application Flask est correctement chargée.")

# Configure logging
logging.basicConfig(level=logging.INFO)

# Secret key for session security
app.secret_key = os.environ.get('SECRET_KEY', 'default_secret_key')

# File upload configuration
basedir = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Allowed file extensions for uploads
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'mp4', 'mp3', 'wav', 'webm', 'ogg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Création de fichiers fictifs pour les fichiers manquants
uploads_dir = os.path.join(os.path.dirname(__file__), 'static', 'uploads')

# Créer intro.pdf
intro_path = os.path.join(uploads_dir, 'intro.pdf')
if not os.path.exists(intro_path):
    with open(intro_path, 'w') as f:
        f.write("Fichier fictif pour intro.pdf")

# Créer strategies.mp4
strategies_path = os.path.join(uploads_dir, 'strategies.mp4')
if not os.path.exists(strategies_path):
    with open(strategies_path, 'w') as f:
        f.write("Fichier fictif pour strategies.mp4")

#############################################
# Dictionnaires pour instruments prédéfinis et taux de conversion
#############################################

predefined_instruments = {
    # Forex
    "EUR/USD": {"type": "forex", "pip_value": 10, "quote_currency": "USD"},
    "GBP/USD": {"type": "forex", "pip_value": 10, "quote_currency": "USD"},
    "USD/JPY": {"type": "forex", "pip_value": 1000, "quote_currency": "JPY"},
    "AUD/USD": {"type": "forex", "pip_value": 10, "quote_currency": "USD"},
    "USD/CHF": {"type": "forex", "pip_value": 10, "quote_currency": "USD"},
    "NZD/USD": {"type": "forex", "pip_value": 10, "quote_currency": "USD"},
    "EUR/JPY": {"type": "forex", "pip_value": 1000, "quote_currency": "JPY"},
    "GBP/JPY": {"type": "forex", "pip_value": 1000, "quote_currency": "JPY"},
    "EUR/GBP": {"type": "forex", "pip_value": 10, "quote_currency": "GBP"},
    # Actions
    "AAPL": {"type": "stock", "multiplier": 1, "currency": "USD"},
    "TSLA": {"type": "stock", "multiplier": 1, "currency": "USD"},
    "MSFT": {"type": "stock", "multiplier": 1, "currency": "USD"},
    "AMZN": {"type": "stock", "multiplier": 1, "currency": "USD"},
    "GOOGL": {"type": "stock", "multiplier": 1, "currency": "USD"},
    "FB": {"type": "stock", "multiplier": 1, "currency": "USD"},
    # Futures
    "CAC40": {"type": "futures", "contract_size": 10, "point_value": 10, "currency": "EUR"},
    "SP500": {"type": "futures", "contract_size": 5, "point_value": 50, "currency": "USD"},
    "DAX": {"type": "futures", "contract_size": 25, "point_value": 5, "currency": "EUR"},
    "FTSE100": {"type": "futures", "contract_size": 10, "point_value": 10, "currency": "GBP"},
    # Commodités
    "Pétrole": {"type": "commodity", "contract_size": 100, "currency": "USD"},
    "Or": {"type": "commodity", "contract_size": 100, "currency": "USD"},
    "Argent": {"type": "commodity", "contract_size": 5000, "currency": "USD"},
    "Cuivre": {"type": "commodity", "contract_size": 25000, "currency": "USD"}
}

conversion_rates = {
    ("USD", "USD"): 1,
    ("EUR", "USD"): 1.1,
    ("USD", "EUR"): 0.91,
    ("JPY", "USD"): 0.007,
    ("USD", "JPY"): 140,
    ("EUR", "EUR"): 1,
    ("JPY", "EUR"): 0.0064,
    ("EUR", "JPY"): 130,
    ("JPY", "JPY"): 1,
    ("GBP", "USD"): 1.3,
    ("USD", "GBP"): 0.77,
    ("GBP", "GBP"): 1
}

#############################################
# Modèles de la base de données
#############################################

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    prenom = db.Column(db.String(50), nullable=False)
    nom = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    pays = db.Column(db.String(50), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    participate = db.Column(db.Boolean, default=False)

    assistance_messages = db.relationship('AssistanceMessage', backref='user', lazy=True)
    reflections = db.relationship('ReflectionEntry', backref='user', lazy=True)
    likes = db.relationship('Like', backref='user', lazy=True)
    groups_owned = db.relationship('Group', backref='owner', lazy=True)
    group_memberships = db.relationship('GroupMember', backref='user', lazy=True)
    group_messages = db.relationship('GroupMessage', backref='user', lazy=True)
    strategies = db.relationship('Strategy', backref='user', lazy=True)

    def __repr__(self):
        return f"<User {self.email}>"

class Journal(db.Model):
    __tablename__ = 'journals'

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    capital_initial = db.Column(db.Float, nullable=False)
    devise = db.Column(db.String(10), nullable=False)
    levier = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    user = db.relationship('User', backref=db.backref('journals', lazy=True))
    trades = db.relationship('Trade', backref='journal', lazy=True)
    analyses = db.relationship('Analysis', backref='journal', lazy=True)
    platform_links = db.relationship('PlatformLink', backref='journal', lazy=True)

    def __repr__(self):
        return f"<Journal {self.nom}>"

class Trade(db.Model):
    __tablename__ = 'trades'

    id = db.Column(db.Integer, primary_key=True)
    date_debut = db.Column(db.DateTime, nullable=False)
    date_fin = db.Column(db.DateTime, nullable=True)
    session = db.Column(db.String(50), nullable=False)
    instrument = db.Column(db.String(50), nullable=False)
    position = db.Column(db.String(10), nullable=False)
    prix_entree = db.Column(db.Float, nullable=False)
    prix_sortie = db.Column(db.Float, nullable=True)
    lot = db.Column(db.Float, nullable=False)
    risk_reward = db.Column(db.String(10), nullable=False)
    time_frame = db.Column(db.String(50), nullable=True)
    commentaires = db.Column(db.Text, nullable=True)
    capture = db.Column(db.String(200), nullable=True)
    resultat = db.Column(db.Float, nullable=True)
    pourcentage = db.Column(db.Float, nullable=True)
    statut = db.Column(db.String(20), default="EN_COURS")
    tags = db.Column(db.String(200), nullable=True)
    journal_id = db.Column(db.Integer, db.ForeignKey('journals.id'), nullable=False)
    date_enregistrement = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    reflections = db.relationship('ReflectionEntry', backref='trade', lazy=True)

    def __repr__(self):
        return f"<Trade {self.instrument} - {self.position}>"

class Analysis(db.Model):
    __tablename__ = 'analyses'

    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(100), nullable=False)
    contenu = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(200), nullable=True)
    journal_id = db.Column(db.Integer, db.ForeignKey('journals.id'), nullable=False)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Analysis {self.titre}>"

class PlatformLink(db.Model):
    __tablename__ = 'platform_links'

    id = db.Column(db.Integer, primary_key=True)
    plateforme = db.Column(db.String(100), nullable=False)
    identifiant = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text, nullable=True)
    journal_id = db.Column(db.Integer, db.ForeignKey('journals.id'), nullable=False)

    def __repr__(self):
        return f"<PlatformLink {self.plateforme}>"

class AssistanceMessage(db.Model):
    __tablename__ = 'assistance_messages'

    id = db.Column(db.Integer, primary_key=True)
    sujet = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

    replies = db.relationship('AssistanceReply', backref='assistance_message', lazy=True)

    def __repr__(self):
        return f"<AssistanceMessage {self.sujet}>"

class AssistanceReply(db.Model):
    __tablename__ = 'assistance_replies'

    id = db.Column(db.Integer, primary_key=True)
    reply_message = db.Column(db.Text, nullable=False)
    assistance_id = db.Column(db.Integer, db.ForeignKey('assistance_messages.id'), nullable=False)
    sender = db.Column(db.String(10), nullable=False)  # "user" or "admin"
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AssistanceReply {self.sender}>"

class InfoPost(db.Model):
    __tablename__ = 'info_posts'

    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(100), nullable=False)
    contenu = db.Column(db.Text, nullable=False)
    media = db.Column(db.String(200), nullable=True)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<InfoPost {self.titre}>"

class AnalysisShare(db.Model):
    __tablename__ = 'analysis_shares'

    id = db.Column(db.Integer, primary_key=True)
    analysis_id = db.Column(db.Integer, db.ForeignKey('analyses.id'), nullable=False)
    shared_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    shared_with = db.Column(db.String(100), nullable=False)

    analysis = db.relationship('Analysis', backref='shares', lazy=True)

    def __repr__(self):
        return f"<AnalysisShare {self.analysis_id}>"

class AnalysisShareComment(db.Model):
    __tablename__ = 'analysis_share_comments'

    id = db.Column(db.Integer, primary_key=True)
    share_id = db.Column(db.Integer, db.ForeignKey('analysis_shares.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AnalysisShareComment {self.comment}>"

class ReflectionEntry(db.Model):
    __tablename__ = 'reflection_entries'

    id = db.Column(db.Integer, primary_key=True)
    emotions = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    lessons_learned = db.Column(db.Text, nullable=True)
    trade_id = db.Column(db.Integer, db.ForeignKey('trades.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ReflectionEntry {self.id}>"

class Group(db.Model):
    __tablename__ = 'groups'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    def __repr__(self):
        return f"<Group {self.name}>"

class GroupMember(db.Model):
    __tablename__ = 'group_members'

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    def __repr__(self):
        return f"<GroupMember {self.group_id}-{self.user_id}>"

class GroupMessage(db.Model):
    __tablename__ = 'group_messages'

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=True)
    media = db.Column(db.String(200), nullable=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<GroupMessage {self.content}>"

class Strategy(db.Model):
    __tablename__ = 'strategies'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    rules = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    # Champs structurés ajoutés
    type = db.Column(db.String(50), nullable=True)
    instruments = db.Column(db.Text, nullable=True)
    timeframe = db.Column(db.String(20), nullable=True)
    entry_type = db.Column(db.String(20), nullable=True)
    exit_type = db.Column(db.Text, nullable=True)
    indicators = db.Column(db.Text, nullable=True)
    risk = db.Column(db.String(20), nullable=True)
    max_loss = db.Column(db.Float, nullable=True)

    def __repr__(self):
        return f"<Strategy {self.name}"


class Like(db.Model):
    __tablename__ = 'likes'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    def __repr__(self):
        return f"<Like {self.user_id}-{self.post_id}>"

class EconomicEvent(db.Model):
    __tablename__ = 'economic_events'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False)
    title = db.Column(db.String(100), nullable=False)
    impact = db.Column(db.String(50), nullable=False)
    currency = db.Column(db.String(10), nullable=False)
    description = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<EconomicEvent {self.title}>"

class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.String(200), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Notification {self.message}>"

class Goal(db.Model):
    __tablename__ = 'goals'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    target_value = db.Column(db.Float, nullable=False)
    current_value = db.Column(db.Float, default=0)
    progress_percentage = db.Column(db.Float, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    def __repr__(self):
        return f"<Goal {self.title}"

# --- ACADEMY ---
import sqlite3

@app.route('/academy')
def academy():
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    modules = conn.execute('SELECT * FROM modules').fetchall()
    modules_list = []
    for module in modules:
        cours = conn.execute('SELECT * FROM cours WHERE module_id = ?', (module['id'],)).fetchall()
        modules_list.append({'module': module, 'cours': cours})
    conn.close()
    return render_template('academy.html', modules=modules_list)

@app.route('/academy/module/create', methods=['GET', 'POST'])
def create_module():
    if request.method == 'POST':
        nom = request.form['nom']
        prix = request.form.get('prix', 0)  # Utilise 0 si le champ n'est pas envoyé
        nb_cours = request.form['nb_cours']
        description = request.form['description']
        competences = request.form['competences']
        image = request.files.get('image')
        image_filename = None
        if image and allowed_file(image.filename):
            image_filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
        conn = get_db_connection()
        conn.execute('INSERT INTO modules (nom, prix, nb_cours, description, competences, image, date_creation) VALUES (?, ?, ?, ?, ?, ?, datetime("now"))',
                     (nom, prix, nb_cours, description, competences, image_filename))
        conn.commit()
        conn.close()
        flash('Module créé avec succès!', 'success')
        return redirect(url_for('academy'))
    return render_template('create_module.html')

@app.route('/academy/module/<int:module_id>/cours/create', methods=['GET', 'POST'])
def create_cours(module_id):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    module = conn.execute('SELECT * FROM modules WHERE id = ?', (module_id,)).fetchone()
    if not module:
        conn.close()
        flash('Module introuvable.', 'danger')
        return redirect(url_for('academy'))
    if request.method == 'POST':
        titre = request.form['titre']
        description = request.form['description']
        prix = request.form['prix']
        fichier = request.files.get('fichier')
        fichier_filename = None
        if fichier and allowed_file(fichier.filename):
            fichier_filename = secure_filename(fichier.filename)
            fichier.save(os.path.join(app.config['UPLOAD_FOLDER'], fichier_filename))
        conn.execute('INSERT INTO cours (titre, description, prix, fichier, module_id, date_creation) VALUES (?, ?, ?, ?, ?, datetime("now"))',
                     (titre, description, prix, fichier_filename, module_id))
        conn.commit()
        conn.close()
        flash('Cours ajouté avec succès!', 'success')
        return redirect(url_for('academy'))
    conn.close()
    return render_template('create_cours.html', module=module)

@app.route('/academy/module/<int:module_id>')
def module_detail(module_id):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    module = conn.execute('SELECT * FROM modules WHERE id = ?', (module_id,)).fetchone()
    cours = conn.execute('SELECT * FROM cours WHERE module_id = ?', (module_id,)).fetchall()
    conn.close()
    if not module:
        flash('Module introuvable.', 'danger')
        return redirect(url_for('academy'))
    return render_template('module_detail.html', module=module, cours=cours)

@app.route('/academy/cours/<int:cours_id>', methods=['GET', 'POST'])
def cours_detail(cours_id):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cours = conn.execute('SELECT * FROM cours WHERE id = ?', (cours_id,)).fetchone()
    if not cours:
        conn.close()
        flash('Cours introuvable.', 'danger')
        return redirect(url_for('academy'))
    module = conn.execute('SELECT * FROM modules WHERE id = ?', (cours['module_id'],)).fetchone()
    # Gestion des likes
    likes_count = conn.execute('SELECT COUNT(*) FROM cours_likes WHERE cours_id = ?', (cours_id,)).fetchone()[0]
    liked = False
    if 'user_id' in session:
        user_like = conn.execute('SELECT 1 FROM cours_likes WHERE cours_id = ? AND user_id = ?', (cours_id, session['user_id'])).fetchone()
        liked = bool(user_like)
    # Gestion des commentaires
    commentaires = conn.execute('SELECT * FROM cours_comments WHERE cours_id = ? ORDER BY date_posted DESC', (cours_id,)).fetchall()
    commentaires_list = []
    for comment in commentaires:
        user = conn.execute('SELECT prenom FROM users WHERE id = ?', (comment['user_id'],)).fetchone()
        commentaires_list.append({
            'user_name': user['prenom'] if user else 'Utilisateur',
            'date_posted': comment['date_posted'],
            'text': comment['commentaire']
        })
    conn.close()
    return render_template('cours_detail.html', cours=cours, module=module, likes_count=likes_count, liked=liked, commentaires=commentaires_list)

@app.route('/academy/cours/<int:cours_id>/like', methods=['POST'])
def like_cours(cours_id):
    if 'user_id' not in session:
        flash('Vous devez être connecté pour aimer un cours.', 'warning')
        return redirect(url_for('cours_detail', cours_id=cours_id))
    conn = get_db_connection()
    already_liked = conn.execute('SELECT 1 FROM cours_likes WHERE cours_id = ? AND user_id = ?', (cours_id, session['user_id'])).fetchone()
    if already_liked:
        conn.execute('DELETE FROM cours_likes WHERE cours_id = ? AND user_id = ?', (cours_id, session['user_id']))
    else:
        conn.execute('INSERT INTO cours_likes (cours_id, user_id) VALUES (?, ?)', (cours_id, session['user_id']))
    conn.commit()
    conn.close()
    return redirect(url_for('cours_detail', cours_id=cours_id))

@app.route('/academy/cours/<int:cours_id>/comment', methods=['POST'])
def comment_cours(cours_id):
    if 'user_id' not in session:
        flash('Vous devez être connecté pour commenter.', 'warning')
        return redirect(url_for('cours_detail', cours_id=cours_id))
    commentaire = request.form.get('commentaire')
    if not commentaire or not commentaire.strip():
        flash('Le commentaire ne peut pas être vide.', 'warning')
        return redirect(url_for('cours_detail', cours_id=cours_id))
    conn = get_db_connection()
    conn.execute('INSERT INTO cours_comments (cours_id, user_id, commentaire, date_posted) VALUES (?, ?, ?, datetime("now"))', (cours_id, session['user_id'], commentaire))
    conn.commit()
    conn.close()
    flash('Commentaire ajouté avec succès!', 'success')
    return redirect(url_for('cours_detail', cours_id=cours_id))

@app.route('/academy/module/<int:module_id>/delete', methods=['POST'])
def delete_module(module_id):
    conn = get_db_connection()
    # Supprimer les cours liés au module
    conn.execute('DELETE FROM cours WHERE module_id = ?', (module_id,))
    # Supprimer le module
    conn.execute('DELETE FROM modules WHERE id = ?', (module_id,))
    conn.commit()
    conn.close()
    flash('Module supprimé avec succès!', 'success')
    return redirect(url_for('academy'))

@app.route('/academy/cours/<int:cours_id>/delete', methods=['POST'])
def delete_cours(cours_id):
    conn = get_db_connection()
    module_id = conn.execute('SELECT module_id FROM cours WHERE id = ?', (cours_id,)).fetchone()
    conn.execute('DELETE FROM cours WHERE id = ?', (cours_id,))
    conn.commit()
    conn.close()
    flash('Cours supprimé avec succès!', 'success')
    if module_id:
        return redirect(url_for('module_detail', module_id=module_id[0]))
    return redirect(url_for('academy'))

#############################################
# Routes et vues
#############################################

@app.context_processor
def inject_site_name():
    return {'site_name': 'NGA|BLOOM-HUB'}

@app.template_filter('datetimeformat')
def datetimeformat(value, format='%d %B %Y'):
    return value.strftime(format) if value else ""

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('home'))
    return render_template('landing.html')

# Routes d'authentification (fusionnées depuis auth_routes.py)
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Validation des champs avec limites
        ok, prenom = sanitize_string(request.form.get('prenom'), min_length=2, max_length=50)
        if not ok:
            flash(f"Prénom invalide : {prenom}")
            return redirect(url_for('register'))
            
        ok, nom = sanitize_string(request.form.get('nom'), min_length=2, max_length=50)
        if not ok:
            flash(f"Nom invalide : {nom}")
            return redirect(url_for('register'))
            
        ok, pays = sanitize_string(request.form.get('pays'), min_length=2, max_length=50, allow_empty=True)
        if not ok:
            flash(f"Pays invalide : {pays}")
            return redirect(url_for('register'))
            
        ok, email = sanitize_string(request.form.get('email'), min_length=5, max_length=100)
        if not ok:
            flash(f"Email invalide : {email}")
            return redirect(url_for('register'))
            
        password = request.form.get('password', '')

        # Préserver la logique d'administrateur via suffixe .admin (doit être retirée avant validation)
        is_admin = False
        if email.endswith('.adminBloom'):
            email = email.replace('.adminBloom', '')
            is_admin = True

        # Validation de l'email
        if not is_valid_email(email):
            flash("Format de l'email invalide.")
            return redirect(url_for('register'))

        # Validation du mot de passe
        ok, msg = is_valid_password(password)
        if not ok:
            flash(msg)
            return redirect(url_for('register'))

        # Vérification si l'email existe déjà
        if User.query.filter_by(email=email).first():
            flash("Cet email est déjà enregistré.")
            return redirect(url_for('register'))

        # is_admin is already set above

        new_user = User(
            prenom=prenom,
            nom=nom,
            pays=pays,
            email=email,
            password=generate_password_hash(password),
            is_admin=is_admin
        )
        db.session.add(new_user)
        db.session.commit()
        session['user_id'] = new_user.id
        session['user_name'] = new_user.prenom
        session['is_admin'] = new_user.is_admin
        flash("Inscription réussie ! Bienvenue.")
        return redirect(url_for('home'))
    return render_template('register.html')  # Removed {{ csrf_token() }} from the template

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['user_name'] = user.prenom
            session['is_admin'] = user.is_admin
            flash("Connexion réussie.")
            return redirect(url_for('home'))
        else:
            flash("Email ou mot de passe incorrect.")
            return redirect(url_for('login'))
    return render_template('login.html', journal=None)  # Removed {{ csrf_token() }} from the template

@app.route('/logout')
def logout():
    session.clear()
    flash("Déconnexion réussie.")
    return redirect(url_for('login'))

# 2. Gestion des journaux
@app.route('/home')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    journals = Journal.query.filter_by(user_id=session.get('user_id')).all()

    if not journals:
        flash("Aucun journal trouvé. Veuillez en créer un.")
        return redirect(url_for('create_journal'))

    total_trades = db.session.query(db.func.count(Trade.id)).join(Journal).filter(Journal.user_id == session['user_id']).scalar() or 0
    total_gains = db.session.query(db.func.sum(Trade.resultat)).join(Journal).filter(
        Journal.user_id == session['user_id'], Trade.statut == "TERMINE", Trade.resultat > 0
    ).scalar() or 0
    total_losses = db.session.query(db.func.sum(Trade.resultat)).join(Journal).filter(
        Journal.user_id == session['user_id'], Trade.statut == "TERMINE", Trade.resultat < 0
    ).scalar() or 0
    win_rate = (
        db.session.query(db.func.count(Trade.id)).join(Journal).filter(
            Journal.user_id == session['user_id'], Trade.statut == "TERMINE", Trade.resultat > 0
        ).scalar() / total_trades * 100 if total_trades > 0 else 0
    )

    stats = {
        "total_trades": total_trades,
        "total_gains": round(total_gains, 2),
        "total_losses": round(abs(total_losses), 2),
        "win_rate": round(win_rate, 2),
    }

    return render_template('home.html', journals=journals, stats=stats)

@app.route('/create_journal', methods=['GET', 'POST'])
def create_journal():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        nom = request.form['nom']
        capital_initial = request.form['capital_initial']
        devise = request.form['devise']
        levier_str = request.form.get('levier', '1')
        try:
            capital_initial = float(capital_initial)
            levier = float(levier_str)
        except ValueError:
            flash("Veuillez saisir des valeurs valides pour le capital initial et l'effet de levier.")
            return redirect(url_for('create_journal'))
        new_journal = Journal(
            nom=nom,
            capital_initial=capital_initial,
            devise=devise,
            levier=levier,
            user_id=session['user_id']
        )
        db.session.add(new_journal)
        db.session.commit()
        flash("Journal créé avec succès.")
        return redirect(url_for('home'))
    return render_template('create_journal.html')

@app.route('/dashboard/<int:journal_id>')
def dashboard(journal_id):
    journal = Journal.query.filter_by(id=journal_id, user_id=session['user_id']).first()
    if not journal:
        return redirect(url_for('home'))

    trades = Trade.query.filter_by(journal_id=journal.id).all()

    # Analyse par symbole
    trades_by_symbol = {}
    for trade in trades:
        symbol = trade.instrument
        if symbol not in trades_by_symbol:
            trades_by_symbol[symbol] = {'count': 0, 'total_result': 0, 'win_rate': 0}
        trades_by_symbol[symbol]['count'] += 1
        trades_by_symbol[symbol]['total_result'] += trade.resultat or 0
        if trade.resultat and trade.resultat > 0:
            trades_by_symbol[symbol]['win_rate'] += 1

    for symbol, data in trades_by_symbol.items():
        data['win_rate'] = (data['win_rate'] / data['count']) * 100 if data['count'] > 0 else 0

    # Analyse par tags
    trades_by_tag = {}
    for trade in trades:
        tags = (trade.tags or '').split(',')
        for tag in tags:
            tag = tag.strip()
            if not tag:
                continue
            if tag not in trades_by_tag:
                trades_by_tag[tag] = {'count': 0, 'total_result': 0, 'win_rate': 0}
            trades_by_tag[tag]['count'] += 1
            trades_by_tag[tag]['total_result'] += trade.resultat or 0
            if trade.resultat and trade.resultat > 0:
                trades_by_tag[tag]['win_rate'] += 1

    for tag, data in trades_by_tag.items():
        data['win_rate'] = (data['win_rate'] / data['count']) * 100 if data['count'] > 0 else 0

    # Analyse par heure
    trades_by_hour = {}
    for trade in trades:
        if trade.date_debut:
            hour = trade.date_debut.strftime('%H:00')
            if hour not in trades_by_hour:
                trades_by_hour[hour] = {'count': 0, 'total_result': 0}
            trades_by_hour[hour]['count'] += 1
            trades_by_hour[hour]['total_result'] += trade.resultat or 0

    # Calculate monthly data for charts
    monthly_data = {}
    for trade in trades:
        if trade.date_debut:
            month = trade.date_debut.strftime('%Y-%m')
            if month not in monthly_data:
                monthly_data[month] = {'gains': 0, 'count': 0}
            monthly_data[month]['gains'] += trade.resultat or 0
            monthly_data[month]['count'] += 1

    mois = list(monthly_data.keys())
    gains_per_month = [monthly_data[month]['gains'] for month in mois]
    trades_count = [monthly_data[month]['count'] for month in mois]

    # Correct calculation of total profit and loss
    total_profit = sum(
        (trade.prix_sortie - trade.prix_entree) * trade.lot * predefined_instruments[trade.instrument]['pip_value']
        if trade.instrument in predefined_instruments and predefined_instruments[trade.instrument]['type'] == 'forex' and trade.resultat > 0 else 0
        for trade in trades
    )

    total_loss = sum(
        (trade.prix_sortie - trade.prix_entree) * trade.lot * predefined_instruments[trade.instrument]['pip_value']
        if trade.instrument in predefined_instruments and predefined_instruments[trade.instrument]['type'] == 'forex' and trade.resultat < 0 else 0
    for trade in trades
    )

    total_loss = abs(total_loss)  # Ensure total_loss is positive for display purposes

    # Adjust win rate calculation to ensure accuracy
    total_wins = sum(1 for trade in trades if trade.resultat and trade.resultat > 0)
    total_trades = len(trades)
    win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0

    stats = {
        'solde': journal.capital_initial + sum(trade.resultat or 0 for trade in trades),
        'mois': mois,
        'gains_per_month': gains_per_month,
        'trades_count': trades_count,
        'total_profit': round(total_profit, 2),
        'total_loss': round(total_loss, 2),
        'win_rate': round(win_rate, 2)
    }

    return render_template(
        'dashboard.html',
        journal=journal,
        stats=stats,
        trades_by_symbol=trades_by_symbol,
        trades_by_tag=trades_by_tag,
        trades_by_hour=trades_by_hour
    )

@app.route('/performance_ranking')
def performance_ranking():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Récupérer uniquement les utilisateurs qui participent
    users = User.query.filter_by(participate=True).all()

    # Calculer la performance mensuelle pour chaque utilisateur
    performance_data = []
    for user in users:
        journals = Journal.query.filter_by(user_id=user.id).all()
        total_gains = 0
        total_losses = 0

        for journal in journals:
            trades = Trade.query.filter_by(journal_id=journal.id, statut="TERMINE").all()
            for trade in trades:
                if trade.resultat > 0:
                    total_gains += trade.resultat
                elif trade.resultat < 0:
                    total_losses += abs(trade.resultat)

        # Calculer la performance mensuelle en pourcentage
        if total_gains + total_losses > 0:
            performance_percentage = (total_gains / (total_gains + total_losses)) * 100
        else:
            performance_percentage = 0

        performance_data.append({
            'name': f"{user.prenom} {user.nom}",
            'performance': round(performance_percentage, 2)
        })

    # Trier les utilisateurs par performance décroissante
    performance_data.sort(key=lambda x: x['performance'], reverse=True)

    # Ajouter un champ `rank` pour chaque utilisateur
    for index, user in enumerate(performance_data, start=1):
        user['rank'] = index

    return render_template('performance_ranking.html', performance_ranking=performance_data)

## SUPPRESSION DE LA DEUXIEME DEFINITION (doublon)

@app.route('/participate_ranking', methods=['POST'])
def participate_ranking():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET participate = 1 WHERE id = ?', (session['user_id'],))
    conn.commit()
    conn.close()
    flash('Vous participez désormais au classement !')
    return redirect(url_for('performance_ranking'))
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Récupérer uniquement les utilisateurs qui participent
    users = User.query.filter_by(participate=True).all()

    # Calculer la performance mensuelle pour chaque utilisateur
    performance_data = []
    for user in users:
        journals = Journal.query.filter_by(user_id=user.id).all()
        total_gains = 0
        total_losses = 0

        for journal in journals:
            trades = Trade.query.filter_by(journal_id=journal.id, statut="TERMINE").all()
            for trade in trades:
                if trade.resultat > 0:
                    total_gains += trade.resultat
                elif trade.resultat < 0:
                    total_losses += abs(trade.resultat)

        # Calculer la performance mensuelle en pourcentage
        if total_gains + total_losses > 0:
            performance_percentage = (total_gains / (total_gains + total_losses)) * 100
        else:
            performance_percentage = 0

        performance_data.append({
            'name': f"{user.prenom} {user.nom}",
            'performance': round(performance_percentage, 2)
        })

    # Trier les utilisateurs par performance décroissante
    performance_data.sort(key=lambda x: x['performance'], reverse=True)

    # Ajouter un champ `rank` pour chaque utilisateur
    for index, user in enumerate(performance_data, start=1):
        user['rank'] = index

    return render_template('performance_ranking.html', performance_ranking=performance_data)

@app.route('/analysis_by_symbol')
def analysis_by_symbol():
    # Exemple de données fictives pour l'analyse par symbole
    trades_by_symbol = {
        'AAPL': {'count': 10, 'total_result': 500, 'win_rate': 70},
        'GOOGL': {'count': 8, 'total_result': 300, 'win_rate': 60},
    }
    return render_template('analysis_by_symbol.html', trades_by_symbol=trades_by_symbol)

@app.route('/analysis_by_tags')
def analysis_by_tags():
    # Exemple de données fictives pour l'analyse par tags
    trades_by_tag = {
        'Breakout': {'count': 15, 'total_result': 700, 'win_rate': 75},
        'Reversal': {'count': 5, 'total_result': -200, 'win_rate': 40},
    }
    return render_template('analysis_by_tags.html', trades_by_tag=trades_by_tag)

@app.route('/analysis_by_hour')
def analysis_by_hour():
    # Exemple de données fictives pour l'analyse par heure
    trades_by_hour = {
        '09:00': {'count': 5, 'total_result': 200},
        '10:00': {'count': 7, 'total_result': 300},
    }
    return render_template('analysis_by_hour.html', trades_by_hour=trades_by_hour)

@app.route('/strategy_check')
def strategy_check():
    # Exemple de messages fictifs pour la vérification des stratégies
    messages = [
        'Stratégie 1 : Valide',
        'Stratégie 2 : À améliorer',
    ]
    return render_template('strategy_check.html', messages=messages)

# 3. Gestion des Trades

def calculate_lot_size(account_risk, leverage, pip_value, base_currency_value):
    """
    Calcule la taille du lot en fonction du risque, de l'effet de levier, de la valeur par pip et de la valeur de la devise de base.

    :param account_risk: Montant risqué (en devise du compte)
    :param leverage: Effet de levier (exemple : 100 pour 1:100)
    :param pip_value: Valeur par pip (en devise du compte)
    :param base_currency_value: Valeur de la devise de base par rapport à la devise du compte
    :return: Taille du lot
    """
    # Calculer la taille de la position en fonction du risque et de l'effet de levier
    position_size = account_risk * leverage

    # Ajuster la taille de la position en fonction de la valeur de la devise de base
    adjusted_position_size = position_size / base_currency_value

    # Calculer la taille du lot
    lot_size = adjusted_position_size / pip_value
    return lot_size

def can_take_position(account_balance, leverage, lot_size, entry_price, instrument):
    """
    Vérifie si une position peut être prise en fonction du capital disponible, de l'effet de levier, et de la taille du lot.

    :param account_balance: Solde du compte (en devise du compte)
    :param leverage: Effet de levier (exemple : 100 pour 1:100)
    :param lot_size: Taille du lot (exemple : 0.01)
    :param entry_price: Prix d'entrée de la position
    :param instrument: Instrument financier (exemple : EUR/USD)
    :return: True si la position peut être prise, False sinon
    """
    # Récupérer les informations de l'instrument
    instrument_data = predefined_instruments.get(instrument)
    if not instrument_data:
        raise ValueError(f"Instrument {instrument} non défini dans predefined_instruments.")

    # Calculer la valeur de la position sans inclure l'effet de levier
    position_value = lot_size * entry_price

    # Calculer le capital requis avec l'effet de levier
    required_margin = position_value / leverage

    # Vérifier si le solde du compte permet de prendre la position
    return account_balance >= required_margin

@app.route('/trades/<int:journal_id>', methods=['GET', 'POST'])
def trades(journal_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    journal = Journal.query.filter_by(id=journal_id, user_id=session['user_id']).first()
    if not journal:
        flash("Journal introuvable ou non autorisé.")
        return redirect(url_for('home'))

    if request.method == 'POST':
        date_debut_str = sanitize_string(request.form.get('date_debut'))
        heure_debut_str = sanitize_string(request.form.get('heure_debut'))
        session_trade = sanitize_string(request.form.get('session'))
        instrument_selected = sanitize_string(request.form.get('instrument'))
        if instrument_selected == "Autre":
            instrument = request.form.get('custom_instrument')
            if not instrument or not instrument.strip():
                flash("Veuillez renseigner l'instrument personnalisé si 'Autre' est sélectionné.")
                return redirect(url_for('trades', journal_id=journal_id))
            predefined = None
        else:
            instrument = instrument_selected
            predefined = predefined_instruments.get(instrument)
        position = sanitize_string(request.form.get('position'))
        prix_entree_str = sanitize_string(request.form.get('prix_entree'))
        lot_str = sanitize_string(request.form.get('lot'))
        rr_str = sanitize_string(request.form.get('risk_reward'))
        tags = sanitize_string(request.form.get('tags', ''))

        # --- SUPPRESSION DES CHAMPS LOWER/HIGHER TIME FRAME ---
        time_frame = sanitize_string(request.form.get('time_frame'))
        if not time_frame:
            flash("Veuillez sélectionner un time frame.")
            return redirect(url_for('trades', journal_id=journal_id))

        # Vérification supplémentaire : afficher les valeurs de tous les champs obligatoires pour debug
        if not all([date_debut_str, heure_debut_str, session_trade, instrument, position, prix_entree_str, lot_str, rr_str, time_frame]):
            flash("Veuillez remplir tous les champs obligatoires. Pour le Risk/Reward, utilisez le format '1:3'.")
            return redirect(url_for('trades', journal_id=journal_id))

        # --- CORRECTION DU CALCUL DU LOT ET RESULTAT ---
        # Le lot doit être pris tel que saisi par l'utilisateur, ne pas recalculer automatiquement
        try:
            user_timezone = timezone(request.form.get('timezone', 'UTC'))
            dt = parse_datetime(date_debut_str, heure_debut_str)
            if not dt:
                flash("Date ou heure invalide.")
                return redirect(url_for('trades', journal_id=journal_id))
            date_debut = user_timezone.localize(dt)
            prix_entree = parse_float(prix_entree_str, None)
            lot = parse_float(lot_str, None)
            if prix_entree is None or lot is None:
                flash("Veuillez saisir des valeurs numériques valides pour le prix d'entrée et le lot.")
                return redirect(url_for('trades', journal_id=journal_id))
        except Exception:
            flash("Fuseau horaire ou date invalide.")
            return redirect(url_for('trades', journal_id=journal_id))

        capture_filename = None
        file = request.files.get('capture')
        if file and file.filename:
            if not allowed_file(file.filename):
                flash("Type de fichier non autorisé.")
                return redirect(url_for('trades', journal_id=journal_id))
            capture_filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            capture_filename = f"{timestamp}_{capture_filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], capture_filename))

        account_risk = float(request.form.get('account_risk', 100))  # Montant risqué par défaut : 100
        leverage = journal.levier

        # Correction pour éviter l'erreur lorsque 'prix_sortie' n'est pas défini
        prix_sortie_str = request.form.get('prix_sortie')
        if predefined:
            instr_type = predefined["type"]
            if instr_type == "forex":
                pip_size = 0.01 if predefined["quote_currency"] == "JPY" else 0.0001
                if prix_sortie_str:
                    prix_sortie = float(prix_sortie_str.replace(',', '.'))
                    pips = (prix_sortie - prix_entree) / pip_size if position.lower() == "achat" else (prix_entree - prix_sortie) / pip_size
                    raw_result = pips * lot * predefined["pip_value"]
                    montant_injecte = abs(prix_entree * lot * predefined["pip_value"])
                else:
                    raw_result = None
                    montant_injecte = abs(prix_entree * lot * predefined["pip_value"])
                trade_currency = predefined["quote_currency"]
            elif instr_type == "stock":
                if prix_sortie_str:
                    prix_sortie = float(prix_sortie_str.replace(',', '.'))
                    raw_result = (prix_sortie - prix_entree) * lot
                else:
                    raw_result = None
                montant_injecte = abs(prix_entree * lot)
                trade_currency = predefined["currency"]
            elif instr_type == "futures":
                if prix_sortie_str:
                    prix_sortie = float(prix_sortie_str.replace(',', '.'))
                    raw_result = (prix_sortie - prix_entree) * predefined["contract_size"] * predefined["point_value"] if position.lower() == "achat" else (prix_entree - prix_sortie) * predefined["contract_size"] * predefined["point_value"]
                else:
                    raw_result = None
                montant_injecte = abs(prix_entree * predefined["contract_size"] * predefined["point_value"])
                trade_currency = predefined["currency"]
            elif instr_type == "commodity":
                if prix_sortie_str:
                    prix_sortie = float(prix_sortie_str.replace(',', '.'))
                    raw_result = (prix_sortie - prix_entree) * predefined["contract_size"] if position.lower() == "achat" else (prix_entree - prix_sortie) * predefined["contract_size"]
                else:
                    raw_result = None
                montant_injecte = abs(prix_entree * predefined["contract_size"])
                trade_currency = predefined["currency"]
            else:
                if prix_sortie_str:
                    prix_sortie = float(prix_sortie_str.replace(',', '.'))
                    raw_result = (prix_sortie - prix_entree) * lot if position.lower() == "achat" else (prix_entree - prix_sortie) * lot
                else:
                    raw_result = None
                montant_injecte = abs(prix_entree * lot)
                trade_currency = journal.devise
        else:
            if prix_sortie_str:
                prix_sortie = float(prix_sortie_str.replace(',', '.'))
                raw_result = (prix_sortie - prix_entree) * lot if position.lower() == "achat" else (prix_entree - prix_sortie) * lot
            else:
                raw_result = None
            montant_injecte = abs(prix_entree * lot)
            trade_currency = journal.devise

        if raw_result is not None:
            journal_currency = journal.devise
            conversion_rate = conversion_rates.get((trade_currency, journal_currency), 1)
            result_converted = raw_result * conversion_rate
        else:
            result_converted = None

        # Pourcentage basé sur le capital initial du journal
        if result_converted is not None and journal.capital_initial:
            pourcentage = (result_converted / journal.capital_initial) * 100
        else:
            pourcentage = 0
        # --- ENREGISTREMENT DU TRADE ---
        from datetime import datetime as dt
        date_enregistrement = dt.now()
        new_trade = Trade(
            date_debut=date_debut,
            session=session_trade,
            instrument=instrument,
            position=position,
            prix_entree=prix_entree,
            lot=lot,
            risk_reward=rr_str,
            time_frame=time_frame,
            commentaires=request.form.get('commentaires', ''),
            capture=capture_filename,
            journal_id=journal.id,
            resultat=result_converted,
            pourcentage=pourcentage,
            tags=tags,
            date_enregistrement=date_enregistrement
        )
        if request.form.get('date_fin') and request.form.get('heure_fin') and request.form.get('prix_sortie'):
            try:
                date_fin = datetime.strptime(request.form.get('date_fin') + ' ' + request.form.get('heure_fin'), '%Y-%m-%d %H:%M')
                prix_sortie = float(request.form.get('prix_sortie').replace(',', '.'))
                # Recalcule le résultat et le montant injecté à la clôture
                if predefined:
                    instr_type = predefined["type"]
                    if instr_type == "forex":
                        pip_size = 0.01 if predefined["quote_currency"] == "JPY" else 0.0001
                        pips = (prix_sortie - prix_entree) / pip_size if position.lower() == "achat" else (prix_entree - prix_sortie) / pip_size
                        raw_result = pips * lot * predefined["pip_value"]
                        montant_injecte = abs(prix_entree * lot * predefined["pip_value"])
                        trade_currency = predefined["quote_currency"]
                    elif instr_type == "stock":
                        raw_result = (prix_sortie - prix_entree) * lot if position.lower() == "achat" else (prix_entree - prix_sortie) * lot
                        montant_injecte = abs(prix_entree * lot)
                        trade_currency = predefined["currency"]
                    elif instr_type == "futures":
                        raw_result = (prix_sortie - prix_entree) * predefined["contract_size"] * predefined["point_value"] if position.lower() == "achat" else (prix_entree - prix_sortie) * predefined["contract_size"] * predefined["point_value"]
                        montant_injecte = abs(prix_entree * predefined["contract_size"] * predefined["point_value"])
                        trade_currency = predefined["currency"]
                    elif instr_type == "commodity":
                        raw_result = (prix_sortie - prix_entree) * predefined["contract_size"] if position.lower() == "achat" else (prix_entree - prix_sortie) * predefined["contract_size"]
                        montant_injecte = abs(prix_entree * predefined["contract_size"])
                        trade_currency = predefined["currency"]
                    else:
                        raw_result = (prix_sortie - prix_entree) * lot if position.lower() == "achat" else (prix_entree - prix_sortie) * lot
                        montant_injecte = abs(prix_entree * lot)
                        trade_currency = journal.devise
                else:
                    raw_result = (prix_sortie - prix_entree) * lot if position.lower() == "achat" else (prix_entree - prix_sortie) * lot
                    montant_injecte = abs(prix_entree * lot)
                    trade_currency = journal.devise
                journal_currency = journal.devise
                conversion_rate = conversion_rates.get((trade_currency, journal_currency), 1)
                result_converted = raw_result * conversion_rate
                # Pourcentage basé sur le capital initial du journal
                if result_converted is not None and journal.capital_initial:
                    pourcentage = (result_converted / journal.capital_initial) * 100
                else:
                    pourcentage = 0
                new_trade.date_fin = date_fin
                new_trade.prix_sortie = prix_sortie
                new_trade.resultat = result_converted
                new_trade.pourcentage = pourcentage
                new_trade.statut = "TERMINE"
            except ValueError:
                flash("Valeur incorrecte pour le prix de sortie ou la date de fin.")
                return redirect(url_for('trades', journal_id=journal_id))
        db.session.add(new_trade)
        db.session.commit()
        flash("Trade enregistré avec succès.")
        return redirect(url_for('trades', journal_id=journal.id))

    trades_encours = Trade.query.filter_by(journal_id=journal.id, statut="EN_COURS").order_by(Trade.date_enregistrement.asc(), Trade.id.asc()).all()
    trades_termine = Trade.query.filter(Trade.journal_id == journal.id, Trade.statut == "TERMINE").order_by(Trade.date_enregistrement.asc(), Trade.id.asc()).all()
    trades_ordered = Trade.query.filter_by(journal_id=journal.id).order_by(Trade.date_enregistrement.asc(), Trade.id.asc()).all()
    numero_ordre_map = {t.id: idx for idx, t in enumerate(trades_ordered, start=1)}

    return render_template(
        'trades.html',
        journal=journal,
        trades_encours=trades_encours,
        trades_termine=trades_termine,
        numero_ordre_map=numero_ordre_map
    )

@app.route('/trade/<int:trade_id>', methods=['GET', 'POST'])
def trade_detail(trade_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    trade = Trade.query.get(trade_id)
    if not trade:
        flash("Trade introuvable.")
        return redirect(url_for('home'))
    journal = Journal.query.get(trade.journal_id)
    if not journal or journal.user.id != session['user_id']:
        flash("Accès non autorisé.")
        return redirect(url_for('home'))
    # Calcul du numéro d'ordre du trade dans le journal (par date_debut croissante)
    trades_ordered = Trade.query.filter_by(journal_id=journal.id).order_by(Trade.date_debut.asc(), Trade.id.asc()).all()
    numero_ordre = None
    for idx, t in enumerate(trades_ordered, start=1):
        if t.id == trade.id:
            numero_ordre = idx
            break
    if request.method == 'POST':
        date_fin_str = request.form.get('date_fin')
        heure_fin_str = request.form.get('heure_fin')
        prix_sortie_str = request.form.get('prix_sortie')
        if date_fin_str and heure_fin_str and prix_sortie_str:
            try:
                date_fin = datetime.strptime(date_fin_str + ' ' + heure_fin_str, '%Y-%m-%d %H:%M')
                prix_sortie = float(prix_sortie_str.replace(',', '.'))
                trade.date_fin = date_fin
                trade.prix_sortie = prix_sortie
                if trade.position.lower() == "achat":
                    trade.resultat = (prix_sortie - trade.prix_entree) * trade.lot
                    trade.pourcentage = ((prix_sortie - trade.prix_entree) / trade.prix_entree) * 100
                else:
                    trade.resultat = (trade.prix_entree - prix_sortie) * trade.lot
                    trade.pourcentage = ((trade.prix_entree - prix_sortie) / trade.prix_entree) * 100
                trade.statut = "TERMINE"
                db.session.commit()
                flash("Trade mis à jour et terminé.")
            except ValueError:
                flash("Valeur incorrecte pour le prix de sortie ou la date de fin.")
        return redirect(url_for('trade_detail', trade_id=trade.id))
    return render_template('trade_detail.html', trade=trade, numero_ordre=numero_ordre)

@app.route('/edit_trade/<int:trade_id>', methods=['GET', 'POST'])
def edit_trade(trade_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    trade = Trade.query.get(trade_id)
    if not trade:
        flash("Trade introuvable.")
        return redirect(url_for('home'))
    journal = Journal.query.get(trade.journal_id)
    if not journal or journal.user.id != session['user_id']:
        flash("Accès non autorisé.")
        return redirect(url_for('home'))
    if request.method == 'POST':
        try:
            trade.date_debut = datetime.strptime(request.form['date_debut'] + ' ' + request.form['heure_debut'], '%Y-%m-%d %H:%M')
            trade.session = request.form['session']
            trade.instrument = request.form['instrument']
            trade.position = request.form['position']
            trade.prix_entree = float(request.form['prix_entree'].replace(',', '.'))
            trade.lot = float(request.form['lot'])
            trade.risk_reward = request.form['risk_reward']
            trade.commentaires = request.form['commentaires']
            trade.tags = request.form['tags']
            if request.form.get('date_fin') and request.form.get('heure_fin') and request.form.get('prix_sortie'):
                trade.date_fin = datetime.strptime(request.form['date_fin'] + ' ' + request.form['heure_fin'], '%Y-%m-%d %H:%M')
                trade.prix_sortie = float(request.form.get('prix_sortie').replace(',', '.'))
                trade.resultat = (trade.prix_sortie - trade.prix_entree) * trade.lot
                trade.pourcentage = ((trade.prix_sortie - trade.prix_entree) / trade.prix_entree) * 100
                trade.statut = "TERMINE"
            db.session.commit()
            flash("Trade modifié avec succès.")
        except ValueError:
            flash("Erreur dans les données saisies.")
        return redirect(url_for('trades', journal_id=trade.journal_id))
    return render_template('edit_trade.html', trade=trade)

@app.route('/delete_trade/<int:trade_id>', methods=['POST'])
def delete_trade(trade_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    trade = Trade.query.get(trade_id)
    if not trade:
        flash("Trade introuvable.")
        return redirect(url_for('home'))
    journal = Journal.query.get(trade.journal_id)
    if not journal or journal.user.id != session['user_id']:
        flash("Accès non autorisé.")
        return redirect(url_for('home'))
    db.session.delete(trade)
    db.session.commit()
    flash("Trade supprimé avec succès.")
    return redirect(url_for('trades', journal_id=journal.id))

# 4. Gestion des Analyses
@app.route('/analyses/<int:journal_id>', methods=['GET', 'POST'])
def analyses(journal_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    journal = Journal.query.filter_by(id=journal_id, user_id=session['user_id']).first()
    if not journal:
        flash("Journal introuvable ou non autorisé.")
        return redirect(url_for('home'))
    if request.method == 'POST':
        titre = request.form['titre']
        contenu = request.form['contenu']
        image_filename = None
        file = request.files.get('image')
        if file and file.filename:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            image_filename = f"{timestamp}_{file.filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
        new_analysis = Analysis(titre=titre, contenu=contenu, image=image_filename, journal_id=journal.id)
        db.session.add(new_analysis)
        db.session.commit()
        flash("Analyse ajoutée avec succès.")
        return redirect(url_for('analyses', journal_id=journal_id))
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = 10
    analyses_list = Analysis.query.filter_by(journal_id=journal.id).paginate(page=page, per_page=per_page, error_out=False)
    return render_template('analyses.html', journal=journal, analyses=analyses_list.items, pagination=analyses_list)

@app.route('/analysis/<int:analysis_id>')
def analysis_detail(analysis_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    analysis = Analysis.query.get(analysis_id)
    if not analysis:
        flash("Analyse introuvable.")
        return redirect(url_for('home'))
    journal = Journal.query.get(analysis.journal_id)
    if not journal or journal.user.id != session['user_id']:
        flash("Accès non autorisé.")
        return redirect(url_for('home'))
    return render_template('analysis_detail.html', analysis=analysis)

# 5. Liaison de plateformes externes
@app.route('/link_platform/<int:journal_id>', methods=['GET', 'POST'])
def link_platform(journal_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    journal = Journal.query.filter_by(id=journal_id, user_id=session['user_id']).first()
    if not journal:
        flash("Journal introuvable ou non autorisé.")
        return redirect(url_for('home'))
    if request.method == 'POST':
        plateforme = request.form['plateforme']
        identifiant = request.form['identifiant']
        details = request.form['details']
        new_link = PlatformLink(plateforme=plateforme, identifiant=identifiant, details=details, journal_id=journal.id)
        db.session.add(new_link)
        db.session.commit()
        flash("Plateforme liée avec succès.")
        return redirect(url_for('link_platform', journal_id=journal.id))
    links = PlatformLink.query.filter_by(journal_id=journal.id).all()
    return render_template('link_platform.html', journal=journal, links=links)

# 6. Paramètres utilisateur
@app.route('/parametres', methods=['GET', 'POST'])
def parametres():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user:
        flash("Utilisateur introuvable.")
        return redirect(url_for('login'))
    if request.method == 'POST':
        if 'new_password' in request.form:
            new_password = request.form['new_password']
            if len(new_password) < 8:
                flash("Le mot de passe doit contenir au moins 8 caractères.")
                return redirect(url_for('parametres'))
            user.password = generate_password_hash(new_password)
            db.session.commit()
            flash("Mot de passe mis à jour avec succès.")
        elif 'theme' in request.form:
            session['theme'] = request.form['theme']
            flash("Thème mis à jour.")
    return render_template('parametres.html', user=user, theme=session.get('theme', 'light'))  # Removed {{ csrf_token() }} from the template

# 7. Assistance utilisateur
@app.route('/assistance', methods=['GET', 'POST'])
def assistance():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        sujet = request.form['sujet']
        message = request.form['message']
        new_msg = AssistanceMessage(sujet=sujet, message=message, user_id=session['user_id'])
        db.session.add(new_msg)
        db.session.commit()
        flash("Votre message a été envoyé. Un administrateur vous répondra prochainement.")
        return redirect(url_for('assistance'))
    user_msgs = AssistanceMessage.query.filter_by(user_id=session['user_id']).all()
    return render_template('my_assistance.html', user_msgs=user_msgs)

@app.route('/my_conversation/<int:msg_id>', methods=['GET', 'POST'])
def my_conversation(msg_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    msg = AssistanceMessage.query.get(msg_id)
    if not msg or msg.user_id != session['user_id']:
        flash("Message introuvable ou non autorisé.")
        return redirect(url_for('assistance'))
    if request.method == 'POST':
        reply_text = request.form['reply']
        new_reply = AssistanceReply(reply_message=reply_text, assistance_id=msg.id, sender="user")
        db.session.add(new_reply)
        db.session.commit()
        flash("Réponse envoyée.")
        return redirect(url_for('my_conversation', msg_id=msg.id))
    return render_template('my_conversation.html', msg=msg)

# 8. Admin – Assistance et conversation
@app.route('/admin_assistance')
def admin_assistance():
    if 'user_id' not in session or not session.get('is_admin'):
        flash("Accès refusé.")
        return redirect(url_for('login'))
    messages = AssistanceMessage.query.order_by(AssistanceMessage.date_creation.desc()).all()
    return render_template('admin_assistance.html', messages=messages)

@app.route('/conversation/<int:msg_id>', methods=['GET', 'POST'])
def conversation_detail(msg_id):
    if 'user_id' not in session or not session.get('is_admin'):
        flash("Accès refusé.")
        return redirect(url_for('login'))
    msg = AssistanceMessage.query.get(msg_id)
    if not msg:
        flash("Message introuvable.")
        return redirect(url_for('admin_assistance'))
    if request.method == 'POST':
        reply_text = request.form['reply']
        new_reply = AssistanceReply(reply_message=reply_text, assistance_id=msg.id, sender="admin")
        db.session.add(new_reply)
        db.session.commit()
        flash("Réponse envoyée.")
        return redirect(url_for('conversation_detail', msg_id=msg.id))
    return render_template('conversation_detail.html', msg=msg)

# 9. Publications Info (façon "reel")
@app.route('/info', methods=['GET', 'POST'])
def info():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session.get('is_admin') and request.method == 'POST':
        # Validation du titre
        ok, titre = sanitize_string(request.form.get('titre'), min_length=3, max_length=100)
        if not ok:
            flash(f"Titre invalide : {titre}")
            return redirect(url_for('info'))

        # Validation du contenu
        ok, contenu = sanitize_string(request.form.get('contenu'), min_length=10, max_length=MAX_TEXT_LENGTH)
        if not ok:
            flash(f"Contenu invalide : {contenu}")
            return redirect(url_for('info'))

        media_filename = None
        file = request.files.get('media')
        if file and file.filename:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            media_filename = f"{timestamp}_{file.filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], media_filename))
        new_info = InfoPost(titre=titre, contenu=contenu, media=media_filename)
        db.session.add(new_info)
        db.session.commit()
        flash("Publication créée avec succès.")
        return redirect(url_for('info'))
    posts = InfoPost.query.order_by(InfoPost.id.desc()).all()
    return render_template('info.html', posts=posts)

@app.route('/edit_info/<int:post_id>', methods=['GET', 'POST'])
def edit_info(post_id):
    if 'user_id' not in session or not session.get('is_admin'):
        flash("Accès refusé.")
        return redirect(url_for('info'))

    post = InfoPost.query.get(post_id)
    if not post:
        flash("Publication introuvable.")
        return redirect(url_for('info'))

    if request.method == 'POST':
        post.titre = request.form['titre']
        post.contenu = request.form['contenu']
        if 'media' in request.files:
            file = request.files['media']
            if file and file.filename:
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                media_filename = f"{timestamp}_{file.filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], media_filename))
                post.media = media_filename
        db.session.commit()
        flash("Publication mise à jour avec succès.")
        return redirect(url_for('info'))

    return render_template('edit_info.html', post=post)

@app.route('/delete_info/<int:post_id>', methods=['POST'])
def delete_info(post_id):
    if 'user_id' not in session or not session.get('is_admin'):
        flash("Accès refusé.")
        return redirect(url_for('login'))

    post = InfoPost.query.get(post_id)
    if not post:
        flash("Publication introuvable.")
        return redirect(url_for('info'))

    db.session.delete(post)
    db.session.commit()
    flash("Publication supprimée avec succès.")
    return redirect(url_for('info'))

# 10. Espace Administrateur – Gestion des utilisateurs
@app.route('/admin')
def admin():
    if 'user_id' not in session or not session.get('is_admin'):
        flash("Accès refusé.")
        return redirect(url_for('login'))
    try:
        users = User.query.all()
    except Exception as e:
        flash(f"Erreur lors de l'accès aux utilisateurs : {str(e)}")
        return redirect(url_for('home'))
    return render_template('admin.html', users=users)

@app.route('/admin/edit_user/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    if 'user_id' not in session or not session.get('is_admin'):
        flash("Accès refusé.")
        return redirect(url_for('login'))
    user = User.query.get(user_id)
    if not user:
        flash("Utilisateur introuvable.")
        return redirect(url_for('admin'))
    if request.method == 'POST':
        # Validation du prénom
        ok, prenom = sanitize_string(request.form.get('prenom'), min_length=2, max_length=50)
        if not ok:
            flash(f"Prénom invalide : {prenom}")
            return redirect(url_for('edit_user', user_id=user.id))
        user.prenom = prenom

        # Validation du nom
        ok, nom = sanitize_string(request.form.get('nom'), min_length=2, max_length=50)
        if not ok:
            flash(f"Nom invalide : {nom}")
            return redirect(url_for('edit_user', user_id=user.id))
        user.nom = nom

        # Validation du pays
        ok, pays = sanitize_string(request.form.get('pays'), min_length=2, max_length=50, allow_empty=True)
        if not ok:
            flash(f"Pays invalide : {pays}")
            return redirect(url_for('edit_user', user_id=user.id))
        user.pays = pays

        # Validation de l'email
        ok, email = sanitize_string(request.form.get('email'), min_length=5, max_length=100)
        if not ok:
            flash(f"Email invalide : {email}")
            return redirect(url_for('edit_user', user_id=user.id))
        if not is_valid_email(email):
            flash("Format d'email invalide")
            return redirect(url_for('edit_user', user_id=user.id))
        user.email = email
        if 'new_password' in request.form and request.form['new_password']:
            new_pw = request.form['new_password']
            if len(new_pw) < 8:
                flash("Le mot de passe doit contenir au moins 8 caractères.")
                return redirect(url_for('edit_user', user_id=user.id))
            user.password = generate_password_hash(new_pw)
        if 'is_admin' in request.form:
            user.is_admin = True
        else:
            user.is_admin = False
        db.session.commit()
        flash("Informations de l'utilisateur mises à jour.")
        return redirect(url_for('admin'))
    return render_template('edit_user.html', user=user)

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if 'user_id' not in session or not session.get('is_admin'):
        flash("Accès refusé.")
        return redirect(url_for('login'))
    user = User.query.get(user_id)
    if not user:
        flash("Utilisateur introuvable.")
        return redirect(url_for('admin'))
    # Suppression de toutes les références liées à l'utilisateur
    AssistanceMessage.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    ReflectionEntry.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    Like.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    Strategy.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    Group.query.filter_by(owner_id=user.id).delete(synchronize_session=False)
    GroupMember.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    GroupMessage.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    Notification.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    Goal.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    AnalysisShare.query.filter_by(shared_by_user_id=user.id).delete(synchronize_session=False)
    AnalysisShareComment.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    # Suppression des analyses, trades et journaux dans le bon ordre
    journals = Journal.query.filter_by(user_id=user.id).all()
    for journal in journals:
        # 1. Supprimer les analyses liées à ce journal
        Analysis.query.filter_by(journal_id=journal.id).delete(synchronize_session=False)
        # 2. Supprimer les trades liés à ce journal
        Trade.query.filter_by(journal_id=journal.id).delete(synchronize_session=False)
        # 3. Supprimer le journal lui-même
        db.session.delete(journal)
    # 4. Supprimer l'utilisateur
    db.session.delete(user)
    db.session.commit()
    flash("Compte et toutes les données associées supprimés.")
    return redirect(url_for('admin'))

# 11. Partage d'analyses
@app.route('/share_analysis/<int:analysis_id>', methods=['GET', 'POST'])
def share_analysis(analysis_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    analysis = Analysis.query.get(analysis_id)
    if not analysis:
        flash("Analyse introuvable.")
        return redirect(url_for('home'))
    journal = Journal.query.get(analysis.journal_id)
    if not journal or journal.user.id != session['user_id']:
        flash("Accès non autorisé.")
        return redirect(url_for('home'))
    if request.method == 'POST':
        shared_with = request.form['shared_with']
        share = AnalysisShare(
            analysis_id=analysis.id,
            shared_by_user_id=session['user_id'],
            shared_with=shared_with
        )
        db.session.add(share)
        db.session.commit()
        flash("Analyse partagée avec succès.")
        return redirect(url_for('analysis_detail', analysis_id=analysis.id))
    return render_template('share_analysis.html', analysis=analysis)

@app.route('/community')
def community():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Fetch shared analyses
    shares = AnalysisShare.query.filter_by(shared_with='all').all()
    shares_with_comments = []
    for share in shares:
        comments = AnalysisShareComment.query.filter_by(share_id=share.id).all()
        shares_with_comments.append({'share': share, 'comments': comments})

   

    # Fetch user groups
    user_groups = Group.query.join(GroupMember).filter(GroupMember.user_id == session['user_id']).all()

    return render_template('community.html', shares=shares_with_comments, user_groups=user_groups)

@app.route('/my_shares')
def my_shares():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    shares = AnalysisShare.query.filter(AnalysisShare.shared_with != 'all', AnalysisShare.shared_with == user.email).all()
    return render_template('my_shares.html', shares=shares)

@app.route('/share_detail/<int:share_id>', methods=['GET', 'POST'])
def share_detail(share_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    share = AnalysisShare.query.get(share_id)
    if not share:
        flash("Partage introuvable.")
        return redirect(url_for('community'))
    user = User.query.get(session['user_id'])
    if share.shared_with != 'all' and share.shared_with != user.email:
        flash("Accès refusé.")
        return redirect(url_for('community'))
    if request.method == 'POST':
        comment_text = request.form['comment']
        new_comment = AnalysisShareComment(
            share_id=share.id,
            user_id=user.id,
            comment=comment_text
        )
        db.session.add(new_comment)
        db.session.commit()
        flash("Commentaire ajouté.")
        return redirect(url_for('share_detail', share_id=share.id))

    # Ensure the share object includes the latest comments
    share.comments = AnalysisShareComment.query.filter_by(share_id=share.id).all()
    return render_template('share_detail.html', share=share)



# 12. Service pour servir les fichiers uploadés
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    # Vérification du fichier avant de le servir
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        return "Fichier introuvable", 404

    # Détection du type MIME pour les vidéos and PDF
    mime_type = None
    if filename.endswith('.mp4'):
        mime_type = 'video/mp4'
    elif filename.endswith('.pdf'):
        mime_type = 'application/pdf'

    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, mimetype=mime_type)

# Route pour afficher et ajouter des entrées de réflexion
@app.route('/reflections', methods=['GET', 'POST'])
def reflections():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        emotions = request.form.get('emotions')
        notes = request.form.get('notes')
        lessons_learned = request.form.get('lessons_learned')
        trade_id = request.form.get('trade_id') or None
        new_entry = ReflectionEntry(
            emotions=emotions,
            notes=notes,
            lessons_learned=lessons_learned,
            trade_id=trade_id,
            user_id=session['user_id']
        )
        db.session.add(new_entry)
        db.session.commit()
        flash("Entrée de réflexion ajoutée avec succès.")
        return redirect(url_for('reflections'))
    entries = ReflectionEntry.query.filter_by(user_id=session['user_id']).order_by(ReflectionEntry.date_creation.desc()).all()
    trades = Trade.query.filter_by(journal_id=Journal.id, statut="TERMINE").all()  # Pour lier à un trade terminé
    return render_template('reflections.html', entries=entries, trades=trades)

# Route pour afficher les détails d'une réflexion
@app.route('/reflection/<int:reflection_id>')
def reflection_detail(reflection_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    entry = ReflectionEntry.query.get(reflection_id)
    if not entry or entry.user_id != session['user_id']:
        flash("Entrée de réflexion introuvable ou non autorisée.")
        return redirect(url_for('reflections'))
    return render_template('reflection_detail.html', entry=entry)

# Route pour supprimer une réflexion
@app.route('/delete_reflection/<int:reflection_id>', methods=['POST'])
def delete_reflection(reflection_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    entry = ReflectionEntry.query.get(reflection_id)
    if not entry or entry.user_id != session['user_id']:
        flash("Entrée de réflexion introuvable ou non autorisée.")
        return redirect(url_for('reflections'))
    db.session.delete(entry)
    db.session.commit()
    flash("Entrée de réflexion supprimée avec succès.")
    return redirect(url_for('reflections'))

@app.route('/calendar', methods=['GET', 'POST'])
def calendar():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST' and session.get('is_admin'):
        title = request.form['title']
        date_str = request.form['date']
        time_str = request.form['time']
        impact = request.form['impact']
        currency = request.form['currency']
        description = request.form.get('description', '')

        try:
            date = datetime.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M')
            new_event = EconomicEvent(
                date=date,
                title=title,
                impact=impact,
                currency=currency,
                description=description
            )
            db.session.add(new_event)
            db.session.commit()
            flash("Événement économique ajouté avec succès.")
        except ValueError:
            flash("Erreur dans la date ou l'heure saisie.")
        return redirect(url_for('calendar'))

    events = EconomicEvent.query.order_by(EconomicEvent.date.asc()).all()
    return render_template('calendar.html', events=events)

@app.route('/delete_event/<int:event_id>', methods=['POST'])
def delete_event(event_id):
    if 'user_id' not in session or not session.get('is_admin'):
        flash("Accès refusé.")
        return redirect(url_for('login'))
    event = EconomicEvent.query.get(event_id)
    if not event:
        flash("Événement introuvable.")
        return redirect(url_for('calendar'))
    db.session.delete(event)
    db.session.commit()
    flash("Événement supprimé avec succès.")
    return redirect(url_for('calendar'))

@app.route('/goals', methods=['GET', 'POST'])
def goals():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        # Validation du titre
        ok, title = sanitize_string(request.form.get('title'), min_length=3, max_length=100)
        if not ok:
            flash(f"Titre de l'objectif invalide : {title}")
            return redirect(url_for('goals'))

        # Validation de la description
        ok, description = sanitize_string(request.form.get('description', ''), 
                                        max_length=MAX_TEXT_LENGTH, 
                                        allow_empty=True)
        if not ok:
            flash(f"Description invalide : {description}")
            return redirect(url_for('goals'))

        # Validation de la valeur cible
        ok, target_value = sanitize_string(request.form.get('target_value'))
        try:
            target_value = float(target_value)
            new_goal = Goal(
                title=title,
                description=description,
                target_value=target_value,
                user_id=session['user_id']
            )
            db.session.add(new_goal)
            db.session.commit()
            flash("Objectif ajouté avec succès.")
        except ValueError:
            flash("Veuillez entrer une valeur numérique valide pour l'objectif.")
        return redirect(url_for('goals'))



    goals = Goal.query.filter_by(user_id=session['user_id']).all()
    return render_template('goals.html', goals=goals)

@app.route('/update_goal/<int:goal_id>', methods=['POST'])
def update_goal(goal_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    goal = Goal.query.get(goal_id)
    if not goal or goal.user_id != session['user_id']:
        flash("Objectif introuvable ou non autorisé.")
        return redirect(url_for('goals'))
    try:
        progress = float(request.form['progress'])
        goal.current_value += progress
        goal.progress_percentage = (goal.current_value / goal.target_value) * 100
        db.session.commit()
        flash("Progression mise à jour avec succès.")
    except ValueError:
        flash("Veuillez entrer une valeur numérique valide pour la progression.")
    return redirect(url_for('goals'))

@app.route('/delete_goal/<int:goal_id>', methods=['POST'])
def delete_goal(goal_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    goal = Goal.query.get(goal_id)
    if not goal or goal.user_id != session['user_id']:
        flash("Objectif introuvable ou non autorisé.")
        return redirect(url_for('goals'))
    db.session.delete(goal)
    db.session.commit()
    flash("Objectif supprimé avec succès.")
    return redirect(url_for('goals'))

@app.route('/notifications')
def notifications():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_notifications = Notification.query.filter_by(user_id=session['user_id']).order_by(Notification.date_creation.desc()).all()
    return render_template('notifications.html', notifications=user_notifications)

@app.route('/mark_notification_read/<int:notification_id>', methods=['POST'])
def mark_notification_read(notification_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    notification = Notification.query.get(notification_id)
    if not notification or notification.user_id != session['user_id']:
        flash("Notification introuvable ou non autorisée.")
        return redirect(url_for('notifications'))
    notification.is_read = True
    db.session.commit()
    flash("Notification marquée comme lue.")
    return redirect(url_for('notifications'))

@app.route('/delete_notification/<int:notification_id>', methods=['POST'])
def delete_notification(notification_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    notification = Notification.query.get(notification_id)
    if not notification or notification.user_id != session['user_id']:
        flash("Notification introuvable ou non autorisée.")
        return redirect(url_for('notifications'))
    db.session.delete(notification)
    db.session.commit()
    flash("Notification supprimée avec succès.")
    return redirect(url_for('notifications'))

# Fonction pour créer une notification (appelée automatiquement dans d'autres parties du code)
def create_notification(user_id, message):
    new_notification = Notification(user_id=user_id, message=message)
    db.session.add(new_notification)
    db.session.commit()

# Exemple d'intégration : notifier un objectif proche de sa réalisation
@app.route('/check_goals')
def check_goals():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    goals = Goal.query.filter_by(user_id=session['user_id']).all()
    for goal in goals:
        if goal.progress_percentage >= 90 and not Notification.query.filter_by(user_id=session['user_id'], message=f"Votre objectif '{goal.title}' est proche de sa réalisation !").first():
            create_notification(session['user_id'], f"Votre objectif '{goal.title}' est proche de sa réalisation !")
    flash("Vérification des objectifs effectuée.")
    return redirect(url_for('goals'))

@app.route('/groups', methods=['GET', 'POST'])
def groups():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        name = request.form['name']
        description = request.form.get('description', '')
        new_group = Group(name=name, description=description, owner_id=session['user_id'])
        db.session.add(new_group)
        db.session.commit()
        new_member = GroupMember(group_id=new_group.id, user_id=session['user_id'])
        db.session.add(new_member)
        db.session.commit()
        flash("Groupe créé avec succès.")
        return redirect(url_for('groups'))
    user_groups = Group.query.join(GroupMember).filter(GroupMember.user_id == session['user_id']).all()
    if not user_groups:
        flash("Aucun groupe trouvé. Veuillez en créer un.")

    return render_template('groups.html', groups=user_groups)

@app.route('/group/<int:group_id>', methods=['GET', 'POST'])
def group_detail(group_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    group = Group.query.get(group_id)
    if not group:
        flash("Groupe introuvable.")
        return redirect(url_for('groups'))

    # Vérifier si l'utilisateur est membre du groupe
    membership = GroupMember.query.filter_by(group_id=group_id, user_id=session['user_id']).first()
    if not membership:
        flash("Vous n'êtes pas membre de ce groupe.")
        return redirect(url_for('groups'))

    if request.method == 'POST':
        # Envoi d'un message ou d'un fichier multimédia
        content = request.form.get('content', '')
        file = request.files.get('media')
        media_filename = None

        if file and file.filename:
            if not allowed_file(file.filename):
                flash("Type de fichier non autorisé.")
                return redirect(url_for('group_detail', group_id=group_id))
            media_filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            media_filename = f"{timestamp}_{media_filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], media_filename))

        if content or media_filename:
            new_message = GroupMessage(
                content=content,
                media=media_filename,
                group_id=group_id,
                user_id=session['user_id']
            )
            db.session.add(new_message)
            db.session.commit()
            flash("Message envoyé avec succès.")
        return redirect(url_for('group_detail', group_id=group_id))

    messages = GroupMessage.query.filter_by(group_id=group_id).order_by(GroupMessage.date_creation.asc()).all()
    members = GroupMember.query.filter_by(group_id=group_id).all()

    return render_template('group_detail.html', group=group, messages=messages, members=members)

@app.route('/add_member/<int:group_id>', methods=['POST'])
def add_member(group_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    group = Group.query.get(group_id)
    if not group:
        flash("Groupe introuvable.")
        return redirect(url_for('groups'))

    if group.owner_id != session['user_id']:
        flash("Seul l'administrateur peut ajouter des membres.")
        return redirect(url_for('group_detail', group_id=group_id))

    email = request.form['email']
    user = User.query.filter_by(email=email).first()
    if not user:
        flash("Utilisateur introuvable.")
        return redirect(url_for('group_detail', group_id=group_id))

    existing_member = GroupMember.query.filter_by(group_id=group_id, user_id=user.id).first()
    if existing_member:
        flash("Cet utilisateur est déjà membre du groupe.")
        return redirect(url_for('group_detail', group_id=group_id))

    new_member = GroupMember(group_id=group_id, user_id=user.id)
    db.session.add(new_member)
    db.session.commit()
    flash("Membre ajouté avec succès.")
    return redirect(url_for('group_detail', group_id=group_id))

@app.route('/join_group/<int:group_id>', methods=['POST'])
def join_group(group_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if not GroupMember.query.filter_by(group_id=group_id, user_id=session['user_id']).first():
        new_member = GroupMember(group_id=group_id, user_id=session['user_id'])
        db.session.add(new_member)
        db.session.commit()
        flash("Vous avez rejoint le groupe.")
    return redirect(url_for('groups'))

@app.route('/leave_group/<int:group_id>', methods=['POST'])
def leave_group(group_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    membership = GroupMember.query.filter_by(group_id=group_id, user_id=session['user_id']).first()
    if membership:
        db.session.delete(membership)
        db.session.commit()
        flash("Vous avez quitté le groupe.")
    return redirect(url_for('groups'))

@app.route('/remove_member/<int:group_id>/<int:user_id>', methods=['POST'])
def remove_member(group_id, user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    group = Group.query.get(group_id)
    if not group:
        flash("Groupe introuvable.")
        return redirect(url_for('groups'))
    # Seul l'admin ou le membre lui-même peut se retirer
    if group.owner_id != session['user_id'] and user_id != session['user_id']:
        flash("Action non autorisée.")
        return redirect(url_for('group_detail', group_id=group_id))
    member = GroupMember.query.filter_by(group_id=group_id, user_id=user_id).first()
    if not member:
        flash("Membre introuvable.")
        return redirect(url_for('group_detail', group_id=group_id))
    db.session.delete(member)
    db.session.commit()
    flash("Membre retiré du groupe.")
    return redirect(url_for('group_detail', group_id=group_id))

@app.route('/strategies', methods=['GET', 'POST'])
def strategies():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        # Validation du nom de la stratégie
        ok, name = sanitize_string(request.form.get('name'), min_length=2, max_length=50)
        if not ok:
            flash(f"Nom de stratégie invalide : {name}")
            return redirect(url_for('strategies'))

        # Validation de la description
        ok, description = sanitize_string(request.form.get('description', ''), 
                                        max_length=MAX_TEXT_LENGTH, 
                                        allow_empty=True)
        if not ok:
            flash(f"Description invalide : {description}")
            return redirect(url_for('strategies'))

        # Validation des règles
        ok, rules = sanitize_string(request.form.get('rules'), 
                                  min_length=10, 
                                  max_length=MAX_TEXT_LENGTH)
        if not ok:
            flash(f"Règles invalides : {rules}")
            return redirect(url_for('strategies'))

        # Validation du type
        ok, type_ = sanitize_string(request.form.get('type', ''), 
                                  min_length=2, 
                                  max_length=50)
        if type_ == 'Autre':
            type_other = request.form.get('type_other', '').strip()
            if type_other:
                type_ = type_other
        # Instruments
        instruments = request.form.getlist('instruments')
        if 'Autre' in instruments:
            other = request.form.get('instruments_other', '').strip()
            if other:
                instruments = [i for i in instruments if i != 'Autre'] + [other]
        # Timeframe
        timeframe = request.form.get('timeframe', '')
        if timeframe == 'Autre':
            tf_other = request.form.get('timeframe_other', '').strip()
            if tf_other:
                timeframe = tf_other
        # Entry type
        entry_type = request.form.get('entry_type', '')
        if entry_type == 'Autre':
            entry_type_other = request.form.get('entry_type_other', '').strip()
            if entry_type_other:
                entry_type = entry_type_other
        # Exit type
        exit_type = request.form.getlist('exit_type')
        if 'Autre' in exit_type:
            exit_type_other = request.form.get('exit_type_other', '').strip()
            if exit_type_other:
                exit_type = [e for e in exit_type if e != 'Autre'] + [exit_type_other]
        # Indicators
        indicators = request.form.getlist('indicators')
        if 'Autre' in indicators:
            indicators_other = request.form.get('indicators_other', '').strip()
            if indicators_other:
                indicators = [i for i in indicators if i != 'Autre'] + [indicators_other]
        # Risk
        risk = request.form.get('risk', '')
        if risk == 'autre':
            risk_other = request.form.get('risk_other', '').strip()
            if risk_other:
                risk = risk_other
        max_loss = request.form.get('max_loss', None)
        # Conversion pour stockage (listes en string)
        instruments_str = ', '.join(instruments) if instruments else ''
        exit_type_str = ', '.join(exit_type) if exit_type else ''
        indicators_str = ', '.join(indicators) if indicators else ''
        # Création de la stratégie enrichie
        new_strategy = Strategy(
            name=name,
            description=description,
            rules=rules,
            user_id=session['user_id'],
            type=type_,
            instruments=instruments_str,
            timeframe=timeframe,
            entry_type=entry_type,
            exit_type=exit_type_str,
            indicators=indicators_str,
            risk=risk,
            max_loss=max_loss
        )
        db.session.add(new_strategy)
        db.session.commit()
        flash("Stratégie créée avec succès.")
        return redirect(url_for('strategies'))
    user_strategies = Strategy.query.filter_by(user_id=session['user_id']).all()
    return render_template('strategies.html', strategies=user_strategies)

@app.route('/strategy/<int:strategy_id>', methods=['GET', 'POST'])
def strategy_detail(strategy_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    strategy = Strategy.query.get(strategy_id)
    if not strategy or strategy.user_id != session['user_id']:
        flash("Stratégie introuvable ou non autorisée.")
        return redirect(url_for('strategies'))
    if request.method == 'POST':
        strategy.name = request.form['name']
        strategy.description = request.form.get('description', '')
        strategy.rules = request.form['rules']
        # Mise à jour des nouveaux champs
        type_ = request.form.get('type', '')
        if type_ == 'Autre':
            type_other = request.form.get('type_other', '').strip()
            if type_other:
                type_ = type_other
        strategy.type = type_
        strategy.instruments = ', '.join(request.form.getlist('instruments')) if request.form.getlist('instruments') else request.form.get('instruments', '')
        strategy.timeframe = request.form.get('timeframe', '')
        strategy.entry_type = request.form.get('entry_type', '')
        strategy.exit_type = ', '.join(request.form.getlist('exit_type')) if request.form.getlist('exit_type') else request.form.get('exit_type', '')
        strategy.indicators = ', '.join(request.form.getlist('indicators')) if request.form.getlist('indicators') else request.form.get('indicators', '')
        strategy.risk = request.form.get('risk', '')
        strategy.max_loss = request.form.get('max_loss', None)
        db.session.commit()
        flash("Stratégie mise à jour avec succès.")
        return redirect(url_for('strategy_detail', strategy_id=strategy_id))
    return render_template('strategy_detail.html', strategy=strategy)

@app.route('/delete_strategy/<int:strategy_id>', methods=['POST'])
def delete_strategy(strategy_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    strategy = Strategy.query.get(strategy_id)
    if not strategy or strategy.user_id != session['user_id']:
        flash("Stratégie introuvable ou non autorisée.")
        return redirect(url_for('strategies'))
    db.session.delete(strategy)
    db.session.commit()
    flash("Stratégie supprimée avec succès.")
    return redirect(url_for('strategies'))

@app.route('/check_trades', methods=['GET'])
def check_trades():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    trades = Trade.query.join(Journal).filter(Journal.user_id == session['user_id']).all()
    strategies = Strategy.query.filter_by(user_id=session['user_id']).all()
    messages = []
    for trade in trades:
        for strategy in strategies:
            if strategy.name in (trade.tags or ''):
                if not evaluate_trade_against_strategy(trade, strategy):
                    messages.append(f"Le trade n°{trade.id} ne respecte pas la stratégie '{strategy.name}'.")
    return render_template('trade_check_results.html', messages=messages)

def evaluate_trade_against_strategy(trade, strategy):
    rules = strategy.rules.lower()
    if "risk/reward" in rules and "1:3" in rules:
        return trade.risk_reward == "1:3"
    return True

@app.route('/update_strategy_validations/<int:strategy_id>', methods=['POST'])
def update_strategy_validations(strategy_id):
    if 'user_id' not in session:
        flash("Vous devez être connecté pour effectuer cette action.")
        return redirect(url_for('login'))

    strategy = Strategy.query.get(strategy_id)
    if not strategy or strategy.user_id != session['user_id']:
        flash("Stratégie introuvable ou non autorisée.")
        return redirect(url_for('strategies'))

    # Process the form data to update validations
    # Assuming `validations` is a list of validation objects
    # Adjusted to avoid errors if validations are not defined
    if hasattr(strategy, 'validations'):
        for index, validation in enumerate(strategy.validations):
            validation.completed = f'validation_{index + 1}' in request.form

    db.session.commit()
    flash("Validations mises à jour avec succès.")
    return redirect(url_for('strategies'))


# Suppression des références à app.models car models.py a été supprimé
# Importation de EconomicEvent depuis economic_events_fetcher.py

scheduler = BackgroundScheduler()

# Planification de la tâche pour s'exécuter toutes les heures
scheduler.add_job(fetch_economic_events, 'interval', hours=1)

scheduler.start()

# Assurez-vous que le planificateur s'arrête correctement à la fin de l'application
import atexit
atexit.register(lambda: scheduler.shutdown())

# Gestion des erreurs
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

# Point d'entrée principal
if __name__ == "__main__":
    app.run(debug=True)