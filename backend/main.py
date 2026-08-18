from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
import hashlib
import secrets
from datetime import datetime

app = FastAPI(title="Superme Messenger Backend")
DB = "database.db"


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        name TEXT NOT NULL,
        stars INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    )""")
    conn.execute("CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id INTEGER NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS gifts(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,price INTEGER NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS referrals(id INTEGER PRIMARY KEY AUTOINCREMENT,referrer_id INTEGER NOT NULL,referred_id INTEGER NOT NULL)")
    conn.commit(); conn.close()

init_db()

class Register(BaseModel):
    phone: str
    password: str
    name: str
    referral: str = ""

class Login(BaseModel):
    phone: str
    password: str

class GiftBuy(BaseModel):
    giftId: int


def password_hash(password: str):
    return hashlib.sha256(password.encode()).hexdigest()


def get_user(token: str):
    conn = db()
    row = conn.execute("SELECT users.* FROM users JOIN sessions ON sessions.user_id=users.id WHERE sessions.token=?", (token,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=401, detail="Login required")
    return row

@app.get("/")
def home():
    return {"status": "ok", "message": "Superme backend ishlayapti"}

@app.post("/register")
def register(data: Register):
    phone = data.phone.strip(); name = data.name.strip()
    if len(phone) < 5: raise HTTPException(400, "Telefon raqami noto'g'ri")
    if len(data.password) < 4: raise HTTPException(400, "Parol kamida 4 belgidan iborat bo'lsin")
    if not name: raise HTTPException(400, "Ismni kiriting")
    conn = db()
    if conn.execute("SELECT id FROM users WHERE phone=?", (phone,)).fetchone():
        conn.close(); raise HTTPException(400, "Bu raqam allaqachon ro'yxatdan o'tgan")
    conn.execute("INSERT INTO users(phone,password,name,stars,created_at) VALUES(?,?,?,?,?)", (phone, password_hash(data.password), name, 0, datetime.utcnow().isoformat()))
    user = conn.execute("SELECT id,phone,name,stars FROM users WHERE phone=?", (phone,)).fetchone()
    if data.referral.strip():
        try:
            referrer_id = int(data.referral.strip())
            if referrer_id != user["id"] and conn.execute("SELECT id FROM users WHERE id=?", (referrer_id,)).fetchone():
                conn.execute("INSERT INTO referrals(referrer_id,referred_id) VALUES(?,?)", (referrer_id, user["id"]))
                conn.execute("UPDATE users SET stars=stars+5 WHERE id=?", (referrer_id,))
        except ValueError: pass
    token = secrets.token_urlsafe(32)
    conn.execute("INSERT INTO sessions(token,user_id) VALUES(?,?)", (token, user["id"]))
    conn.commit(); conn.close()
    return {"success": True, "token": token, "user": dict(user)}

@app.post("/login")
def login(data: Login):
    conn = db()
    user = conn.execute("SELECT id,phone,name,stars FROM users WHERE phone=? AND password=?", (data.phone.strip(), password_hash(data.password))).fetchone()
    if not user:
        conn.close(); raise HTTPException(401, "Telefon yoki parol noto'g'ri")
    token = secrets.token_urlsafe(32)
    conn.execute("INSERT INTO sessions(token,user_id) VALUES(?,?)", (token, user["id"]))
    conn.commit(); conn.close()
    return {"success": True, "token": token, "user": dict(user)}

@app.get("/me")
def me(token: str):
    user = get_user(token)
    return {"id": user["id"], "phone": user["phone"], "name": user["name"], "stars": user["stars"]}

@app.get("/users/{user_id}/balance")
def balance(user_id: int):
    conn = db(); user = conn.execute("SELECT stars FROM users WHERE id=?", (user_id,)).fetchone(); conn.close()
    if not user: raise HTTPException(404, "Foydalanuvchi topilmadi")
    return {"ok": True, "stars": user["stars"]}

@app.post("/stars/add")
def disabled_stars_add():
    raise HTTPException(403, "Stars faqat tasdiqlangan Superme to'lovi orqali qo'shiladi")

@app.get("/gifts")
def gifts():
    conn = db(); rows = conn.execute("SELECT id,name,price FROM gifts ORDER BY id").fetchall(); conn.close()
    return {"ok": True, "gifts": [dict(r) for r in rows]}

@app.post("/gift/buy")
def buy_gift(token: str, data: GiftBuy):
    user = get_user(token); conn = db()
    gift = conn.execute("SELECT * FROM gifts WHERE id=?", (data.giftId,)).fetchone()
    if not gift:
        conn.close(); raise HTTPException(404, "Gift topilmadi")
    if user["stars"] < gift["price"]:
        conn.close(); raise HTTPException(400, "Stars yetarli emas")
    conn.execute("UPDATE users SET stars=stars-? WHERE id=?", (gift["price"], user["id"]))
    try:
        conn.execute("INSERT INTO purchased_gifts(user_id,gift_id,gift_name,price_stars,purchased_at) VALUES(?,?,?,?,?)", (user["id"], gift["id"], gift["name"], gift["price"], datetime.utcnow().isoformat()))
        conn.execute("INSERT INTO superme_transactions(user_id,kind,stars_delta,reference,created_at) VALUES(?,?,?,?,?)", (user["id"], "gift_purchase", -gift["price"], str(gift["id"]), datetime.utcnow().isoformat()))
    except sqlite3.OperationalError: pass
    conn.commit(); conn.close()
    return {"ok": True, "success": True, "message": "Gift sotib olindi"}

@app.get("/users/{user_id}/referral")
def referral(user_id: int):
    conn = db()
    if not conn.execute("SELECT id FROM users WHERE id=?", (user_id,)).fetchone():
        conn.close(); raise HTTPException(404, "Foydalanuvchi topilmadi")
    count = conn.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (user_id,)).fetchone()[0]
    conn.close()
    return {"ok": True, "referrals": count, "earned_stars": count * 5}

@app.get("/health")
def health():
    return {"ok": True, "status": "online"}

try:
    from .superme_api import router as superme_router
except ImportError:
    from superme_api import router as superme_router
app.include_router(superme_router)
