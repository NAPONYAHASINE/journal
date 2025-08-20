import requests
from datetime import datetime
import os
from main import EconomicEvent, db

# Correction du chemin de la base de données pour utiliser un chemin absolu
basedir = os.path.abspath(os.path.dirname(__file__))

def fetch_economic_events():
    """Récupère les annonces économiques depuis une API externe et les enregistre dans la base de données."""
    API_URL = "https://api.tradingeconomics.com/calendar"  # URL réelle de l'API Trading Economics
    API_KEY = "votre_cle_api"  # Remplacez par votre clé API valide

    try:
        response = requests.get(API_URL, headers={"Authorization": f"Bearer {API_KEY}"})
        response.raise_for_status()
        events = response.json()

        for event in events:
            existing_event = EconomicEvent.query.filter_by(title=event['title'], date=event['date']).first()
            if not existing_event:
                new_event = EconomicEvent(
                    date=event['date'],
                    title=event['title'],
                    impact=event['impact'],
                    currency=event['currency'],
                    description=event.get('description', '')
                )
                db.session.add(new_event)

        db.session.commit()
        print("Mise à jour des annonces économiques réussie.")
    except Exception as e:
        print(f"Erreur lors de la récupération des annonces économiques : {e}")

if __name__ == "__main__":
    fetch_economic_events()