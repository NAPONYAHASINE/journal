import sqlite3

# Connexion à la base de données
conn = sqlite3.connect('instance/trading_journal.db')
cursor = conn.cursor()

# Vérifiez les données dans la table academy_posts
try:
    cursor.execute("SELECT * FROM academy_posts LIMIT 5;")
    rows = cursor.fetchall()
    if rows:
        print("Données trouvées dans academy_posts :")
        for row in rows:
            print(row)
    else:
        print("Aucune donnée trouvée dans academy_posts.")
except sqlite3.Error as e:
    print(f"Erreur SQLite : {e}")
finally:
    conn.close()