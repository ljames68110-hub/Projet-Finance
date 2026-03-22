# admin_routes.py
from flask import Blueprint, request, jsonify, Response
from db import get_conn
import re
from datetime import datetime
import threading
import os
import smtplib
from email.message import EmailMessage

# Optional SMTP config import (put SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_USE_TLS in config.py)
import config

admin_bp = Blueprint("admin", __name__)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_admin(user_id: int) -> bool:
    """
    Vérifie en base si l'utilisateur a le rôle 'admin'.
    Retourne True si admin, False sinon.
    """
    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT role FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        return bool(row and row[0] == "admin")
    except Exception:
        return False
    finally:
        try:
            if cur:
                cur.close()
            if conn:
                conn.close()
        except Exception:
            pass


def _send_notification_email(old_email: str, new_email: str, changed_by: int):
    """
    Envoi d'emails de notification à l'ancienne et à la nouvelle adresse.
    Exécuté dans un thread séparé pour ne pas bloquer la requête HTTP.

    Lecture de la configuration SMTP (priorité : variables d'environnement, puis config.py) :
      - SMTP_HOST (ex: 127.0.0.1)
      - SMTP_PORT (ex: 1025, 1026, 25, 587)
      - SMTP_USER (optionnel)
      - SMTP_PASS (optionnel)
      - SMTP_USE_TLS (optionnel, True/False)
    """
    try:
        # Lecture config : priorité aux variables d'environnement
        smtp_host = os.getenv("SMTP_HOST") or getattr(config, "SMTP_HOST", None) or "127.0.0.1"
        smtp_port_raw = os.getenv("SMTP_PORT") or getattr(config, "SMTP_PORT", None) or "1025"
        try:
            smtp_port = int(smtp_port_raw)
        except Exception:
            smtp_port = 1025

        smtp_user = os.getenv("SMTP_USER") or getattr(config, "SMTP_USER", None) or ""
        smtp_pass = os.getenv("SMTP_PASS") or getattr(config, "SMTP_PASS", None) or ""
        smtp_use_tls_raw = os.getenv("SMTP_USE_TLS")
        if smtp_use_tls_raw is None:
            smtp_use_tls = bool(getattr(config, "SMTP_USE_TLS", False))
        else:
            smtp_use_tls = str(smtp_use_tls_raw).lower() in ("1", "true", "yes")

        # DEBUG prints temporaires (supprimer après vérification)
        print("DEBUG SMTP CONFIG -> host:", smtp_host, "port:", smtp_port, "user:", bool(smtp_user), "use_tls:", smtp_use_tls)

        # Si on n'a pas d'hôte/port, on ne tente pas l'envoi
        if not smtp_host or not smtp_port:
            print("SMTP non configuré (host/port manquant), notification non envoyée.")
            return

        msg_old = EmailMessage()
        msg_old["Subject"] = "Votre adresse email a été modifiée"
        msg_old["From"] = smtp_user or "no-reply@example.com"
        msg_old["To"] = old_email
        msg_old.set_content(
            f"L'adresse de votre compte a été changée vers {new_email} par l'administrateur (id {changed_by})."
        )

        msg_new = EmailMessage()
        msg_new["Subject"] = "Votre nouvelle adresse a été enregistrée"
        msg_new["From"] = smtp_user or "no-reply@example.com"
        msg_new["To"] = new_email
        msg_new.set_content(
            "Votre adresse a été enregistrée pour le compte utilisateur. Si ce n'est pas vous, contactez le support."
        )

        # Connexion SMTP : supporte serveur sans auth (utile pour aiosmtpd local)
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as s:
            s.set_debuglevel(1)  # utile pour debug local
            # STARTTLS si demandé
            if smtp_use_tls:
                try:
                    s.starttls()
                except Exception as e:
                    print("DEBUG STARTTLS failed:", e)
            # Auth si on a des identifiants
            if smtp_user and smtp_pass:
                try:
                    s.login(smtp_user, smtp_pass)
                except Exception as e:
                    print("DEBUG SMTP login failed:", e)
            # Envoi des messages
            s.send_message(msg_old)
            s.send_message(msg_new)
    except Exception as e:
        # Ne pas interrompre le flux principal ; logguer l'erreur pour debug
        print("Erreur envoi email:", e)


@admin_bp.route("/admin/users/<int:user_id>/email", methods=["PUT"])
def admin_update_email(user_id):
    """
    Endpoint pour que l'administrateur change l'email d'un utilisateur.
    - Vérifie que la requête provient d'un admin (X-User-Id header).
    - Valide le format de l'email et l'unicité.
    - Met à jour users.email (et email_verified si la colonne existe).
    - Insère une ligne dans email_change_audit.
    - Lance l'envoi de notifications (thread non bloquant).
    - Renvoie l'identifiant utilisateur (entier) en texte brut.
    """
    auth_user = request.headers.get("X-User-Id")
    if not auth_user:
        return jsonify({"error": "forbidden"}), 403

    try:
        auth_user_id = int(auth_user)
    except Exception:
        return jsonify({"error": "forbidden"}), 403

    if not is_admin(auth_user_id):
        return jsonify({"error": "forbidden"}), 403

    data = request.get_json() or {}
    new_email = (data.get("email") or "").strip().lower()
    if not new_email or not EMAIL_RE.match(new_email):
        return jsonify({"error": "invalid_email"}), 400

    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()

        # Vérifier unicité
        cur.execute("SELECT id FROM users WHERE email = ?", (new_email,))
        row = cur.fetchone()
        if row and row[0] != user_id:
            return jsonify({"error": "email_already_in_use"}), 409

        # Récupérer ancien email
        cur.execute("SELECT email FROM users WHERE id = ?", (user_id,))
        old = cur.fetchone()
        if not old:
            return jsonify({"error": "user_not_found"}), 404
        old_email = old[0]

        # Mettre à jour l'email ; si email_verified existe, le remettre à 0
        try:
            cur.execute("UPDATE users SET email = ?, email_verified = 0 WHERE id = ?", (new_email, user_id))
        except Exception:
            # Si la colonne email_verified n'existe pas, on met juste à jour l'email
            cur.execute("UPDATE users SET email = ? WHERE id = ?", (new_email, user_id))

        conn.commit()

        # Journaliser l'opération
        cur.execute(
            "INSERT INTO email_change_audit (user_id, old_email, new_email, changed_by, changed_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, old_email, new_email, auth_user_id, datetime.utcnow().isoformat()),
        )
        conn.commit()

        # Envoi des notifications en arrière-plan (ne bloque pas la réponse)
        try:
            t = threading.Thread(target=_send_notification_email, args=(old_email, new_email, auth_user_id), daemon=True)
            t.start()
        except Exception as e:
            print("Impossible de lancer le thread d'envoi d'email:", e)

        # Renvoie l'entier (user_id) en texte brut comme demandé
        return Response(str(user_id), status=200, mimetype="text/plain")

    finally:
        try:
            if cur:
                cur.close()
            if conn:
                conn.close()
        except Exception:
            pass