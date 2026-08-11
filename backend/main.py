from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
import hashlib
import secrets
from datetime import datetime

app = FastAPI(title="Messenger Backend")

DB = "database.db"


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            stars INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL
        )
    """)

    conn.commit()
    conn.close()


init_db()


class Register(BaseModel):
    phone: str
    password: str
    name: str


class Login(BaseModel):
    phone: str
    password: str


class StarsAdd(BaseModel):
    amount: int


def password_hash(password):
    return hashlib.sha256(password.encode()).hexdigest()


def get_user(token):
    conn = db()

    row = conn.execute("""
        SELECT users.*
        FROM users
        JOIN sessions ON sessions.user_id = users.id
        WHERE sessions.token = ?
    """, (token,)).fetchone()

    conn.close()

    if not row:
        raise HTTPException(status_code=401, detail="Login required")

    return row


@app.get("/")
def home():
    return {
        "status": "ok",
        "message": "Messenger backend ishlayapti"
    }


@app.post("/register")
def register(data: Register):
    if len(data.phone) < 5:
        raise HTTPException(
            status_code=400,
            detail="Telefon raqami noto‘g‘ri"
        )

    if len(data.password) < 4:
        raise HTTPException(
            status_code=400,
            detail="Parol kamida 4 belgidan iborat bo‘lsin"
        )

    conn = db()

    exists = conn.execute(
        "SELECT id FROM users WHERE phone = ?",
        (data.phone,)
    ).fetchone()

    if exists:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="Bu raqam allaqachon ro‘yxatdan o‘tgan"
        )

    conn.execute("""
        INSERT INTO users
        (phone, password, name, stars, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        data.phone,
        password_hash(data.password),
        data.name,
        0,
        datetime.utcnow().isoformat()
    ))

    conn.commit()

    user = conn.execute(
        "SELECT id, phone, name, stars FROM users WHERE phone = ?",
        (data.phone,)
    ).fetchone()

    token = secrets.token_urlsafe(32)

    conn.execute(
        "INSERT INTO sessions(token, user_id) VALUES (?, ?)",
        (token, user["id"])
    )

    conn.commit()
    conn.close()

    return {
        "success": True,
        "token": token,
        "user": dict(user)
    }


@app.post("/login")
def login(data: Login):
    conn = db()

    user = conn.execute("""
        SELECT id, phone, name, stars
        FROM users
        WHERE phone = ? AND password = ?
    """, (
        data.phone,
        password_hash(data.password)
    )).fetchone()

    if not user:
        conn.close()
        raise HTTPException(
            status_code=401,
            detail="Telefon yoki parol noto‘g‘ri"
        )

    token = secrets.token_urlsafe(32)

    conn.execute(
        "INSERT INTO sessions(token, user_id) VALUES (?, ?)",
        (token, user["id"])
    )

    conn.commit()
    conn.close()

    return {
        "success": True,
        "token": token,
        "user": dict(user)
    }


@app.get("/me")
def me(token: str):
    user = get_user(token)

    return {
        "id": user["id"],
        "phone": user["phone"],
        "name": user["name"],
        "stars": user["stars"]
    }


@app.post("/stars/add")
def add_stars(token: str, data: StarsAdd):
    if data.amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Noto‘g‘ri miqdor"
        )

    user = get_user(token)

    conn = db()

    conn.execute(
        "UPDATE users SET stars = stars + ? WHERE id = ?",
        (data.amount, user["id"])
    )

    conn.commit()

    updated = conn.execute(
        "SELECT stars FROM users WHERE id = ?",
        (user["id"],)
    ).fetchone()

    conn.close()

    return {
        "success": True,
        "stars": updated["stars"]
}
