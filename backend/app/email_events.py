import httpx
from .config import settings

async def emit_email(event_type: str, to: str, name: str, **data):
    payload = {"event_type": event_type, "to": to, "name": name, **data}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(settings.n8n_webhook_url, json=payload)
    except Exception:
        # Appointment state changes must not be rolled back if local email automation is temporarily unavailable.
        pass
