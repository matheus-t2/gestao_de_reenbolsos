"""Fluxo de aprovação. Cada operação é uma transação única: mudança de estado +
histórico (`decisions`) + auditoria (`audit_log`) – tudo ou nada."""
import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import audit
from .audit import write_tx
from .models import Decision, ReimbursementRequest as R, Status, User, utcnow
from .policy import can_pay, decision_stage
from .schemas import PayIn, RequestIn


class Audited(HTTPException):
    """Erro que o router registra na trilha de auditoria (tentativa não autorizada, violação de integridade)."""
    def __init__(self, code: int, detail: str, action: str):
        super().__init__(code, detail)
        self.action = action


def Forbidden(msg="Você não tem permissão para esta ação nesta solicitação."):
    return Audited(403, msg, "ACCESS_DENIED")


# ------------------------------------------------------------- helpers
def receipt_key(ref: str) -> str:
    return " ".join(ref.strip().upper().split())


def content_hash(req: R) -> str:
    payload = [req.requester_id, req.department_id, req.category.value, req.amount_cents,
               req.expense_date.isoformat(), req.justification, req.receipt_key]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()


def _cents(p: RequestIn) -> int:
    return int((p.amount * 100).to_integral_value())


def _check_receipt(db: Session, user_id: int, key: str, exclude_id: int | None = None):  # RN05
    q = select(R.id).where(R.requester_id == user_id, R.receipt_key == key)
    if exclude_id:
        q = q.where(R.id != exclude_id)
    if db.scalar(q) is not None:
        raise HTTPException(409, "Você já registrou uma despesa com esta referência de comprovante.")


def _owned_draft(user: User, req: R, verb: str):
    if req.requester_id != user.id:
        raise Forbidden(f"Somente o solicitante pode {verb} a solicitação.")
    if req.status != Status.DRAFT:  # RN07
        raise HTTPException(409, "A solicitação já foi enviada e não pode mais ser alterada ou excluída.")


def _log(db, req, actor, stage, decision, comment, from_s, to_s, ip, action):
    db.add(Decision(request_id=req.id, actor_id=actor.id, actor_role=actor.role.value, stage=stage,
                    decision=decision, comment=comment, from_status=from_s.value, to_status=to_s.value,
                    content_hash=req.content_hash))
    audit.record(db, actor, action, "reimbursement", req.id,
                 {"from": from_s.value, "to": to_s.value, "stage": stage, "comment": comment}, ip)


def _check_integrity(req: R):
    if req.content_hash and content_hash(req) != req.content_hash:
        raise Audited(409, "Conteúdo divergente do que foi enviado (violação de integridade).", "INTEGRITY_VIOLATION")


# ------------------------------------------------------------- operações
def create_draft(db: Session, user: User, p: RequestIn, ip) -> R:
    with write_tx(db):
        key = receipt_key(p.receipt_reference)
        _check_receipt(db, user.id, key)
        req = R(requester_id=user.id, department_id=user.department_id, category=p.category,
                amount_cents=_cents(p), expense_date=p.expense_date, justification=p.justification,
                receipt_reference=p.receipt_reference, receipt_key=key, status=Status.DRAFT)
        db.add(req)
        db.flush()
        audit.record(db, user, "CREATE", "reimbursement", req.id, {"amount_cents": req.amount_cents}, ip)
    return req


def update_draft(db: Session, user: User, req: R, p: RequestIn, ip) -> R:
    with write_tx(db):
        _owned_draft(user, req, "editar")
        key = receipt_key(p.receipt_reference)
        _check_receipt(db, user.id, key, exclude_id=req.id)
        req.category, req.amount_cents, req.expense_date = p.category, _cents(p), p.expense_date
        req.justification, req.receipt_reference, req.receipt_key = p.justification, p.receipt_reference, key
        req.updated_at = utcnow()
        audit.record(db, user, "UPDATE", "reimbursement", req.id, {"amount_cents": req.amount_cents}, ip)
    return req


def delete_draft(db: Session, user: User, req: R, ip) -> None:
    with write_tx(db):
        _owned_draft(user, req, "excluir")
        rid = req.id
        db.delete(req)
        db.flush()
        audit.record(db, user, "DELETE", "reimbursement", rid, {}, ip)


def submit(db: Session, user: User, req: R, ip) -> R:
    with write_tx(db):
        _owned_draft(user, req, "enviar")
        req.content_hash = content_hash(req)  # congela o conteúdo submetido
        req.status, req.submitted_at, req.updated_at = Status.PENDING_MANAGER, utcnow(), utcnow()
        _log(db, req, user, "SUBMISSION", "SUBMITTED", None, Status.DRAFT, Status.PENDING_MANAGER, ip, "SUBMIT")
    return req


def decide(db: Session, user: User, req: R, approve: bool, comment: str | None, ip) -> R:
    with write_tx(db):
        stage = decision_stage(user, req)
        if stage is None:
            if req.status in (Status.PENDING_MANAGER, Status.PENDING_FINANCE):
                raise Forbidden("Você não é o responsável por analisar esta solicitação nesta etapa.")
            raise HTTPException(409, f"Solicitação na situação '{req.status.value}' não aceita análise.")
        if not approve and not comment:  # RN11 (defesa em profundidade; o schema já exige)
            raise HTTPException(422, "Informe a justificativa da recusa.")
        _check_integrity(req)
        before = req.status
        if not approve:
            after, verb, action = Status.REJECTED, "REJECTED", f"REJECT_{stage}"
        elif stage == "MANAGER":
            after, verb, action = Status.PENDING_FINANCE, "APPROVED", "APPROVE_MANAGER"
            req.manager_approved_at = utcnow()  # RN08: só a partir daqui o financeiro enxerga
        else:
            after, verb, action = Status.APPROVED, "APPROVED", "APPROVE_FINANCE"
        req.status, req.updated_at = after, utcnow()
        _log(db, req, user, stage, verb, comment, before, after, ip, action)
    return req


def pay(db: Session, user: User, req: R, p: PayIn, ip) -> R:
    with write_tx(db):
        if not can_pay(user, req):
            if req.status == Status.APPROVED:
                raise Forbidden("Somente o financeiro (e nunca o próprio solicitante) pode registrar o pagamento.")
            raise HTTPException(409, "O pagamento só pode ser registrado após a aprovação financeira.")  # RN10
        _check_integrity(req)
        req.status, req.updated_at = Status.PAID, utcnow()
        _log(db, req, user, "PAYMENT", "PAID", f"ref: {p.payment_reference}", Status.APPROVED, Status.PAID, ip, "PAY")
    return req
