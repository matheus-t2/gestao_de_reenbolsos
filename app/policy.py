"""Regras de acesso centralizadas (única fonte de verdade) – ver matriz em docs/DOCUMENTACAO.md.

Visibilidade:
  EMPLOYEE -> só as próprias
  MANAGER  -> as próprias + as ENVIADAS (não-rascunho) do seu departamento      (RN02/RN03)
  FINANCE  -> as próprias + as que já foram encaminhadas pelo gestor
  ADMIN    -> só as próprias (administra cadastro; não enxerga dados financeiros)
"""
from sqlalchemy import and_, or_

from .models import ReimbursementRequest as R, Role, Status


def visibility_clause(user):
    own = R.requester_id == user.id
    if user.role == Role.MANAGER:
        return or_(own, and_(R.status != Status.DRAFT, R.department_id == user.department_id))
    if user.role == Role.FINANCE:
        return or_(own, R.manager_approved_at.is_not(None))
    return own


def decision_stage(user, req) -> str | None:
    """Etapa que `user` pode decidir agora, ou None. Ninguém decide a própria solicitação (RN09)."""
    if not user.active or req.requester_id == user.id:
        return None
    if req.status == Status.PENDING_MANAGER and user.role == Role.MANAGER and user.department_id == req.department_id:
        return "MANAGER"
    if req.status == Status.PENDING_FINANCE and user.role == Role.FINANCE:
        return "FINANCE"
    return None


def can_pay(user, req) -> bool:
    return (user.active and user.role == Role.FINANCE and req.status == Status.APPROVED
            and req.requester_id != user.id)


def allowed_actions(user, req) -> list[str]:
    acts = []
    if req.requester_id == user.id and req.status == Status.DRAFT:
        acts += ["edit", "delete", "submit"]
    if decision_stage(user, req):
        acts += ["approve", "reject"]
    if can_pay(user, req):
        acts.append("pay")
    return acts
