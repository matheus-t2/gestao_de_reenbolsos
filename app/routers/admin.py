from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import audit
from ..audit import write_tx
from ..database import get_db
from ..models import Department, Role, User
from ..schemas import DepartmentIn, DepartmentOut, UserAdminUpdate, UserIn, UserOut
from ..security import current_user, hash_password, require_roles

router = APIRouter(prefix="/admin", tags=["admin"])
departments_router = APIRouter(tags=["departments"])
admin_only = require_roles(Role.ADMIN)


def _ip(r: Request):
    return r.client.host if r.client else None


@departments_router.get("/departments", response_model=list[DepartmentOut])
def list_departments(_: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Department).order_by(Department.name)).all()


@router.post("/departments", response_model=DepartmentOut, status_code=201)
def create_department(body: DepartmentIn, request: Request, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    try:
        with write_tx(db):
            d = Department(name=body.name)
            db.add(d)
            db.flush()
            audit.record(db, admin, "DEPARTMENT_CREATE", "department", d.id, {"name": d.name}, _ip(request))
    except IntegrityError:
        raise HTTPException(409, "Departamento já existe.")
    return d


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: UserIn, request: Request, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    if not db.get(Department, body.department_id):
        raise HTTPException(422, "Departamento inexistente.")
    try:
        with write_tx(db):
            u = User(name=body.name, email=str(body.email).lower(), password_hash=hash_password(body.password),
                     role=body.role, department_id=body.department_id)
            db.add(u)
            db.flush()
            audit.record(db, admin, "USER_CREATE", "user", u.id,
                         {"role": u.role.value, "department_id": u.department_id}, _ip(request))
    except IntegrityError:
        raise HTTPException(409, "E-mail já cadastrado.")
    return u


@router.get("/users", response_model=list[UserOut])
def list_users(_: User = Depends(admin_only), db: Session = Depends(get_db)):
    return db.scalars(select(User).order_by(User.id)).all()


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserAdminUpdate, request: Request, admin: User = Depends(admin_only),
                db: Session = Depends(get_db)):
    """Único caminho para alterar perfil/departamento/ativação – restrito ao ADMIN e auditado (RN15)."""
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "Usuário não encontrado.")
    if u.id == admin.id:
        raise HTTPException(409, "Um administrador não pode alterar o próprio perfil, vínculo ou ativação.")
    if body.department_id is not None and not db.get(Department, body.department_id):
        raise HTTPException(422, "Departamento inexistente.")
    changes = body.model_dump(exclude_none=True)
    with write_tx(db):
        before = {k: getattr(u, k).value if hasattr(getattr(u, k), "value") else getattr(u, k) for k in changes}
        for k, v in changes.items():
            setattr(u, k, v)
        u.token_version += 1  # RN14: sessões antigas deixam de valer
        audit.record(db, admin, "USER_UPDATE", "user", u.id,
                     {"before": before, "after": {k: getattr(v, "value", v) for k, v in changes.items()}}, _ip(request))
    return u
