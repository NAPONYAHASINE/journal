import logging
logging.basicConfig(level=logging.DEBUG)
logging.debug("Routes enregistrées dans l'application.")

from flask import render_template, url_for, request, redirect, flash, session, send_from_directory
from app import app
import sqlite3
import os
from datetime import datetime
from werkzeug.utils import secure_filename
from app import db
from app.models import Module

# Ajoutez cette fonction si elle n'est pas définie ailleurs
def allowed_file(filename):
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'mp4', 'mp3', 'wav'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions
