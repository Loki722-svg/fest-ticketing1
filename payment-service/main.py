import uuid
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Mock Payment Service")


class PayIn(BaseModel):
    amount: float
    email: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/pay")
def pay(data: PayIn):
    # Mock rule: negative amounts fail, everything else succeeds.
    if data.amount < 0:
        return {"status": "failed", "reference": None}
    return {"status": "success", "reference": "PAY-" + uuid.uuid4().hex[:10].upper()}
