"""Os 8 cenários de homologação do enunciado (seção 7)."""
from sqlalchemy import text

from app.database import engine

from .conftest import PWD, approve, draft, login, pay, payload, submitted


def test_cenario_01_acesso_indevido(env):
    rid = submitted(env, "bruno", receipt="BR-1", amount="321.55")      # Bruno, Tecnologia
    r = env.get(f"/reimbursements/{rid}", headers=login(env, "ana"))    # Ana, Comercial
    assert r.status_code == 403
    assert "321" not in r.text and "BR-1" not in r.text                 # nenhum dado financeiro vaza
    assert env.get(f"/reimbursements/{rid}/history", headers=login(env, "ana")).status_code == 403
    assert env.put(f"/reimbursements/{rid}", json=payload(), headers=login(env, "ana")).status_code == 403
    assert env.delete(f"/reimbursements/{rid}", headers=login(env, "ana")).status_code == 403
    assert env.get("/reimbursements", headers=login(env, "ana")).json() == []


def test_cenario_02_gestor_de_outro_departamento(env):
    rid = submitted(env, "bruno")                                       # Tecnologia
    assert approve(env, "patricia", rid).status_code == 403             # gestora do Comercial
    assert env.post(f"/reimbursements/{rid}/reject", headers=login(env, "patricia"),
                    json={"justification": "não gostei"}).status_code == 403
    assert env.get(f"/reimbursements/{rid}", headers=login(env, "tiago")).json()["status"] == "PENDING_MANAGER"  # intacta


def test_cenario_03_credenciais_incorretas(env):
    wrong_pwd = env.post("/auth/login", data={"username": "ana@nexus.com", "password": "errada"})
    unknown = env.post("/auth/login", data={"username": "ninguem@nexus.com", "password": "errada"})
    assert wrong_pwd.status_code == unknown.status_code == 401
    assert wrong_pwd.json() == unknown.json()                           # não revela se o e-mail existe
    assert "access_token" not in wrong_pwd.text


def test_cenario_04_tentativa_de_elevacao_de_permissao(env):
    ana = login(env, "ana")
    # (a) atualização de cadastro tentando virar financeiro / mudar departamento
    r = env.patch("/me", headers=ana, json={"role": "FINANCE", "department_id": 3})
    assert r.status_code == 403
    me = env.get("/me", headers=ana).json()
    assert me["role"] == "EMPLOYEE" and me["department_id"] == 1
    # (b) criar solicitação forjando solicitante/departamento/situação
    r = env.post("/reimbursements", headers=ana,
                 json=payload(requester_id=99, department_id=3, status="APPROVED"))
    assert r.status_code == 422
    # (c) endpoints administrativos e de financeiro continuam fechados
    assert env.post("/admin/users", headers=ana, json={"name": "X", "email": "x@x.com", "password": "Senha@Forte123",
                                                        "role": "FINANCE", "department_id": 3}).status_code == 403
    assert env.patch("/admin/users/4", headers=ana, json={"role": "FINANCE"}).status_code == 403
    assert env.get("/me", headers=ana).json()["role"] == "EMPLOYEE"
    assert any(e["action"] == "PRIVILEGE_ESCALATION_ATTEMPT"
               for e in env.get("/audit", headers=login(env, "admin")).json())


def test_cenario_05_aprovacao_fora_da_sequencia(env):
    rid = submitted(env, "ana")                                         # aguardando gestor
    assert approve(env, "fabio", rid).status_code == 403                # financeiro não pode aprovar antes
    assert pay(env, "fabio", rid).status_code == 403                    # nem pagar
    assert env.get(f"/reimbursements/{rid}", headers=login(env, "ana")).json()["status"] == "PENDING_MANAGER"


def test_cenario_06_manipulacao_apos_envio(env):
    rid = submitted(env, "ana", amount="180.00")
    ana = login(env, "ana")
    r = env.put(f"/reimbursements/{rid}", json=payload(amount="1800.00"), headers=ana)
    assert r.status_code == 409
    assert env.get(f"/reimbursements/{rid}", headers=ana).json()["amount"] == "180.00"
    assert env.delete(f"/reimbursements/{rid}", headers=ana).status_code == 409
    # mesmo adulterando direto no banco, a aprovação é barrada pelo hash do conteúdo enviado
    with engine.begin() as c:
        c.execute(text("UPDATE reimbursement_requests SET amount_cents=180000 WHERE id=:i"), {"i": rid})
    r = approve(env, "patricia", rid)
    assert r.status_code == 409 and "integridade" in r.json()["detail"]


def test_cenario_07_consulta_com_filtros(env):
    a = submitted(env, "ana", receipt="C-1")
    b = submitted(env, "bruno", receipt="T-1")
    rascunho = draft(env, "carlos", receipt="C-2")
    pat = login(env, "patricia")
    rows = env.get("/reimbursements?status=PENDING_MANAGER", headers=pat).json()
    assert [r["id"] for r in rows] == [a]                               # só Comercial, só pendentes, sem rascunhos
    assert all(r["department"]["name"] == "Comercial" for r in rows)
    # tentar "forçar" outro departamento pelo filtro não amplia o acesso
    assert env.get("/reimbursements?department_id=2", headers=pat).json() == []
    assert b not in [r["id"] for r in env.get("/reimbursements", headers=pat).json()]
    assert rascunho not in [r["id"] for r in env.get("/reimbursements", headers=pat).json()]


def test_cenario_08_historico_completo(env):
    rid = submitted(env, "ana")
    assert approve(env, "patricia", rid, "Conferido").json()["status"] == "PENDING_FINANCE"
    assert approve(env, "fabio", rid, "Valor ok").json()["status"] == "APPROVED"
    assert pay(env, "fernanda", rid, "PIX-777").json()["status"] == "PAID"
    h = env.get(f"/reimbursements/{rid}/history", headers=login(env, "ana")).json()
    assert [(x["stage"], x["decision"], x["actor"]["name"], x["comment"]) for x in h] == [
        ("SUBMISSION", "SUBMITTED", "Ana Colaboradora", None),
        ("MANAGER", "APPROVED", "Patrícia Gestora", "Conferido"),
        ("FINANCE", "APPROVED", "Fábio Financeiro", "Valor ok"),
        ("PAYMENT", "PAID", "Fernanda Financeiro", "ref: PIX-777")]
    assert all(x["created_at"] for x in h) and len({x["content_hash"] for x in h}) == 1
