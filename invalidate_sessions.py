# invalidate_sessions.py
from db import get_conn
import sys

if len(sys.argv) < 2:
    print("Usage: python invalidate_sessions.py <user_id>")
    sys.exit(1)

user_id = int(sys.argv[1])
conn = get_conn()
cur = conn.cursor()
# Exemple : si tu as une table sessions avec colonne valid ou revoked
try:
    cur.execute("UPDATE sessions SET valid = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    print("Sessions invalidées pour user_id =", user_id)
except Exception as e:
    print("Erreur:", e)
finally:
    conn.close()
