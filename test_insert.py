# test_insert.py
from db import ensure_db, create_user, list_users

ensure_db()
uid = create_user("Yoann", "l.yoann68@hotmail.fr")
print("nouvel id:", uid)
print("utilisateurs:", list_users())