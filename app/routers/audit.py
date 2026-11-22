from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..database import get_db
from ..models import AuditLog, Role
from ..security import require_roles

router = APIRouter(prefix="/audit", tags=["audit"], dependencies=[Depends(require_roles(Role.ADMIN))])


@router.get("")
def list_audit(entity_type: str | None = None, entity_id: int | None = None, action: str | None = None,
               limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    q = select(AuditLog)
    if entity_type:
        q = q.where(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        q = q.where(AuditLog.entity_id == entity_id)
    if action:
        q = q.where(AuditLog.action == action)
    rows = db.scalars(q.order_by(AuditLog.id.desc()).limit(limit).offset(offset)).all()
    return [dict(id=r.id, at=r.created_at, actor_id=r.actor_id, action=r.action, entity_type=r.entity_type,
                 entity_id=r.entity_id, detail=r.detail, ip=r.ip, hash=r.hash) for r in rows]


@router.get("/verify")
def verify(db: Session = Depends(get_db)):
    """Recalcula a cadeia de hashes: qualquer alteração/remoção de registro é detectada."""
    return audit.verify_chain(db)
