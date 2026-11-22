import os

os.environ["DATABASE_URL"] = "sqlite:///./test_nexus.db"
os.environ["NEXUS_JWT_SECRET"] = "test-secret-test-secret-test-secret"
os.environ["NEXUS_PBKDF2_ITER"] = "1000"  # rápido nos testes

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app
from seed import seed

PWD = "Trocar@12345"


@pytest.fixture()
def env():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db, PWD)
    with TestClient(app) as c:
        yield c


def login(c, who, pwd=PWD):
    r = c.post("/auth/login", data={"username": f"{who}@nexus.com", "password": pwd})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def payload(receipt="NF-1001", amount="180.00", category="FOOD", **kw):
    return {"category": category, "amount": amount, "expense_date": "2026-11-10",
            "justification": "Almoço com cliente em visita técnica", "receipt_reference": receipt, **kw}


def draft(c, who="ana", **kw):
    r = c.post("/reimbursements", json=payload(**kw), headers=login(c, who))
    assert r.status_code == 201, r.text
    return r.json()["id"]


def submitted(c, who="ana", **kw):
    rid = draft(c, who, **kw)
    r = c.post(f"/reimbursements/{rid}/submit", headers=login(c, who))
    assert r.status_code == 200, r.text
    return rid


def approve(c, who, rid, comment=None):
    return c.post(f"/reimbursements/{rid}/approve", headers=login(c, who), json={"comment": comment})


def reject(c, who, rid, justification="Comprovante ilegível"):
    return c.post(f"/reimbursements/{rid}/reject", headers=login(c, who), json={"justification": justification})


def pay(c, who, rid, ref="PIX-0001"):
    return c.post(f"/reimbursements/{rid}/pay", headers=login(c, who), json={"payment_reference": ref})
