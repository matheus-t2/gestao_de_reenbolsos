"""Executa os 8 cenários de homologação contra a API e grava as evidências em docs/EVIDENCIAS.md.
Uso (na raiz do projeto):  python scripts/demo_cenarios.py
Usa um banco SQLite próprio (demo_evidencias.db), recriado a cada execução."""
import json
import os
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DB = ROOT / "demo_evidencias.db"
DB.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{DB}"
os.environ["NEXUS_JWT_SECRET"] = "demo-secret-demo-secret-demo-secret"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from seed import PWD, seed  # noqa: E402

Base.metadata.create_all(engine)
with SessionLocal() as s:
    seed(s)

client = TestClient(app)
out: list[str] = []
tokens: dict[str, str] = {}


def w(txt=""):
    out.append(txt)


def login(who):
    r = client.post("/auth/login", data={"username": f"{who}@nexus.com", "password": PWD})
    tokens[who] = r.json()["access_token"]
    return tokens[who]


def call(who, method, path, body=None, form=None, note=""):
    headers = {}
    if who:
        headers["Authorization"] = f"Bearer {tokens.get(who) or login(who)}"
    r = client.request(method, path, json=body, data=form, headers=headers)
    try:
        resp = json.dumps(r.json(), ensure_ascii=False, indent=2) if r.content else "(sem corpo)"
    except Exception:
        resp = r.text
    shown_body = body if body is not None else (
        {k: ("***" if "pass" in k else v) for k, v in form.items()} if form else None)
    w(f"**{note}**" if note else "")
    w("```http")
    w(f"{method} {path}    [{'Bearer ***' + ' (' + who + ')' if who else 'sem credenciais'}]")
    if shown_body:
        w(json.dumps(shown_body, ensure_ascii=False))
    w(f"→ HTTP {r.status_code}")
    w(resp.replace("access_token", "access_token").replace(tokens.get(who, "@@"), "***") if who else resp)
    w("```")
    return r


def table_counts():
    con = sqlite3.connect(DB)
    q = lambda sql: con.execute(sql).fetchall()
    res = {"solicitacoes": q("select count(*) from reimbursement_requests")[0][0],
           "decisoes": q("select count(*) from decisions")[0][0],
           "snapshot": q("select id,status,amount_cents,version from reimbursement_requests order by id")}
    con.close()
    return res


w("# Evidências de execução – NexusCorp Reembolsos")
w(f"_Gerado automaticamente por `scripts/demo_cenarios.py` em {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC, "
  "contra a API real e um banco SQLite em arquivo. Usuários: ver `seed.py`._")
w()
d = date.today().replace(day=1).isoformat()
nova = lambda ref, valor="180.00", cat="FOOD": {"category": cat, "amount": valor, "expense_date": d,
                                                "justification": "Almoço com cliente durante visita técnica",
                                                "receipt_reference": ref}

# ---------------------------------------------------------------- preparação
w("## 0. Preparação e identificação (RN01)")
call(None, "GET", "/reimbursements", note="Acesso sem identificação")
call("bruno", "POST", "/reimbursements", nova("NF-TEC-001", "321.55", "TRANSPORT"), note="Bruno (Tecnologia) cria rascunho")
call("bruno", "POST", "/reimbursements/1/submit", note="Bruno envia para o gestor")
call("ana", "POST", "/reimbursements", nova("NF-COM-001", "180.00"), note="Ana (Comercial) cria rascunho")
call("ana", "POST", "/reimbursements/2/submit", note="Ana envia para o gestor")

# ---------------------------------------------------------------- cenários
w("\n## Cenário 01 — Acesso indevido")
w("_Esperado: Ana não acessa a solicitação de Bruno; nenhum dado financeiro na resposta._")
call("ana", "GET", "/reimbursements/1", note="Ana tenta ler a solicitação de Bruno pelo identificador")
call("ana", "GET", "/reimbursements/1/history", note="…e o histórico")
call("ana", "GET", "/reimbursements", note="Listagem da Ana mostra apenas o que é dela")

w("\n## Cenário 02 — Gestor de outro departamento")
w("_Esperado: Patrícia (Comercial) não aprova despesa de Tecnologia._")
call("patricia", "POST", "/reimbursements/1/approve", {"comment": "ok"}, note="Patrícia tenta aprovar a despesa de Bruno")
call("patricia", "POST", "/reimbursements/1/reject", {"justification": "teste"}, note="…ou recusar")
call("tiago", "GET", "/reimbursements/1", note="Estado preservado (conferido pelo gestor de Tecnologia): continua PENDING_MANAGER")

w("\n## Cenário 03 — Credenciais incorretas")
w("_Esperado: mesma resposta genérica para senha errada e e-mail inexistente._")
call(None, "POST", "/auth/login", form={"username": "ana@nexus.com", "password": "senha-errada"}, note="Senha incorreta")
call(None, "POST", "/auth/login", form={"username": "inexistente@nexus.com", "password": "qualquer"}, note="E-mail inexistente")

w("\n## Cenário 04 — Tentativa de alteração de permissões")
w("_Esperado: nenhuma alteração efetivada._")
call("ana", "PATCH", "/me", {"role": "FINANCE", "department_id": 3}, note="Ana tenta virar Financeiro pela atualização de cadastro")
call("ana", "GET", "/me", note="Perfil e departamento continuam os mesmos")
call("ana", "POST", "/reimbursements", {**nova("NF-FORJADA"), "requester_id": 1, "department_id": 3, "status": "APPROVED"},
     note="Ana forja solicitante/departamento/situação no corpo de uma solicitação")
call("ana", "PATCH", "/admin/users/4", {"role": "FINANCE"}, note="Ana tenta usar a rota administrativa")

w("\n## Cenário 05 — Aprovação fora da sequência")
w("_Esperado: Financeiro não aprova nem paga solicitação que aguarda o gestor._")
call("fabio", "POST", "/reimbursements/2/approve", {"comment": "adiantando"}, note="Fábio (Financeiro) tenta aprovar solicitação da Ana")
call("fabio", "POST", "/reimbursements/2/pay", {"payment_reference": "PIX-1"}, note="…ou pagar")

w("\n## Cenário 06 — Manipulação de solicitação (R$ 180,00 → R$ 1.800,00)")
w("_Esperado: valor original preservado._")
call("ana", "PUT", "/reimbursements/2", nova("NF-COM-001", "1800.00"), note="Ana tenta alterar o valor após o envio")
call("ana", "DELETE", "/reimbursements/2", note="…ou excluir")
call("ana", "GET", "/reimbursements/2", note="Valor continua 180.00")

w("\n## Cenário 07 — Consulta com filtros")
w("_Esperado: gestor vê apenas pendências do próprio departamento._")
call("ana", "POST", "/reimbursements", nova("NF-COM-RASCUNHO"), note="(Ana cria um rascunho — não deve aparecer para o gestor)")
call("patricia", "GET", "/reimbursements?status=PENDING_MANAGER", note="Patrícia consulta as pendentes de decisão")
call("patricia", "GET", "/reimbursements?department_id=2", note="Patrícia tenta forçar o filtro de outro departamento")
call("tiago", "GET", "/reimbursements?status=PENDING_MANAGER&category=TRANSPORT", note="Tiago (Tecnologia) com filtros de situação e categoria")

w("\n## Cenário 08 — Histórico financeiro (gestor → financeiro → pagamento)")
call("patricia", "POST", "/reimbursements/2/approve", {"comment": "Conferido com a agenda do cliente"}, note="Patrícia aprova")
call("fabio", "POST", "/reimbursements/2/pay", {"payment_reference": "PIX-0001"}, note="Fábio tenta pagar antes de aprovar (RN10)")
call("fabio", "POST", "/reimbursements/2/approve", {"comment": "Valor dentro da política"}, note="Fábio aprova financeiramente")
call("fernanda", "POST", "/reimbursements/2/pay", {"payment_reference": "PIX-0001"}, note="Fernanda registra o pagamento")
call("ana", "GET", "/reimbursements/2/history", note="Histórico completo, visível à solicitante")

w("\n## Fluxo de recusa (RN11)")
call("patricia", "POST", "/reimbursements", nova("NF-COM-003", "75.00", "MATERIALS"), note="Patrícia cria despesa própria")
call("patricia", "POST", "/reimbursements/4/submit", note="Patrícia envia")
call("patricia", "POST", "/reimbursements/4/approve", note="Patrícia não aprova a própria solicitação (RN09)")
call("ana", "POST", "/reimbursements", nova("NF-COM-004", "50.00"), note="Ana cria e envia outra despesa")
call("ana", "POST", "/reimbursements/5/submit")
call("patricia", "POST", "/reimbursements/5/reject", {}, note="Recusa sem justificativa")
call("patricia", "POST", "/reimbursements/5/reject", {"justification": "Comprovante ilegível"}, note="Recusa com justificativa")
call("ana", "POST", "/reimbursements", nova("nf-com-004", "50.00"), note="Reuso da mesma referência de comprovante (RN05)")

# ---------------------------------------------------------------- persistência
w("\n## Persistência e integridade no banco")
admin_audit = call("admin", "GET", "/audit/verify", note="Verificação da cadeia de auditoria (somente ADMIN)")
snap = table_counts()
w("**Leitura direta do arquivo SQLite (conexão independente da API):**")
w("```")
w(f"reimbursement_requests: {snap['solicitacoes']} linhas | decisions: {snap['decisoes']} linhas")
for row in snap["snapshot"]:
    w(f"  id={row[0]} status={row[1]} amount_cents={row[2]} version={row[3]}")
w("```")
con = sqlite3.connect(DB)
w("```")
w("decisions (solicitação 2): responsável → etapa → decisão")
for r in con.execute("select d.id, u.name, d.stage, d.decision, d.from_status, d.to_status, d.created_at "
                     "from decisions d join users u on u.id=d.actor_id where d.request_id=2 order by d.id"):
    w("  " + " | ".join(str(x) for x in r))
w("```")
con.close()

(ROOT / "docs").mkdir(exist_ok=True)
(ROOT / "docs" / "EVIDENCIAS.md").write_text("\n".join(out) + "\n", encoding="utf-8")
DB.unlink(missing_ok=True)
print("Evidências gravadas em docs/EVIDENCIAS.md")
