from fastapi import APIRouter, Header, HTTPException
import json
import os
import urllib.request

router = APIRouter(prefix="/superme/external", tags=["superme-gifts"])


def telegram_available_gifts():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise HTTPException(status_code=503, detail="TELEGRAM_BOT_TOKEN_NOT_CONFIGURED")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/getAvailableGifts",
        headers={"Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="TELEGRAM_GIFTS_UNAVAILABLE") from exc
    if not payload.get("ok"):
        raise HTTPException(status_code=503, detail="TELEGRAM_GIFTS_UNAVAILABLE")
    return payload.get("result", {}).get("gifts", [])


@router.get("/gifts")
def external_gifts(x_client_id: str = Header(default="", alias="X-Client-Id")):
    if not str(x_client_id or "").strip().isdigit():
        raise HTTPException(status_code=400, detail="X-Client-Id required")
    gifts = []
    for gift in telegram_available_gifts():
        sticker = gift.get("sticker") or {}
        gifts.append({
            "id": str(gift.get("id", "")),
            "stars": int(gift.get("star_count") or 0),
            "title": sticker.get("emoji") or "🎁",
            "emoji": sticker.get("emoji") or "🎁",
            "remaining_count": gift.get("remaining_count"),
            "total_count": gift.get("total_count"),
        })
    return {"ok": True, "gifts": gifts}
