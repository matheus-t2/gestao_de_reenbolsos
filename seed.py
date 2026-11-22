"""Dados de demonstração:  python seed.py   (senha: SEED_PASSWORD ou 'Trocar@12345')"""
import os

from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import Department, Role, User
from app.security import hash_password

PWD = os.getenv("SEED_PASSWORD", "Trocar@12345")

USERS = [  # (nome, e-mail, perfil, departamento)
    ("Patrícia Gestora", "patricia@nexus.com", Role.MANAGER, "Comercial"),
    ("Tiago Gestor", "tiago@nexus.com", Role.MANAGER, "Tecnologia"),
    ("Marta Gestora", "marta@nexus.com", Role.MANAGER, "Financeiro"),
    ("Ana Colaboradora", "ana@nexus.com", Role.EMPLOYEE, "Comercial"),
    ("Carlos Colaborador", "carlos@nexus.com", Role.EMPLOYEE, "Comercial"),
    ("Bruno Colaborador", "bruno@nexus.com", Role.EMPLOYEE, "Tecnologia"),
    ("Fábio Financeiro", "fabio@nexus.com", Role.FINANCE, "Financeiro"),
    ("Fernanda Financeiro", "fernanda@nexus.com", Role.FINANCE, "Financeiro"),
    ("Admin TI", "admin@nexus.com", Role.ADMIN, "Tecnologia"),
]


def seed(db, password=PWD):
    depts = {n: Department(name=n) for n in ("Comercial", "Tecnologia", "Financeiro")}
    db.add_all(depts.values())
    db.flush()
    for name, email, role, dept in USERS:
        db.add(User(name=name, email=email, password_hash=hash_password(password), role=role,
                    department_id=depts[dept].id))
    db.commit()


if __name__ == "__main__":
    Base.metadata.create_all(engine)
    with SessionLocal() as s:
        if s.scalar(select(User).limit(1)):
            print("Banco já populado.")
        else:
            seed(s)
            print(f"Seed concluído. Usuários: {', '.join(u[1] for u in USERS)} | senha: {PWD}")
