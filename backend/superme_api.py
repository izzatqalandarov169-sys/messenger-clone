from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sqlite3
import os
import secrets
from datetime import datetime, timezone

router = APIRouter(prefix="/superme", tags=["superme"])
DB = "database.db"

STARS_PACKAGES = [
    {"id": "stars_100", "stars": 100, "price_uzs": 10000},
    {"id": "stars_150", "stars": 150, "price_uzs": 15000},
    {"id": "stars_250", "stars": 250, "price_uzs": 25000},
    {"id": "stars_350", "stars": 350, "price_uzs": 35000},
    {"id": "stars_500", "stars": 500, "price_uzs": 40000},
    {"id": "stars_750", "stars": 750, "price_uzs": 50000},
    {"id": "stars_1000", "stars": 1000, "price_uzs": 30000},
    {"id": "stars_1500", "stars": 1500, "price_uzs": 60000},
    {"id": "stars_2500", "stars": 2500, "price_uzs": 90000},
    {"id": "stars_5000", "stars": 5000, "price_uzs": 50000},
    {"id": "stars_10000", "stars": 10000, "price_uzs": 120000},
]

SUBSCRIPTIONS = {
    "premium_month": {"name": "Premium", "period": "month", "price_uzs": 15000},
    "premium_year": {"name": "Premium", "period": "year", "price_uzs": 45000},
    "business_month": {"name": "Business", "period": "month", "price_uzs": 15000},
    "business_year": {"name": "Business", "period": "year", "price_uzs": 45000},
}

class PaymentOrder(BaseModel):
    product_type: str
    product_id: str

class VerifyPayment(BaseModel):
    order_id: str
    payment_reference: str = ""


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def now():
    return datetime.now(timezone.utc).isoformat()


def current_user(token: str):
    conn = db()
    row = conn.execute(
        "SELECT users.* FROM users JOIN sessions ON sessions.user_id=users.id WHERE sessions.token=?",
        (token,),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=401, detail="Login required")
    return row


def migrate():
    conn = db()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
    for name, sql in [
        ("premium_until", "ALTER TABLE users ADD COLUMN premium_until TEXT"),
        ("business_until", "ALTER TABLE users ADD COLUMN business_until TEXT"),
        ("last_owner_grant", "ALTER TABLE users ADD COLUMN last_owner_grant TEXT"),
    ]:
        if name not in cols:
            conn.execute(sql)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS superme_orders (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            product_type TEXT NOT NULL,
            product_id TEXT NOT NULL,
            amount_uzs INTEGER NOT NULL,
            stars INTEGER DEFAULT 0,
            status TEXT NOT NULL,
            payment_reference TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            verified_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS purchased_gifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            gift_id INTEGER NOT NULL,
            gift_name TEXT NOT NULL,
            price_stars INTEGER NOT NULL,
            purchased_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS superme_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            kind TEXT NOT NULL,
            amount_uzs INTEGER DEFAULT 0,
            stars_delta INTEGER DEFAULT 0,
            reference TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

migrate()


def owner_grant(conn, user):
    owner_phone = os.getenv("SUPERME_OWNER_PHONE", "").strip()
    if not owner_phone or user["phone"] != owner_phone:
        return
    last = user["last_owner_grant"]
    if last:
        try:
            previous = datetime.fromisoformat(last)
            if (datetime.now(timezone.utc) - previous).total_seconds() < 30 * 24 * 3600:
                return
        except ValueError:
            pass
    # Initial grant is also handled by this one-time/monthly mechanism.
    grant = 500_000_000
    conn.execute("UPDATE users SET stars=stars+?, last_owner_grant=? WHERE id=?", (grant, now(), user["id"]))
    conn.execute(
        "INSERT INTO superme_transactions(user_id,kind,stars_delta,reference,created_at) VALUES(?,?,?,?,?)",
        (user["id"], "owner_monthly_grant", grant, "SUPERME_OWNER_GRANT", now()),
    )
    conn.commit()


@router.get("/config")
def config():
    return {"stars_packages": STARS_PACKAGES, "subscriptions": SUBSCRIPTIONS}


@router.get("/balance")
def superme_balance(token: str):
    conn = db()
    user = current_user(token)
    owner_grant(conn, user)
    row = conn.execute("SELECT stars,premium_until,business_until FROM users WHERE id=?", (user["id"],)).fetchone()
    conn.close()
    return {"ok": True, "stars": row["stars"], "premium_until": row["premium_until"], "business_until": row["business_until"]}


@router.post("/orders")
def create_order(token: str, data: PaymentOrder):
    user = current_user(token)
    amount = None
    stars = 0
    if data.product_type == "stars":
        match = next((p for p in STARS_PACKAGES if p["id"] == data.product_id), None)
        if not match:
            raise HTTPException(status_code=400, detail="Stars paketi topilmadi")
        amount, stars = match["price_uzs"], match["stars"]
    elif data.product_type in ("premium", "business"):
        match = SUBSCRIPTIONS.get(data.product_id)
        if not match:
            raise HTTPException(status_code=400, detail="Obuna topilmadi")
        amount = match["price_uzs"]
    else:
        raise HTTPException(status_code=400, detail="Noma'lum mahsulot")

    order_id = secrets.token_urlsafe(18)
    conn = db()
    conn.execute(
        "INSERT INTO superme_orders(id,user_id,product_type,product_id,amount_uzs,stars,status,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (order_id, user["id"], data.product_type, data.product_id, amount, stars, "pending", now()),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "order_id": order_id, "status": "pending", "amount_uzs": amount, "stars": stars}


@router.post("/orders/verify")
def verify_order(data: VerifyPayment, admin_token: str):
    expected = os.getenv("SUPERME_ADMIN_TOKEN", "")
    if not expected or not secrets.compare_digest(admin_token, expected):
        raise HTTPException(status_code=403, detail="Admin authorization required")
    conn = db()
    order = conn.execute("SELECT * FROM superme_orders WHERE id=?", (data.order_id,)).fetchone()
    if not order:
        conn.close()
        raise HTTPException(status_code=404, detail="Order topilmadi")
    if order["status"] != "pending":
        conn.close()
        return {"ok": True, "status": order["status"]}

    conn.execute("UPDATE superme_orders SET status='paid', payment_reference=?, verified_at=? WHERE id=?", (data.payment_reference, now(), data.order_id))
    if order["product_type"] == "stars":
        conn.execute("UPDATE users SET stars=stars+? WHERE id=?", (order["stars"], order["user_id"]))
        conn.execute("INSERT INTO superme_transactions(user_id,kind,amount_uzs,stars_delta,reference,created_at) VALUES(?,?,?,?,?,?)", (order["user_id"], "stars_purchase", order["amount_uzs"], order["stars"], data.order_id, now()))
    else:
        days = 365 if order["product_id"].endswith("_year") else 30
        column = "premium_until" if order["product_type"] == "premium" else "business_until"
        conn.execute(f"UPDATE users SET {column}=datetime('now', ? || ' days') WHERE id=?", (days, order["user_id"]))
        conn.execute("INSERT INTO superme_transactions(user_id,kind,amount_uzs,reference,created_at) VALUES(?,?,?,?,?)", (order["user_id"], order["product_type"] + "_purchase", order["amount_uzs"], data.order_id, now()))
    conn.commit()
    conn.close()
    return {"ok": True, "status": "paid", "order_id": data.order_id}


@router.get("/orders")
def orders(token: str):
    user = current_user(token)
    conn = db()
    rows = conn.execute("SELECT id,product_type,product_id,amount_uzs,stars,status,payment_reference,created_at,verified_at FROM superme_orders WHERE user_id=? ORDER BY created_at DESC", (user["id"],)).fetchall()
    conn.close()
    return {"ok": True, "orders": [dict(r) for r in rows]}


@router.get("/transactions")
def transactions(token: str):
    user = current_user(token)
    conn = db()
    rows = conn.execute("SELECT id,kind,amount_uzs,stars_delta,reference,created_at FROM superme_transactions WHERE user_id=? ORDER BY id DESC", (user["id"],)).fetchall()
    conn.close()
    return {"ok": True, "transactions": [dict(r) for r in rows]}


@router.get("/profile/gifts")
def profile_gifts(token: str):
    user = current_user(token)
    conn = db()
    rows = conn.execute("SELECT id,gift_id,gift_name,price_stars,purchased_at FROM purchased_gifts WHERE user_id=? ORDER BY id DESC", (user["id"],)).fetchall()
    conn.close()
    return {"ok": True, "gifts": [dict(r) for r in rows]}
