from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
import hashlib
import secrets
from datetime import datetime

app = FastAPI(title="Messenger Backend")

DB = "database.db"


# ================= DATABASE =================

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

    conn.execute("""
        CREATE TABLE IF NOT EXISTS gifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price INTEGER NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER NOT NULL,
            referred_id INTEGER NOT NULL
        )
    """)

    # Boshlang'ich giftlar
    count = conn.execute(
        "SELECT COUNT(*) FROM gifts"
    ).fetchone()[0]

    if count == 0:
        conn.execute(
            "INSERT INTO gifts (name, price) VALUES (?, ?)",
            ("Rose", 10)
        )
        conn.execute(
            "INSERT INTO gifts (name, price) VALUES (?, ?)",
            ("Heart", 25)
        )
        conn.execute(
            "INSERT INTO gifts (name, price) VALUES (?, ?)",
            ("Star Gift", 50)
        )

    conn.commit()
    conn.close()


init_db()


# ================= MODELS =================

class Register(BaseModel):
    phone: str
    password: str
    name: str
    referral: str = ""


class Login(BaseModel):
    phone: str
    password: str


class StarsAdd(BaseModel):
    amount: int


class GiftBuy(BaseModel):
    userId: int
    giftId: int


# ================= HELPERS =================

def password_hash(password):
    return hashlib.sha256(
        password.encode()
    ).hexdigest()


def get_user(token):
    conn = db()

    row = conn.execute("""
        SELECT users.*
        FROM users
        JOIN sessions
        ON sessions.user_id = users.id
        WHERE sessions.token = ?
    """, (token,)).fetchone()

    conn.close()

    if not row:
        raise HTTPException(
            status_code=401,
            detail="Login required"
        )

    return row


# ================= HOME =================

@app.get("/")
def home():
    return {
        "status": "ok",
        "message": "Messenger backend ishlayapti"
    }


# ================= REGISTER =================

@app.post("/register")
def register(data: Register):

    if len(data.phone.strip()) < 5:
        raise HTTPException(
            status_code=400,
            detail="Telefon raqami noto'g'ri"
        )

    if len(data.password) < 4:
        raise HTTPException(
            status_code=400,
            detail="Parol kamida 4 belgidan iborat bo'lsin"
        )

    if not data.name.strip():
        raise HTTPException(
            status_code=400,
            detail="Ismni kiriting"
        )

    conn = db()

    exists = conn.execute(
        "SELECT id FROM users WHERE phone = ?",
        (data.phone.strip(),)
    ).fetchone()

    if exists:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="Bu raqam allaqachon ro'yxatdan o'tgan"
        )

    conn.execute("""
        INSERT INTO users
        (phone, password, name, stars, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        data.phone.strip(),
        password_hash(data.password),
        data.name.strip(),
        0,
        datetime.utcnow().isoformat()
    ))

    conn.commit()

    user = conn.execute("""
        SELECT id, phone, name, stars
        FROM users
        WHERE phone = ?
    """, (data.phone.strip(),)).fetchone()

    # Referral
    if data.referral.strip():
        try:
            referrer_id = int(data.referral.strip())

            if referrer_id != user["id"]:
                referrer = conn.execute(
                    "SELECT id FROM users WHERE id = ?",
                    (referrer_id,)
                ).fetchone()

                if referrer:
                    conn.execute("""
                        INSERT INTO referrals
                        (referrer_id, referred_id)
                        VALUES (?, ?)
                    """, (
                        referrer_id,
                        user["id"]
                    ))

                    # Referral uchun 5 Stars
                    conn.execute("""
                        UPDATE users
                        SET stars = stars + 5
                        WHERE id = ?
                    """, (referrer_id,))

        except ValueError:
            pass

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


# ================= LOGIN =================

@app.post("/login")
def login(data: Login):

    conn = db()

    user = conn.execute("""
        SELECT id, phone, name, stars
        FROM users
        WHERE phone = ?
        AND password = ?
    """, (
        data.phone.strip(),
        password_hash(data.password)
    )).fetchone()

    if not user:
        conn.close()
        raise HTTPException(
            status_code=401,
            detail="Telefon yoki parol noto'g'ri"
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


# ================= ME =================

@app.get("/me")
def me(token: str):

    user = get_user(token)

    return {
        "id": user["id"],
        "phone": user["phone"],
        "name": user["name"],
        "stars": user["stars"]
    }


# ================= BALANCE =================

@app.get("/users/{user_id}/balance")
def balance(user_id: int):

    conn = db()

    user = conn.execute(
        "SELECT stars FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    conn.close()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Foydalanuvchi topilmadi"
        )

    return {
        "ok": True,
        "stars": user["stars"]
    }


# ================= STARS ADD =================

@app.post("/stars/add")
def add_stars(
    token: str,
    data: StarsAdd
):

    if data.amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Noto'g'ri miqdor"
        )

    user = get_user(token)

    conn = db()

    conn.execute("""
        UPDATE users
        SET stars = stars + ?
        WHERE id = ?
    """, (
        data.amount,
        user["id"]
    ))

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


# ================= GIFTS =================

@app.get("/gifts")
def gifts():

    conn = db()

    rows = conn.execute("""
        SELECT id, name, price
        FROM gifts
        ORDER BY id
    """).fetchall()

    conn.close()

    return {
        "ok": True,
        "gifts": [dict(row) for row in rows]
    }


# ================= BUY GIFT =================

@app.post("/gift/buy")
def buy_gift(data: GiftBuy):

    conn = db()

    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (data.userId,)
    ).fetchone()

    gift = conn.execute(
        "SELECT * FROM gifts WHERE id = ?",
        (data.giftId,)
    ).fetchone()

    if not user:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Foydalanuvchi topilmadi"
        )

    if not gift:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Gift topilmadi"
        )

    if user["stars"] < gift["price"]:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="Stars yetarli emas"
        )

    conn.execute("""
        UPDATE users
        SET stars = stars - ?
        WHERE id = ?
    """, (
        gift["price"],
        data.userId
    ))

    conn.commit()
    conn.close()

    return {
        "ok": True,
        "success": True,
        "message": "Gift sotib olindi"
    }


# ================= REFERRAL =================

@app.get("/users/{user_id}/referral")
def referral(user_id: int):

    conn = db()

    user = conn.execute(
        "SELECT id FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    if not user:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Foydalanuvchi topilmadi"
        )

    count = conn.execute("""
        SELECT COUNT(*)
        FROM referrals
        WHERE referrer_id = ?
    """, (user_id,)).fetchone()[0]

    # Referral mukofoti:
    # har bir taklif qilingan foydalanuvchi uchun 5 Stars
    earned = count * 5

    conn.close()

    return {
        "ok": True,
        "referral_link":
            f"https://t.me/your_bot?start={user_id}",
        "referrals": count,
        "earned_stars": earned
    }


# ================= HEALTH =================

@app.get("/health")
def health():
    return {
        "ok": True,
        "status": "online"
        }
