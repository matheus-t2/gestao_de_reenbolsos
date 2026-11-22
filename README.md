# NexusCorp – API de Gestão de Reembolsos

API REST (Python · FastAPI · SQLAlchemy · SQLite/PostgreSQL) com controle de acesso por perfil, fluxo de aprovação em duas etapas, histórico imutável e auditoria.

📄 **Documentação técnica:** [`docs/DOCUMENTACAO.md`](docs/DOCUMENTACAO.md) (modelo de dados, contratos, matriz de permissões, regras RN01–RN15, decisões de segurança)
🧪 **Evidências:** [`docs/EVIDENCIAS.md`](docs/EVIDENCIAS.md) (8 cenários de homologação executados) · [`docs/evidencia_testes.txt`](docs/evidencia_testes.txt) (33 testes)

## Executando
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export NEXUS_JWT_SECRET="$(python -c 'import secrets;print(secrets.token_urlsafe(48))')"
python seed.py                          # cria nexus.db com departamentos e usuários de exemplo
uvicorn app.main:app --reload           # Swagger em http://localhost:8000/docs
```
Usuários de exemplo (senha `Trocar@12345`, ou a definida em `SEED_PASSWORD`):

| E-mail | Perfil | Departamento |
|---|---|---|
| ana@nexus.com, carlos@nexus.com | Colaborador | Comercial |
| bruno@nexus.com | Colaborador | Tecnologia |
| patricia@nexus.com / tiago@nexus.com / marta@nexus.com | Gestor | Comercial / Tecnologia / Financeiro |
| fabio@nexus.com, fernanda@nexus.com | Financeiro | Financeiro |
| admin@nexus.com | Admin (cadastro e auditoria) | Tecnologia |

No Swagger: `POST /auth/login` → copie o `access_token` → botão **Authorize**.

## Testes e evidências
```bash
pytest -v                               # 33 testes: 8 cenários + RN01–RN15 + filtros + auditoria
python scripts/demo_cenarios.py         # reexecuta os cenários e regrava docs/EVIDENCIAS.md
```

## Estrutura
```
app/
  main.py          aplicação, handlers de erro
  models.py        entidades + guardas de integridade (imutabilidade, transições)
  schemas.py       contratos de entrada/saída e validações
  policy.py        quem vê e quem faz o quê (única fonte de verdade)
  services.py      fluxo de aprovação (transações)
  security.py      senha, JWT, dependências de autenticação/perfil
  audit.py         trilha de auditoria encadeada
  routers/         auth, reimbursements, admin, audit
tests/             cenários de homologação e regras de negócio
scripts/           geração das evidências
docs/              documentação técnica e evidências
seed.py            dados de demonstração
```

## Publicando no GitHub
```bash
git remote add origin https://github.com/<usuario>/nexuscorp-reembolsos.git
git push -u origin main
```
