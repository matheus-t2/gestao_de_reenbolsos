from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit, services
from ..audit import write_tx
from ..database import get_db
from ..models import Category, ReimbursementRequest as R, Status, User
from ..policy import allowed_actions, visibility_clause
from ..schemas import (ApproveIn, DecisionOut, PayIn, Ref, RejectIn, RequestIn, RequestOut, RequestSummary)
from ..security import current_user, require_roles
from ..models import Role

router = APIRouter(prefix="/reimbursements", tags=["reimbursements"])
business_user = require_roles(Role.EMPLOYEE, Role.MANAGER, Role.FINANCE)  # ADMIN não opera reembolsos


def _ip(r: Request):
    return r.client.host if r.client else None


def _money(cents: int) -> Decimal:
    return (Decimal(cents) / 100).quantize(Decimal("0.01"))


def _summary(r: R) -> dict:
    return dict(id=r.id, requester=Ref(id=r.requester.id, name=r.requester.name),
                department=Ref(id=r.department.id, name=r.department.name), category=r.category,
                amount=_money(r.amount_cents), expense_date=r.expense_date, status=r.status)


def _out(r: R, user: User) -> RequestOut:
    return RequestOut(**_summary(r), justification=r.justification, receipt_reference=r.receipt_reference,
                      created_at=r.created_at, updated_at=r.updated_at, submitted_at=r.submitted_at,
                      version=r.version, allowed_actions=allowed_actions(user, r))


def load_visible(db: Session, user: User, rid: int, ip) -> R:
    """404 se não existe; 403 (sem revelar nenhum dado) se existe mas o usuário não pode acessá-la."""
    req = db.scalar(select(R).where(R.id == rid, visibility_clause(user)))
    if req:
        return req
    if db.get(R, rid) is None:
        raise HTTPException(404, "Solicitação não encontrada.")
    with write_tx(db):
        audit.record(db, user, "ACCESS_DENIED", "reimbursement", rid, {"reason": "not_visible"}, ip)
    raise HTTPException(403, "Você não tem permissão para acessar esta solicitação.")


def _guarded(db: Session, user: User, rid: int, ip, fn):
    try:
        return fn()
    except services.Audited as e:  # persiste a tentativa na auditoria (a transação da operação já foi revertida)
        with write_tx(db):
            audit.record(db, user, e.action, "reimbursement", rid, {"detail": str(e.detail)}, ip)
        raise


@router.post("", response_model=RequestOut, status_code=201)
def create(body: RequestIn, request: Request, user: User = Depends(business_user), db: Session = Depends(get_db)):
    return _out(services.create_draft(db, user, body, _ip(request)), user)


@router.get("", response_model=list[RequestSummary])
def list_requests(
    department_id: int | None = None,
    status: Status | None = None,
    category: Category | None = None,
    mine: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(business_user),
    db: Session = Depends(get_db),
):
    """Lista o que o perfil pode ver; os filtros apenas restringem ainda mais (nunca ampliam)."""
    q = select(R).where(visibility_clause(user))
    if mine:
        q = q.where(R.requester_id == user.id)
    if department_id is not None:
        q = q.where(R.department_id == department_id)
    if status:
        q = q.where(R.status == status)
    if category:
        q = q.where(R.category == category)
    return [RequestSummary(**_summary(r)) for r in db.scalars(q.order_by(R.id.desc()).limit(limit).offset(offset))]


@router.get("/{rid}", response_model=RequestOut)
def get_one(rid: int, request: Request, user: User = Depends(business_user), db: Session = Depends(get_db)):
    ip = _ip(request)
    req = load_visible(db, user, rid, ip)
    if req.requester_id != user.id:  # leitura de dados de terceiros fica registrada
        with write_tx(db):
            audit.record(db, user, "READ", "reimbursement", rid, {}, ip)
    return _out(req, user)


@router.put("/{rid}", response_model=RequestOut)
def update(rid: int, body: RequestIn, request: Request, user: User = Depends(business_user), db: Session = Depends(get_db)):
    ip = _ip(request)
    req = load_visible(db, user, rid, ip)
    return _out(_guarded(db, user, rid, ip, lambda: services.update_draft(db, user, req, body, ip)), user)


@router.delete("/{rid}", status_code=204)
def delete(rid: int, request: Request, user: User = Depends(business_user), db: Session = Depends(get_db)):
    ip = _ip(request)
    req = load_visible(db, user, rid, ip)
    _guarded(db, user, rid, ip, lambda: services.delete_draft(db, user, req, ip))
    return Response(status_code=204)


@router.post("/{rid}/submit", response_model=RequestOut)
def submit(rid: int, request: Request, user: User = Depends(business_user), db: Session = Depends(get_db)):
    ip = _ip(request)
    req = load_visible(db, user, rid, ip)
    return _out(_guarded(db, user, rid, ip, lambda: services.submit(db, user, req, ip)), user)


@router.post("/{rid}/approve", response_model=RequestOut)
def approve(rid: int, request: Request, body: ApproveIn = ApproveIn(), user: User = Depends(business_user),
            db: Session = Depends(get_db)):
    """Gestor (etapa 1) ou Financeiro (etapa 2): a etapa é definida pela situação atual e pelo perfil."""
    ip = _ip(request)
    req = load_visible(db, user, rid, ip)
    return _out(_guarded(db, user, rid, ip, lambda: services.decide(db, user, req, True, body.comment, ip)), user)


@router.post("/{rid}/reject", response_model=RequestOut)
def reject(rid: int, body: RejectIn, request: Request, user: User = Depends(business_user), db: Session = Depends(get_db)):
    ip = _ip(request)
    req = load_visible(db, user, rid, ip)
    return _out(_guarded(db, user, rid, ip, lambda: services.decide(db, user, req, False, body.justification, ip)), user)


@router.post("/{rid}/pay", response_model=RequestOut)
def pay(rid: int, body: PayIn, request: Request, user: User = Depends(business_user), db: Session = Depends(get_db)):
    ip = _ip(request)
    req = load_visible(db, user, rid, ip)
    return _out(_guarded(db, user, rid, ip, lambda: services.pay(db, user, req, body, ip)), user)


@router.get("/{rid}/history", response_model=list[DecisionOut])
def history(rid: int, request: Request, user: User = Depends(business_user), db: Session = Depends(get_db)):
    req = load_visible(db, user, rid, _ip(request))
    return [DecisionOut(id=d.id, actor=Ref(id=d.actor.id, name=d.actor.name), actor_role=d.actor_role, stage=d.stage,
                        decision=d.decision, comment=d.comment, from_status=d.from_status, to_status=d.to_status,
                        content_hash=d.content_hash, created_at=d.created_at) for d in req.decisions]
