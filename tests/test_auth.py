# tests/test_auth.py
import json
import pytest
import jwt
import os
import datetime
from auth_refresh import app, db, create_access_token, create_refresh_token, RefreshToken

@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client
        with app.app_context():
            db.drop_all()

def test_create_tokens_and_protected(client):
    access = create_access_token(user_id=1, email="test@example.com", role="user")
    refresh = create_refresh_token(user_id=1)
    rv = client.get("/protected", headers={"Authorization": f"Bearer {access}"})
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["status"] == "ok"
    assert data["payload"]["sub"] == "1"

def test_refresh_rotation(client):
    payload = {"identifier": "Yoann", "password": "Lk@09112004"}
    rv = client.post("/login", data=json.dumps(payload), content_type="application/json")
    assert rv.status_code == 200
    data = rv.get_json()
    old_refresh = data["refresh_token"]
    rv2 = client.post("/token/refresh", data=json.dumps({"refresh_token": old_refresh}), content_type="application/json")
    assert rv2.status_code == 200
    data2 = rv2.get_json()
    assert "access_token" in data2 and "refresh_token" in data2
    rv3 = client.post("/token/refresh", data=json.dumps({"refresh_token": old_refresh}), content_type="application/json")
    assert rv3.status_code == 401

def test_logout_revokes(client):
    payload = {"identifier": "Yoann", "password": "Lk@09112004"}
    rv = client.post("/login", data=json.dumps(payload), content_type="application/json")
    data = rv.get_json()
    refresh = data["refresh_token"]
    rv2 = client.post("/logout", data=json.dumps({"refresh_token": refresh}), content_type="application/json")
    assert rv2.status_code == 200
    rv3 = client.post("/token/refresh", data=json.dumps({"refresh_token": refresh}), content_type="application/json")
    assert rv3.status_code == 401
