from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
import json
import secrets
from .superme_api import db, external_user_id, external_owner_grant, SUBSCRIPTIONS, now

router = APIRouter(prefix="/superme", tags=["superme"])

class ExternalSubscriptionStarsPurchase(BaseModel):
    product_id: str

@router.post("/external/subscription-stars")
def external_subscription_stars_purchase(
    data: ExternalSubscriptionStarsPurchase,
    x_client_id: str = Header(default="", alias="X-Client-Id"),
    x_request_id: str = Header(default="", alias="X-Request-Id"),
):
    user_id = external_user_id(x_client_id)
    request_id = str(x_request_id or "").strip()
    if not request_id:
        raise HTTPException(status_code=400, detail="X-Request-Id required")
    product = SUBSCRIPTIONS.get(data.product_id)
    if not product or data.product_id not in SUBSCRIPTIONS:
        raise HTTPException(status_code=400, detail="Subscription not found")

    conn = db()
    existing = conn.execute(
        "SELECT id,metadata_json FROM superme_external_transactions WHERE reference=? AND external_user_id=?",
        (request_id, user_id),
    ).fetchone()
    if existing:
        meta = json.loads(existing["metadata_json"] or "{}")
        conn.close()
        return {"ok": True, "transaction_id": existing["id"], "balance": int(meta.get("balance_after", 0)), "product_id": data.product_id, "status": "paid"}

    wallet = external_owner_grant(conn, user_id)
    balance = int(wallet["stars"])
    price = int(product["price_stars"])
    if balance < price:
        conn.close()
        raise HTTPException(status_code=402, detail="INSUFFICIENT_SUPERME_STARS")

    next_balance = balance - price
    transaction_id = secrets.token_urlsafe(18)
    timestamp = now()
    metadata = {
        "product_id": data.product_id,
        "subscription": product["name"],
        "period": product["period"],
        "price_stars": price,
        "balance_before": balance,
        "balance_after": next_balance,
        "activated": True,
    }
    conn.execute(
        "UPDATE superme_external_wallets SET stars=?,updated_at=? WHERE external_user_id=?",
        (next_balance, timestamp, user_id),
    )
    conn.execute(
        "INSERT INTO superme_external_transactions(id,external_user_id,kind,stars_delta,product_id,reference,metadata_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (transaction_id, user_id, "subscription_stars_purchase", -price, data.product_id, request_id, json.dumps(metadata, ensure_ascii=False), timestamp),
    )
    conn.commit()
    conn.close()
    return {
        "ok": True,
        "transaction_id": transaction_id,
        "balance": next_balance,
        "product_id": data.product_id,
        "status": "paid",
        "subscription": product["name"],
        "period": product["period"],
        "activated": True,
    }
