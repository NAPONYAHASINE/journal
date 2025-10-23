import re
from datetime import datetime

# Constantes de validation
MAX_STRING_LENGTH = 1000  # Limite générale pour les chaînes
MAX_TEXT_LENGTH = 50000   # Limite pour les textes longs (descriptions, contenus)
MIN_STRING_LENGTH = 1     # Longueur minimum par défaut

# Try to use the robust email_validator package when available
try:
    from email_validator import validate_email, EmailNotValidError
    _HAS_EMAIL_VALIDATOR = True
except Exception:
    _HAS_EMAIL_VALIDATOR = False

# Fallback regex (stricter than a naive one)
EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def is_valid_email(email: str) -> bool:
    if not email or not isinstance(email, str):
        return False
    email = email.strip()
    # Use email_validator if available
    if _HAS_EMAIL_VALIDATOR:
        try:
            # Skip network/DNS deliverability checks to keep validation local and
            # deterministic (e.g. example.com has no MX and would fail).
            validate_email(email, check_deliverability=False)
            return True
        except EmailNotValidError:
            # If the robust validator rejects it, fall back to the regex below.
            pass

    # Basic heuristic checks with regex fallback
    if '..' in email:
        return False
    if not EMAIL_REGEX.match(email):
        return False
    return True


def sanitize_string(value: str, min_length: int = 0, max_length: int = MAX_STRING_LENGTH, 
                  allow_empty: bool = True) -> tuple[bool, str]:
    """
    Nettoie et valide une chaîne de caractères.
    
    Args:
        value: La chaîne à nettoyer
        min_length: Longueur minimum (0 par défaut)
        max_length: Longueur maximum (MAX_STRING_LENGTH par défaut)
        allow_empty: Si True, permet les chaînes vides
        
    Returns:
        tuple[bool, str]: (True, chaîne_nettoyée) si valide,
                         (False, message_erreur) si invalide
    """
    if value is None:
        return (True, '') if allow_empty else (False, "La valeur ne peut pas être nulle")
    
    cleaned = str(value).strip()
    
    if not cleaned and not allow_empty:
        return False, "Ce champ ne peut pas être vide"
        
    if len(cleaned) < min_length:
        return False, f"La longueur minimum est de {min_length} caractères"
        
    if len(cleaned) > max_length:
        return False, f"La longueur maximum est de {max_length} caractères"
        
    return True, cleaned


def is_valid_password(password: str) -> tuple[bool, str]:
    if not password or len(password) < 8:
        return False, "Le mot de passe doit contenir au moins 8 caractères"
    if not re.search(r"[A-Z]", password):
        return False, "Le mot de passe doit contenir au moins une majuscule"
    if not re.search(r"[a-z]", password):
        return False, "Le mot de passe doit contenir au moins une minuscule"
    if not re.search(r"\d", password):
        return False, "Le mot de passe doit contenir au moins un chiffre"
    return True, "OK"


def parse_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(str(value).replace(',', '.'))
    except Exception:
        return default


def parse_datetime(date_str: str, time_str: str) -> datetime | None:
    try:
        if not date_str or not time_str:
            return None
        return datetime.strptime(date_str + ' ' + time_str, '%Y-%m-%d %H:%M')
    except Exception:
        return None
