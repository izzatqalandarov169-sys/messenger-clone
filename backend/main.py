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
            referral_code TEXT UNIQUE,
            referred_by INTEGER,
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
        CREATE TABLE IF NOT EXISTS gift_purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            gift_id INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # Boshlang‘ich giftlar
    count = conn.execute(
        "SELECT COUNT(*) AS count FROM gifts"
    ).fetchone()["count"]

    if count == 0:
        gifts = [
            ("❤️ Yurak", 15),
            ("🌹 Atirgul", 25),
            ("🎁 Sovg‘a", 50),
            ("💎 Olmos", 100),
        ]

        conn.executemany(
            "INSERT INTO gifts(name, price) VALUES (?, ?)",
            gifts
        )

    conn.commit()
    conn.close()


init_db()


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


def password_hash(password):
    return hashlib.sha256(
        password.encode()
    ).hexdigest()


def make_referral_code():
    return secrets.token_urlsafe(6)


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


@app.get("/")
def home():
    return {
        "status": "ok",
        "message": "Messenger backend ishlayapti"
    }


# ================= REGISTER =================

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

    referral_code = make_referral_code()
    referred_by = None

    if data.referral.strip():
        ref_user = conn.execute(
            """
            SELECT id
            FROM users
            WHERE referral_code = ?
            """,
            (data.referral.strip(),)
        ).fetchone()

        if ref_user:
            referred_by = ref_user["id"]

    conn.execute("""
        INSERT INTO users
        (
            phone,
            password,
            name,
            stars,
            referral_code,
            referred_by,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        data.phone,
        password_hash(data.password),
        data.name,
        0,
        referral_code,
        referred_by,
        datetime.utcnow().isoformat()
    ))

    conn.commit()

    user = conn.execute(
        """
        SELECT
            id,
            phone,
            name,
            stars,
            referral_code
        FROM users
        WHERE phone = ?
        """,
        (data.phone,)
    ).fetchone()

    token = secrets.token_urlsafe(32)

    conn.execute(
        """
        INSERT INTO sessions(token, user_id)
        VALUES (?, ?)
        """,
        (token, user["id"])
    )

    conn.commit()
    conn.close()

    return {
        "success": True,
        "token": token,
        "user": {
            "id": user["id"],
            "phone": user["phone"],
            "name": user["name"],
            "stars": user["stars"],
            "referral_code": user["referral_code"],
            "isOwner": False
        }
    }


# ================= LOGIN =================

@app.post("/login")
def login(data: Login):
    conn = db()

    user = conn.execute("""
        SELECT
            id,
            phone,
            name,
            stars,
            referral_code
        FROM users
        WHERE phone = ?
        AND password = ?
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
        """
        INSERT INTO sessions(token, user_id)
        VALUES (?, ?)
        """,
        (token, user["id"])
    )

    conn.commit()
    conn.close()

    return {
        "success": True,
        "token": token,
        "user": {
            "id": user["id"],
            "phone": user["phone"],
            "name": user["name"],
            "stars": user["stars"],
            "referral_code": user["referral_code"],
            "isOwner": False
        }
    }


# ================= ME =================

@app.get("/me")
def me(token: str):
    user = get_user(token)

    return {
        "id": user["id"],
        "phone": user["phone"],
        "name": user["name"],
        "stars": user["stars"],
        "referral_code": user["referral_code"]
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
            detail="Noto‘g‘ri miqdor"
        )

    user = get_user(token)

    conn = db()

    conn.execute(
        """
        UPDATE users
        SET stars = stars + ?
        WHERE id = ?
        """,
        (data.amount, user["id"])
    )

    conn.commit()

    updated = conn.execute(
        """
        SELECT stars
        FROM users
        WHERE id = ?
        """,
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

    rows = conn.execute(
        """
        SELECT id, name, price
        FROM gifts
        ORDER BY id ASC
        """
    ).fetchall()

    conn.close()

    return {
        "success": True,
        "gifts": [dict(row) for row in rows]
    }


# ================= BUY GIFT =================

@app.post("/gift/buy")
def buy_gift(data: GiftBuy):
    conn = db()

    user = conn.execute(
        """
        SELECT id, stars
        FROM users
        WHERE id = ?
        """,
        (data.userId,)
    ).fetchone()

    if not user:
        conn.close()

        raise HTTPException(
            status_code=404,
            detail="Foydalanuvchi topilmadi"
        )

    gift = conn.execute(
        """
        SELECT id, name, price
        FROM gifts
        WHERE id = ?
        """,
        (data.giftId,)
    ).fetchone()

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

    conn.execute(
        """
        UPDATE users
        SET stars = stars - ?
        WHERE id = ?
        """,
        (
            gift["price"],
            data.userId
        )
    )

    conn.execute(
        """
        INSERT INTO gift_purchases
        (
            user_id,
            gift_id,
            created_at
        )
        VALUES (?, ?, ?)
        """,
        (
            data.userId,
            data.giftId,
            datetime.utcnow().isoformat()
        )
    )

    conn.commit()

    updated = conn.execute(
        """
        SELECT stars
        FROM users
        WHERE id = ?
        """,
        (data.userId,)
    ).fetchone()

    conn.close()

    return {
        "success": True,
        "message": f"{gift['name']} sotib olindi",
        "stars": updated["stars"]
    }


# ================= BALANCE =================

@app.get("/users/{user_id}/balance")
def balance(user_id: int):
    conn = db()

    user = conn.execute(
        """
        SELECT id, stars
        FROM users
        WHERE id = ?
        """,
        (user_id,)
    ).fetchone()

    conn.close()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Foydalanuvchi topilmadi"
        )

    return {
        "success": True,
        "stars": user["stars"]
    }


# ================= REFERRAL =================

@app.get("/users/{user_id}/referral")
def referral(user_id: int):
    conn = db()

    user = conn.execute(
        """
        SELECT
            id,
            referral_code
        FROM users
        WHERE id = ?
        """,
        (user_id,)
    ).fetchone()

    if not user:
        conn.close()

        raise HTTPException(
            status_code=404,
            detail="Foydalanuvchi topilmadi"
        )

    count = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM users
        WHERE referred_by = ?
        """,
        (user_id,)
    ).fetchone()["count"]

    conn.close()

    return {
        "success": True,
        "referral_link":
            f"messenger://ref/{user['referral_code']}",
        "referrals": count,
        "earned_stars": 0
    }
