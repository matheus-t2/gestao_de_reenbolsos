"""Trilha de auditoria append-only com encadeamento de hash.

`write_tx` serializa as escritas (necessário para o encadeamento). Em produção
com PostgreSQL, trocar o lock de processo por pg_advisory_xact_lock.
"""
import hashlib
import json
import threading
from contextlib import contextmanager

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AuditLog, utcnow

GENESIS = "0" * 64
_lock = threading.RLock()


@contextmanager
def write_tx(db: Session):
    with _lock:
        try:
            yield
            db.commit()
        except BaseException:
            db.rollback()
            raise


def _digest(prev, ts, actor_id, action, etype, eid, detail, ip) -> str:
    raw = json.dumps([prev, ts.isoformat(), actor_id, action, etype, eid, detail, ip], separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def record(db: Session, actor, action: str, entity_type: str, entity_id=None, detail=None, ip=None):
    prev = db.scalar(select(AuditLog.hash).order_by(AuditLog.id.desc()).limit(1)) or GENESIS
    ts = utcnow()
    actor_id = getattr(actor, "id", None)
    detail_s = json.dumps(detail or {}, sort_keys=True, default=str, ensure_ascii=False)
    db.add(AuditLog(created_at=ts, actor_id=actor_id, action=action, entity_type=entity_type,
                    entity_id=entity_id, detail=detail_s, ip=ip, prev_hash=prev,
                    hash=_digest(prev, ts, actor_id, action, entity_type, entity_id, detail_s, ip)))
    db.flush()


def verify_chain(db: Session) -> dict:
    prev, n = GENESIS, 0
    for row in db.scalars(select(AuditLog).order_by(AuditLog.id)).yield_per(500):
        expected = _digest(prev, row.created_at, row.actor_id, row.action, row.entity_type,
                           row.entity_id, row.detail, row.ip)
        if row.prev_hash != prev or row.hash != expected:
            return {"valid": False, "checked": n, "first_invalid_id": row.id}
        prev, n = row.hash, n + 1
    return {"valid": True, "checked": n, "first_invalid_id": None}
