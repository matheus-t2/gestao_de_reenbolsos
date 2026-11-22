from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from .database import Base, engine
from .models import ImmutableError
from .routers import admin, audit, auth, reimbursements


@asynccontextmanager
async def lifespan(_):
    Base.metadata.create_all(engine)  # v1; em produção usar migrations (Alembic)
    yield


app = FastAPI(title="NexusCorp – API de Reembolsos", version="1.0.0", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(admin.departments_router)
app.include_router(reimbursements.router)
app.include_router(audit.router)


@app.exception_handler(ImmutableError)
async def _immutable(_: Request, exc: ImmutableError):
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.exception_handler(StaleDataError)
async def _stale(_: Request, exc: StaleDataError):
    return JSONResponse({"detail": "Conflito de concorrência: a solicitação foi alterada por outra operação. Recarregue."},
                        status_code=409)


@app.get("/health", tags=["infra"])
def health():
    return {"status": "ok"}


@app.exception_handler(IntegrityError)
async def _integrity(_: Request, exc: IntegrityError):  # última barreira (ex.: corrida na unicidade do comprovante)
    return JSONResponse({"detail": "Operação viola uma restrição de integridade (ex.: registro duplicado)."}, status_code=409)
