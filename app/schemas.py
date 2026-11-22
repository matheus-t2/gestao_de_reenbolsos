from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .models import Category, Role, Status


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RequestIn(Strict):
    """Somente estes campos são aceitos: solicitante, departamento e situação nunca vêm do cliente."""
    category: Category
    amount: Decimal = Field(gt=0, le=Decimal("50000"), max_digits=9, decimal_places=2)  # RN04
    expense_date: date
    justification: str = Field(min_length=3, max_length=1000)
    receipt_reference: str = Field(min_length=3, max_length=50)

    @field_validator("expense_date")
    @classmethod
    def not_future(cls, v):  # RN06
        if v > date.today():
            raise ValueError("A data da despesa não pode estar no futuro.")
        return v


class ApproveIn(Strict):
    comment: str | None = Field(default=None, max_length=1000)


class RejectIn(Strict):
    justification: str = Field(min_length=3, max_length=1000)  # RN11


class PayIn(Strict):
    payment_reference: str = Field(min_length=3, max_length=100)


class Ref(BaseModel):
    id: int
    name: str


class RequestSummary(BaseModel):
    id: int
    requester: Ref
    department: Ref
    category: Category
    amount: Decimal
    expense_date: date
    status: Status


class RequestOut(RequestSummary):
    justification: str
    receipt_reference: str
    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None
    version: int
    allowed_actions: list[str]


class DecisionOut(BaseModel):
    id: int
    actor: Ref
    actor_role: str
    stage: str
    decision: str
    comment: str | None
    from_status: str
    to_status: str
    content_hash: str | None
    created_at: datetime


class DepartmentIn(Strict):
    name: str = Field(min_length=2, max_length=100)


class DepartmentOut(BaseModel):
    id: int
    name: str


class UserIn(Strict):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    role: Role
    department_id: int


class UserAdminUpdate(Strict):
    role: Role | None = None
    department_id: int | None = None
    active: bool | None = None


class ProfileUpdate(BaseModel):
    """Atualização do próprio perfil: só nome e senha. Campos privilegiados enviados aqui são
    tratados como tentativa de elevação (403 + auditoria) pelo endpoint (RN15)."""
    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)
    name: str | None = Field(default=None, min_length=2, max_length=120)
    current_password: str | None = Field(default=None, max_length=128)
    new_password: str | None = Field(default=None, min_length=10, max_length=128)


class UserOut(BaseModel):  # sem hash/credenciais (RN13)
    id: int
    name: str
    email: str
    role: Role
    department_id: int
    active: bool


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
