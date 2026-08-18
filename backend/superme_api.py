from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
import sqlite3
import os
import secrets
import json
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

class ExternalGiftPurchase(BaseModel):
    gift_id: str
    stars: int
    recipient_id: str
    gift_title: str = "Gift"
    message: str = ""
    anonymous: bool = False
    upgraded: bool = False

class ExternalSubscriptionOrder(BaseModel):
    product_id: str
    product_type: str


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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS superme_external_wallets (
            external_user_id TEXT PRIMARY KEY,
            stars INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS superme_external_transactions (
            id TEXT PRIMARY KEY,
            external_user_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            stars_delta INTEGER NOT NULL DEFAULT 0,
            product_id TEXT DEFAULT '',
            recipient_id TEXT DEFAULT '',
            reference TEXT DEFAULT '',
            metadata_json TEXT DEFAULT '{}',
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS superme_external_gifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            external_user_id TEXT NOT NULL,
            recipient_id TEXT NOT NULL,
            gift_id TEXT NOT NULL,
            gift_title TEXT NOT NULL,
            price_stars INTEGER NOT NULL,
            message TEXT DEFAULT '',
            anonymous INTEGER NOT NULL DEFAULT 0,
            upgraded INTEGER NOT NULL DEFAULT 0,
            transaction_id TEXT NOT NULL,
            purchased_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS superme_external_orders (
            id TEXT PRIMARY KEY,
            external_user_id TEXT NOT NULL,
            product_type TEXT NOT NULL,
            product_id TEXT NOT NULL,
            amount_uzs INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            payment_reference TEXT DEFAULT ''
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
    grant = 500_000_000
    conn.execute("UPDATE users SET stars=stars+?, last_owner_grant=? WHERE id=?", (grant, now(), user["id"]))
    conn.execute(
        "INSERT INTO superme_transactions(user_id,kind,stars_delta,reference,created_at) VALUES(?,?,?,?,?)",
        (user["id"], "owner_monthly_grant", grant, "SUPERME_OWNER_GRANT", now()),
    )
    conn.commit()


def external_user_id(client_id: str) -> str:
    value = str(client_id or "").strip()
    if not value or not value.isdigit():
        raise HTTPException(status_code=400, detail="X-Client-Id required")
    return value


def external_owner_grant(conn, user_id: str):
    owner_id = os.getenv("SUPERME_OWNER_EXTERNAL_ID", "8572946823").strip()
    row = conn.execute("SELECT * FROM superme_external_wallets WHERE external_user_id=?", (user_id,)).fetchone()
    if row:
        return row
    initial = 500_000_000 if user_id == owner_id else 0
    timestamp = now()
    conn.execute(
        "INSERT INTO superme_external_wallets(external_user_id,stars,created_at,updated_at) VALUES(?,?,?,?,?)",
        (user_id, initial, timestamp, timestamp),
    )
    if initial:
        tx = secrets.token_urlsafe(18)
        conn.execute(
            "INSERT INTO superme_external_transactions(id,external_user_id,kind,stars_delta,reference,created_at) VALUES(?,?,?,?,?,?)",
            (tx, user_id, "owner_initial_grant", initial, "SUPERME_OWNER_INITIAL", timestamp),
        )
    conn.commit()
    return conn.execute("SELECT * FROM superme_external_wallets WHERE external_user_id=?", (user_id,)).fetchone()


def telegram_gift_price(gift_id: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return None
    try:
        import urllib.request
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/getAvailableGifts",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
        for gift in data.get("result", {}).get("gifts", []):
            if str(gift.get("id")) == gift_id:
                return int(gift.get("star_count") or 0)
    except Exception:
        return None
    return 0


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


@router.get("/external/balance")
def external_balance(x_client_id: str = Header(default="", alias="X-Client-Id")):
    user_id = external_user_id(x_client_id)
    conn = db()
    row = external_owner_grant(conn, user_id)
    conn.close()
    return {"ok": True, "external_user_id": user_id, "stars": int(row["stars"])}


@router.post("/external/gift")
def external_gift_purchase(
    data: ExternalGiftPurchase,
    x_client_id: str = Header(default="", alias="X-Client-Id"),
    x_request_id: str = Header(default="", alias="X-Request-Id"),
):
    user_id = external_user_id(x_client_id)
    request_id = str(x_request_id or "").strip()
    if not request_id:
        raise HTTPException(status_code=400, detail="X-Request-Id required")
    if data.stars <= 0 or data.stars > 10_000_000:
        raise HTTPException(status_code=400, detail="Invalid gift price")
    if not data.recipient_id.strip():
        raise HTTPException(status_code=400, detail="Invalid recipient")

    conn = db()
    existing = conn.execute(
        "SELECT id,metadata_json FROM superme_external_transactions WHERE reference=? AND external_user_id=?",
        (request_id, user_id),
    ).fetchone()
    if existing:
        meta = json.loads(existing["metadata_json"] or "{}")
        conn.close()
        return {"ok": True, "transaction_id": existing["id"], "balance": int(meta.get("balance_after", 0)), "gift_id": meta.get("gift_id", data.gift_id)}

    authoritative_price = telegram_gift_price(data.gift_id)
    if authoritative_price is None:
        conn.close()
        raise HTTPException(status_code=503, detail="TELEGRAM_BOT_TOKEN_NOT_CONFIGURED")
    if authoritative_price <= 0 or authoritative_price != data.stars:
        conn.close()
        raise HTTPException(status_code=409, detail="GIFT_PRICE_MISMATCH")

    wallet = external_owner_grant(conn, user_id)
    balance = int(wallet["stars"])
    if balance < data.stars:
        conn.close()
        raise HTTPException(status_code=402, detail="INSUFFICIENT_SUPERME_STARS")

    next_balance = balance - data.stars
    transaction_id = secrets.token_urlsafe(18)
    timestamp = now()
    metadata = {
        "gift_id": data.gift_id,
        "gift_title": data.gift_title[:120],
        "balance_before": balance,
        "balance_after": next_balance,
        "anonymous": bool(data.anonymous),
        "upgraded": bool(data.upgraded),
    }
    conn.execute("UPDATE superme_external_wallets SET stars=?,updated_at=? WHERE external_user_id=?", (next_balance, timestamp, user_id))
    conn.execute(
        "INSERT INTO superme_external_transactions(id,external_user_id,kind,stars_delta,product_id,recipient_id,reference,metadata_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (transaction_id, user_id, "gift_purchase", -data.stars, data.gift_id, data.recipient_id, request_id, json.dumps(metadata, ensure_ascii=False), timestamp),
    )
    conn.execute(
        "INSERT INTO superme_external_gifts(external_user_id,recipient_id,gift_id,gift_title,price_stars,message,anonymous,upgraded,transaction_id,purchased_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (user_id, data.recipient_id, data.gift_id, data.gift_title[:120], data.stars, data.message[:4096], int(data.anonymous), int(data.upgraded), transaction_id, timestamp),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "transaction_id": transaction_id, "balance": next_balance, "gift_id": data.gift_id, "recipient_id": data.recipient_id}


@router.get("/external/profile/gifts")
def external_profile_gifts(x_client_id: str = Header(default="", alias="X-Client-Id")):
    user_id = external_user_id(x_client_id)
    conn = db()
    rows = conn.execute(
        "SELECT id,recipient_id,gift_id,gift_title,price_stars,message,anonymous,upgraded,transaction_id,purchased_at FROM superme_external_gifts WHERE recipient_id=? OR external_user_id=? ORDER BY id DESC",
        (user_id, user_id),
    ).fetchall()
    conn.close()
    return {"ok": True, "gifts": [dict(r) for r in rows]}


@router.post("/external/subscription-order")
def external_subscription_order(data: ExternalSubscriptionOrder, x_client_id: str = Header(default="", alias="X-Client-Id")):
    user_id = external_user_id(x_client_id)
    if data.product_type not in ("premium", "business"):
        raise HTTPException(status_code=400, detail="Invalid subscription type")
    product = SUBSCRIPTIONS.get(data.product_id)
    if not product or not data.product_id.startswith(data.product_type + "_"):
        raise HTTPException(status_code=400, detail="Subscription not found")
    order_id = secrets.token_urlsafe(18)
    conn = db()
    conn.execute(
        "INSERT INTO superme_external_orders(id,external_user_id,product_type,product_id,amount_uzs,status,created_at) VALUES(?,?,?,?,?,?,?)",
        (order_id, user_id, data.product_type, data.product_id, product["price_uzs"], "pending", now()),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "order_id": order_id, "status": "pending", "product_type": data.product_type, "product_id": data.product_id, "amount_uzs": product["price_uzs"]}


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
