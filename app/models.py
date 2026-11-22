"""Modelo de dados (ver docs/DOCUMENTACAO.md para o diagrama).

Defesas na camada de persistência, além das regras da API:
  * versão otimista (version_id_col): decisões concorrentes não se sobrepõem;
  * campos da solicitação só mudam em DRAFT; transições seguem o fluxo (RN07/RN08/RN10);
  * só rascunhos podem ser excluídos;
  * `decisions` e `audit_log` são somente-inserção.
"""
import enum
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, String, Text, UniqueConstraint, event, inspect
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)  # UTC


class ImmutableError(Exception):
    pass


class Role(str, enum.Enum):
    EMPLOYEE = "EMPLOYEE"    # Colaborador
    MANAGER = "MANAGER"      # Gestor
    FINANCE = "FINANCE"      # Financeiro
    ADMIN = "ADMIN"          # técnico: cadastro de usuários; sem acesso a reembolsos


class Status(str, enum.Enum):
    DRAFT = "DRAFT"                      # Rascunho
    PENDING_MANAGER = "PENDING_MANAGER"  # Aguardando gestor
    PENDING_FINANCE = "PENDING_FINANCE"  # Aguardando financeiro
    APPROVED = "APPROVED"                # Aprovada
    PAID = "PAID"                        # Paga
    REJECTED = "REJECTED"                # Recusada


class Category(str, enum.Enum):
    FOOD = "FOOD"            # alimentação
    TRANSPORT = "TRANSPORT"  # transporte
    LODGING = "LODGING"      # hospedagem
    MATERIALS = "MATERIALS"  # materiais


ALLOWED_TRANSITIONS = {
    Status.DRAFT: {Status.PENDING_MANAGER},
    Status.PENDING_MANAGER: {Status.PENDING_FINANCE, Status.REJECTED},
    Status.PENDING_FINANCE: {Status.APPROVED, Status.REJECTED},
    Status.APPROVED: {Status.PAID},
    Status.PAID: set(),
    Status.REJECTED: set(),
}
PROTECTED_FIELDS = ("requester_id", "department_id", "category", "amount_cents",
                    "expense_date", "justification", "receipt_reference", "receipt_key")


def _enum(e):
    return Enum(e, native_enum=False, length=20)


class Department(Base):
    __tablename__ = "departments"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300))  # PBKDF2 com salt; nunca devolvido pela API
    role: Mapped[Role] = mapped_column(_enum(Role))
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    active: Mapped[bool] = mapped_column(default=True)
    token_version: Mapped[int] = mapped_column(default=1)  # incrementar invalida todos os tokens emitidos
    failed_attempts: Mapped[int] = mapped_column(default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, default=None)

    department: Mapped[Department] = relationship()


class ReimbursementRequest(Base):
    __tablename__ = "reimbursement_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)  # do solicitante, na criação
    category: Mapped[Category] = mapped_column(_enum(Category), index=True)
    amount_cents: Mapped[int]
    expense_date: Mapped[date] = mapped_column(Date)
    justification: Mapped[str] = mapped_column(Text)
    receipt_reference: Mapped[str] = mapped_column(String(50))
    receipt_key: Mapped[str] = mapped_column(String(50))  # referência normalizada (anti-duplicidade)
    status: Mapped[Status] = mapped_column(_enum(Status), default=Status.DRAFT, index=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), default=None)  # congelado no envio
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    manager_approved_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    version: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": version}
    __table_args__ = (UniqueConstraint("requester_id", "receipt_key", name="uq_requester_receipt"),)  # RN05

    requester: Mapped[User] = relationship()
    department: Mapped[Department] = relationship()
    decisions: Mapped[list["Decision"]] = relationship(order_by="Decision.id")


class Decision(Base):
    """Histórico de análise: responsável, etapa, decisão, data e observação (RN12)."""
    __tablename__ = "decisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("reimbursement_requests.id"), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    actor_role: Mapped[str] = mapped_column(String(20))
    stage: Mapped[str] = mapped_column(String(20))      # SUBMISSION | MANAGER | FINANCE | PAYMENT
    decision: Mapped[str] = mapped_column(String(20))   # SUBMITTED | APPROVED | REJECTED | PAID
    comment: Mapped[str | None] = mapped_column(Text, default=None)
    from_status: Mapped[str] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    content_hash: Mapped[str | None] = mapped_column(String(64), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    actor: Mapped[User] = relationship()


class AuditLog(Base):
    """Trilha de auditoria encadeada por hash (detecta adulteração/remoção)."""
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    actor_id: Mapped[int | None] = mapped_column(default=None)
    action: Mapped[str] = mapped_column(String(40), index=True)
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[int | None] = mapped_column(default=None)
    detail: Mapped[str] = mapped_column(Text, default="{}")
    ip: Mapped[str | None] = mapped_column(String(45), default=None)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))
    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id"),)


# ---------------------------------------------------------------- guardas
@event.listens_for(ReimbursementRequest, "before_update")
def _guard_update(mapper, conn, t):
    st = inspect(t)
    old = st.attrs.status.history.deleted
    before = old[0] if old else t.status
    if old and t.status not in ALLOWED_TRANSITIONS[before]:
        raise ImmutableError(f"Transição inválida: {before.value} -> {t.status.value}")
    if before != Status.DRAFT and any(st.attrs[f].history.has_changes() for f in PROTECTED_FIELDS):
        raise ImmutableError("Solicitação não pode ser alterada após o envio.")


@event.listens_for(ReimbursementRequest, "before_delete")
def _guard_delete(mapper, conn, t):
    if t.status != Status.DRAFT:
        raise ImmutableError("Somente rascunhos podem ser excluídos.")


def _append_only(*_):
    raise ImmutableError("Registro de histórico/auditoria é somente-inserção.")


for _m in (Decision, AuditLog):
    event.listen(_m, "before_update", _append_only)
    event.listen(_m, "before_delete", _append_only)
