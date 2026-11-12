import os
import httpx

PAYMENT_URL = os.getenv("PAYMENT_URL", "http://payment-service:8001")


def charge(amount: float, email: str) -> dict:
    """Call the mock payment service. Returns {"status": "success"|"failed", "reference": str}."""
    r = httpx.post(f"{PAYMENT_URL}/pay", json={"amount": amount, "email": email}, timeout=5)
    r.raise_for_status()
    return r.json()
