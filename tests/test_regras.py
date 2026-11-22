"""Regras de negócio RN01–RN15, requisitos funcionais e fluxo."""
from sqlalchemy import text

from app.database import engine

from .conftest import PWD, approve, draft, login, pay, payload, reject, submitted


# RN01 / RN14 ------------------------------------------------------------------
def test_rn01_requires_authentication(env):
    for method, path in [("get", "/reimbursements"), ("post", "/reimbursements"), ("get", "/reimbursements/1"),
                         ("get", "/me"), ("get", "/admin/users"), ("get", "/departments")]:
        assert getattr(env, method)(path).status_code == 401, path
    assert env.get("/reimbursements", headers={"Authorization": "Bearer lixo"}).status_code == 401
    assert env.get("/health").status_code == 200


def test_rn14_session_invalidation(env):
    h = login(env, "ana")
    assert env.get("/me", headers=h).status_code == 200
    assert env.post("/auth/logout", headers=h).status_code == 204          # logout invalida o token
    assert env.get("/me", headers=h).status_code == 401
    h = login(env, "ana")
    ana_id = env.get("/me", headers=h).json()["id"]
    admin = login(env, "admin")
    assert env.patch(f"/admin/users/{ana_id}", headers=admin, json={"active": False}).status_code == 200
    assert env.get("/reimbursements", headers=h).status_code == 401        # desativada: nada passa
    assert env.post("/auth/login", data={"username": "ana@nexus.com", "password": PWD}).status_code == 401


def test_rn14_role_change_forces_new_token(env):
    h = login(env, "ana")
    ana_id = env.get("/me", headers=h).json()["id"]
    env.patch(f"/admin/users/{ana_id}", headers=login(env, "admin"), json={"department_id": 2})
    assert env.get("/me", headers=h).status_code == 401


def test_login_lockout(env):
    for _ in range(5):
        assert env.post("/auth/login", data={"username": "ana@nexus.com", "password": "x"}).status_code == 401
    assert env.post("/auth/login", data={"username": "ana@nexus.com", "password": PWD}).status_code == 429


# RN02 / RN03 -------------------------------------------------------------------
def test_rn02_drafts_private_even_to_manager_and_finance(env):
    rid = draft(env, "ana")
    for who in ("patricia", "fabio", "carlos", "admin"):
        assert env.get(f"/reimbursements/{rid}", headers=login(env, who)).status_code == 403, who
    assert env.get("/reimbursements/9999", headers=login(env, "ana")).status_code == 404


def test_rn03_manager_sees_only_own_department(env):
    c, t = submitted(env, "ana", receipt="REC-A"), submitted(env, "bruno", receipt="REC-B")
    assert env.get(f"/reimbursements/{c}", headers=login(env, "patricia")).status_code == 200
    assert env.get(f"/reimbursements/{t}", headers=login(env, "patricia")).status_code == 403


def test_finance_sees_only_after_manager_approval(env):
    rid = submitted(env, "ana")
    fin = login(env, "fabio")
    assert env.get(f"/reimbursements/{rid}", headers=fin).status_code == 403
    assert env.get("/reimbursements", headers=fin).json() == []
    approve(env, "patricia", rid)
    assert [r["id"] for r in env.get("/reimbursements", headers=fin).json()] == [rid]


# RN04 / RN06 / validação -------------------------------------------------------------
def test_rn04_rn06_and_input_validation(env):
    h = login(env, "ana")
    bad = [payload(amount="0"), payload(amount="-5"), payload(amount="10.999"), payload(amount="abc"),
           payload(amount="999999"), payload(category="LAZER"), payload(receipt=""),
           {**payload(), "expense_date": "2999-01-01"}, {**payload(), "expense_date": "ontem"},
           {k: v for k, v in payload().items() if k != "justification"}]
    for b in bad:
        assert env.post("/reimbursements", json=b, headers=h).status_code == 422, b
    assert env.get("/reimbursements", headers=h).json() == []             # nada foi gravado


# RN05 ------------------------------------------------------------------------------
def test_rn05_duplicate_receipt_per_collaborator(env):
    draft(env, "ana", receipt="NF-9")
    h = login(env, "ana")
    assert env.post("/reimbursements", json=payload(receipt=" nf-9 "), headers=h).status_code == 409  # normalizada
    assert env.post("/reimbursements", json=payload(receipt="NF-10"), headers=h).status_code == 201
    assert env.post("/reimbursements", json=payload(receipt="NF-9"), headers=login(env, "carlos")).status_code == 201


def test_rn05_also_on_update_and_after_rejection(env):
    a = draft(env, "ana", receipt="X-1")
    b = draft(env, "ana", receipt="X-2")
    h = login(env, "ana")
    assert env.put(f"/reimbursements/{b}", json=payload(receipt="X-1"), headers=h).status_code == 409
    assert env.put(f"/reimbursements/{b}", json=payload(receipt="X-2", amount="99.90"), headers=h).status_code == 200
    env.post(f"/reimbursements/{a}/submit", headers=h)
    reject(env, "patricia", a)
    assert env.post("/reimbursements", json=payload(receipt="X-1"), headers=h).status_code == 409  # continua registrada


# RN07 + requisitos 4/5 ---------------------------------------------------------------------
def test_rn07_edit_delete_only_in_draft_and_only_owner(env):
    rid = draft(env, "ana")
    ana, carlos = login(env, "ana"), login(env, "carlos")
    assert env.put(f"/reimbursements/{rid}", json=payload(amount="55.00"), headers=carlos).status_code == 403
    assert env.put(f"/reimbursements/{rid}", json=payload(amount="55.00"), headers=ana).json()["amount"] == "55.00"
    assert env.delete(f"/reimbursements/{rid}", headers=ana).status_code == 204
    assert env.get(f"/reimbursements/{rid}", headers=ana).status_code == 404
    done = submitted(env, "ana", receipt="Z-1")
    approve(env, "patricia", done)
    assert env.put(f"/reimbursements/{done}", json=payload(receipt="Z-1"), headers=ana).status_code == 409
    assert env.delete(f"/reimbursements/{done}", headers=ana).status_code == 409


def test_receipt_reference_is_released_when_draft_deleted(env):
    rid = draft(env, "ana", receipt="R-1")
    assert env.delete(f"/reimbursements/{rid}", headers=login(env, "ana")).status_code == 204
    assert env.post("/reimbursements", json=payload(receipt="R-1"), headers=login(env, "ana")).status_code == 201


# RN08 / RN10 / fluxo ------------------------------------------------------------------------
def test_full_flow_and_closed_states(env):
    rid = submitted(env, "ana")
    assert approve(env, "patricia", rid).json()["status"] == "PENDING_FINANCE"
    assert pay(env, "fabio", rid).status_code == 409                       # RN10: ainda não aprovada pelo financeiro
    assert approve(env, "fabio", rid).json()["status"] == "APPROVED"
    assert pay(env, "fernanda", rid).json()["status"] == "PAID"
    for call in (approve(env, "fabio", rid), reject(env, "fabio", rid), pay(env, "fabio", rid), approve(env, "patricia", rid)):
        assert call.status_code in (403, 409)
    assert env.delete(f"/reimbursements/{rid}", headers=login(env, "ana")).status_code == 409


def test_cannot_submit_twice_or_by_others(env):
    rid = draft(env, "ana")
    assert env.post(f"/reimbursements/{rid}/submit", headers=login(env, "carlos")).status_code == 403
    assert env.post(f"/reimbursements/{rid}/submit", headers=login(env, "ana")).status_code == 200
    assert env.post(f"/reimbursements/{rid}/submit", headers=login(env, "ana")).status_code == 409


def test_finance_rejection_closes_process(env):
    rid = submitted(env, "ana")
    approve(env, "patricia", rid)
    assert reject(env, "fabio", rid, "Valor acima da política").json()["status"] == "REJECTED"
    assert approve(env, "fernanda", rid).status_code in (403, 409)
    assert pay(env, "fernanda", rid).status_code == 409


# RN09 --------------------------------------------------------------------------------------
def test_rn09_no_self_approval(env):
    g = submitted(env, "patricia", receipt="P-1")        # gestora pede reembolso no próprio departamento
    assert approve(env, "patricia", g).status_code == 403
    assert reject(env, "patricia", g).status_code == 403
    f = submitted(env, "fabio", receipt="F-1")           # financeiro pede reembolso
    approve(env, "marta", f)                             # gestora do Financeiro aprova etapa 1
    assert approve(env, "fabio", f).status_code == 403   # ele mesmo não aprova a etapa financeira
    assert approve(env, "fernanda", f).json()["status"] == "APPROVED"
    assert pay(env, "fabio", f).status_code == 403       # nem registra o pagamento
    assert pay(env, "fernanda", f).json()["status"] == "PAID"


# RN11 / RN12 -----------------------------------------------------------------------------------
def test_rn11_rejection_requires_justification(env):
    rid = submitted(env, "ana")
    p = login(env, "patricia")
    assert env.post(f"/reimbursements/{rid}/reject", headers=p, json={}).status_code == 422
    assert env.post(f"/reimbursements/{rid}/reject", headers=p, json={"justification": "  "}).status_code == 422
    assert env.get(f"/reimbursements/{rid}", headers=p).json()["status"] == "PENDING_MANAGER"
    assert reject(env, "patricia", rid, "Sem nota fiscal").json()["status"] == "REJECTED"
    h = env.get(f"/reimbursements/{rid}/history", headers=login(env, "ana")).json()
    assert h[-1]["decision"] == "REJECTED" and h[-1]["comment"] == "Sem nota fiscal" and h[-1]["actor"]["name"] == "Patrícia Gestora"


# RN13 ---------------------------------------------------------------------------------------------
def test_rn13_credentials_never_exposed_or_stored_in_clear(env):
    h = login(env, "admin")
    txt = env.get("/admin/users", headers=h).text + env.get("/me", headers=h).text
    assert "password" not in txt.lower() and "pbkdf2" not in txt
    with engine.connect() as c:
        hashes = [r[0] for r in c.execute(text("SELECT password_hash FROM users"))]
    assert hashes and all(x.startswith("pbkdf2$") and PWD not in x for x in hashes)
    assert len(set(hashes)) == len(hashes)  # salt individual


# RN15 -----------------------------------------------------------------------------------------------
def test_rn15_only_admin_changes_role_or_department_and_it_is_audited(env):
    ana = login(env, "ana")
    assert env.patch("/me", headers=ana, json={"name": "Ana Maria"}).json()["name"] == "Ana Maria"
    assert env.patch("/me", headers=ana, json={"role": "MANAGER"}).status_code == 403
    assert env.patch("/me", headers=ana, json={"foo": 1}).status_code == 422
    ana_id = env.get("/me", headers=ana).json()["id"]
    adm = login(env, "admin")
    r = env.patch(f"/admin/users/{ana_id}", headers=adm, json={"department_id": 2})
    assert r.status_code == 200 and r.json()["department_id"] == 2
    ev = [e for e in env.get("/audit?action=USER_UPDATE", headers=adm).json()]
    assert len(ev) == 1


def test_password_change_requires_current_password(env):
    h = login(env, "ana")
    assert env.patch("/me", headers=h, json={"new_password": "NovaSenha@123"}).status_code == 403
    assert env.patch("/me", headers=h, json={"current_password": PWD, "new_password": "NovaSenha@123"}).status_code == 200
    assert env.get("/me", headers=h).status_code == 401  # tokens antigos caducam
    assert env.post("/auth/login", data={"username": "ana@nexus.com", "password": "NovaSenha@123"}).status_code == 200


def test_admin_has_no_access_to_reimbursements(env):
    rid = submitted(env, "ana")
    adm = login(env, "admin")
    assert env.get("/reimbursements", headers=adm).status_code == 403
    assert env.get(f"/reimbursements/{rid}", headers=adm).status_code == 403


# filtros (requisito §4) -----------------------------------------------------------------------------------
def test_filters_by_department_status_and_category(env):
    submitted(env, "ana", receipt="REC-F1", category="FOOD")
    submitted(env, "carlos", receipt="REC-T1", category="TRANSPORT")
    submitted(env, "bruno", receipt="REC-L1", category="LODGING")
    approve(env, "patricia", 1); approve(env, "patricia", 2); approve(env, "tiago", 3)
    fin = login(env, "fabio")
    assert len(env.get("/reimbursements", headers=fin).json()) == 3
    assert len(env.get("/reimbursements?department_id=1", headers=fin).json()) == 2
    assert [r["category"] for r in env.get("/reimbursements?category=LODGING", headers=fin).json()] == ["LODGING"]
    assert env.get("/reimbursements?status=PENDING_FINANCE&department_id=2&category=LODGING", headers=fin).json()[0]["id"] == 3
    assert env.get("/reimbursements?status=PAID", headers=fin).json() == []
    assert env.get("/reimbursements?status=INVALIDO", headers=fin).status_code == 422


# rastreabilidade / auditoria ------------------------------------------------------------------------------
def test_audit_chain_tamper_detected_and_admin_only(env):
    rid = submitted(env, "ana")
    approve(env, "patricia", rid)
    adm = login(env, "admin")
    assert env.get("/audit/verify", headers=adm).json()["valid"] is True
    with engine.begin() as c:
        c.execute(text("UPDATE audit_log SET actor_id = 5 WHERE action='APPROVE_MANAGER'"))
    assert env.get("/audit/verify", headers=adm).json()["valid"] is False
    assert env.get("/audit", headers=login(env, "ana")).status_code == 403


def test_denied_attempts_do_not_change_data_and_are_audited(env):
    rid = submitted(env, "bruno")
    with engine.connect() as c:
        before = c.execute(text("SELECT status, version, updated_at FROM reimbursement_requests")).all()
    approve(env, "patricia", rid); reject(env, "ana", rid); pay(env, "fabio", rid)
    env.get(f"/reimbursements/{rid}", headers=login(env, "ana"))
    with engine.connect() as c:
        assert c.execute(text("SELECT status, version, updated_at FROM reimbursement_requests")).all() == before
        assert c.execute(text("SELECT count(*) FROM decisions")).scalar() == 1  # só o envio
    denied = env.get("/audit?action=ACCESS_DENIED", headers=login(env, "admin")).json()
    assert len(denied) == 4


def test_orm_blocks_history_rewrite(env):
    import pytest
    from app.database import SessionLocal
    from app.models import Decision, ImmutableError
    rid = submitted(env, "ana")
    with SessionLocal() as db:
        d = db.query(Decision).filter_by(request_id=rid).first()
        d.comment = "reescrito"
        with pytest.raises(ImmutableError):
            db.commit()
