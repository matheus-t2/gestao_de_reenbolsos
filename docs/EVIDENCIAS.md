# Evidências de execução – NexusCorp Reembolsos
_Gerado automaticamente por `scripts/demo_cenarios.py` em 2026-11-22 16:10 UTC, contra a API real e um banco SQLite em arquivo. Usuários: ver `seed.py`._

## 0. Preparação e identificação (RN01)
**Acesso sem identificação**
```http
GET /reimbursements    [sem credenciais]
→ HTTP 401
{
  "detail": "Not authenticated"
}
```
**Bruno (Tecnologia) cria rascunho**
```http
POST /reimbursements    [Bearer *** (bruno)]
{"category": "TRANSPORT", "amount": "321.55", "expense_date": "2026-11-01", "justification": "Almoço com cliente durante visita técnica", "receipt_reference": "NF-TEC-001"}
→ HTTP 201
{
  "id": 1,
  "requester": {
    "id": 6,
    "name": "Bruno Colaborador"
  },
  "department": {
    "id": 2,
    "name": "Tecnologia"
  },
  "category": "TRANSPORT",
  "amount": "321.55",
  "expense_date": "2026-11-01",
  "status": "DRAFT",
  "justification": "Almoço com cliente durante visita técnica",
  "receipt_reference": "NF-TEC-001",
  "created_at": "2026-11-22T16:10:04.989369",
  "updated_at": "2026-11-22T16:10:04.989375",
  "submitted_at": null,
  "version": 1,
  "allowed_actions": [
    "edit",
    "delete",
    "submit"
  ]
}
```
**Bruno envia para o gestor**
```http
POST /reimbursements/1/submit    [Bearer *** (bruno)]
→ HTTP 200
{
  "id": 1,
  "requester": {
    "id": 6,
    "name": "Bruno Colaborador"
  },
  "department": {
    "id": 2,
    "name": "Tecnologia"
  },
  "category": "TRANSPORT",
  "amount": "321.55",
  "expense_date": "2026-11-01",
  "status": "PENDING_MANAGER",
  "justification": "Almoço com cliente durante visita técnica",
  "receipt_reference": "NF-TEC-001",
  "created_at": "2026-11-22T16:10:04.989369",
  "updated_at": "2026-11-22T16:10:04.997658",
  "submitted_at": "2026-11-22T16:10:04.997653",
  "version": 2,
  "allowed_actions": []
}
```
**Ana (Comercial) cria rascunho**
```http
POST /reimbursements    [Bearer *** (ana)]
{"category": "FOOD", "amount": "180.00", "expense_date": "2026-11-01", "justification": "Almoço com cliente durante visita técnica", "receipt_reference": "NF-COM-001"}
→ HTTP 201
{
  "id": 2,
  "requester": {
    "id": 4,
    "name": "Ana Colaboradora"
  },
  "department": {
    "id": 1,
    "name": "Comercial"
  },
  "category": "FOOD",
  "amount": "180.00",
  "expense_date": "2026-11-01",
  "status": "DRAFT",
  "justification": "Almoço com cliente durante visita técnica",
  "receipt_reference": "NF-COM-001",
  "created_at": "2026-11-22T16:10:05.068112",
  "updated_at": "2026-11-22T16:10:05.068118",
  "submitted_at": null,
  "version": 1,
  "allowed_actions": [
    "edit",
    "delete",
    "submit"
  ]
}
```
**Ana envia para o gestor**
```http
POST /reimbursements/2/submit    [Bearer *** (ana)]
→ HTTP 200
{
  "id": 2,
  "requester": {
    "id": 4,
    "name": "Ana Colaboradora"
  },
  "department": {
    "id": 1,
    "name": "Comercial"
  },
  "category": "FOOD",
  "amount": "180.00",
  "expense_date": "2026-11-01",
  "status": "PENDING_MANAGER",
  "justification": "Almoço com cliente durante visita técnica",
  "receipt_reference": "NF-COM-001",
  "created_at": "2026-11-22T16:10:05.068112",
  "updated_at": "2026-11-22T16:10:05.073340",
  "submitted_at": "2026-11-22T16:10:05.073335",
  "version": 2,
  "allowed_actions": []
}
```

## Cenário 01 — Acesso indevido
_Esperado: Ana não acessa a solicitação de Bruno; nenhum dado financeiro na resposta._
**Ana tenta ler a solicitação de Bruno pelo identificador**
```http
GET /reimbursements/1    [Bearer *** (ana)]
→ HTTP 403
{
  "detail": "Você não tem permissão para acessar esta solicitação."
}
```
**…e o histórico**
```http
GET /reimbursements/1/history    [Bearer *** (ana)]
→ HTTP 403
{
  "detail": "Você não tem permissão para acessar esta solicitação."
}
```
**Listagem da Ana mostra apenas o que é dela**
```http
GET /reimbursements    [Bearer *** (ana)]
→ HTTP 200
[
  {
    "id": 2,
    "requester": {
      "id": 4,
      "name": "Ana Colaboradora"
    },
    "department": {
      "id": 1,
      "name": "Comercial"
    },
    "category": "FOOD",
    "amount": "180.00",
    "expense_date": "2026-11-01",
    "status": "PENDING_MANAGER"
  }
]
```

## Cenário 02 — Gestor de outro departamento
_Esperado: Patrícia (Comercial) não aprova despesa de Tecnologia._
**Patrícia tenta aprovar a despesa de Bruno**
```http
POST /reimbursements/1/approve    [Bearer *** (patricia)]
{"comment": "ok"}
→ HTTP 403
{
  "detail": "Você não tem permissão para acessar esta solicitação."
}
```
**…ou recusar**
```http
POST /reimbursements/1/reject    [Bearer *** (patricia)]
{"justification": "teste"}
→ HTTP 403
{
  "detail": "Você não tem permissão para acessar esta solicitação."
}
```
**Estado preservado (conferido pelo gestor de Tecnologia): continua PENDING_MANAGER**
```http
GET /reimbursements/1    [Bearer *** (tiago)]
→ HTTP 200
{
  "id": 1,
  "requester": {
    "id": 6,
    "name": "Bruno Colaborador"
  },
  "department": {
    "id": 2,
    "name": "Tecnologia"
  },
  "category": "TRANSPORT",
  "amount": "321.55",
  "expense_date": "2026-11-01",
  "status": "PENDING_MANAGER",
  "justification": "Almoço com cliente durante visita técnica",
  "receipt_reference": "NF-TEC-001",
  "created_at": "2026-11-22T16:10:04.989369",
  "updated_at": "2026-11-22T16:10:04.997658",
  "submitted_at": "2026-11-22T16:10:04.997653",
  "version": 2,
  "allowed_actions": [
    "approve",
    "reject"
  ]
}
```

## Cenário 03 — Credenciais incorretas
_Esperado: mesma resposta genérica para senha errada e e-mail inexistente._
**Senha incorreta**
```http
POST /auth/login    [sem credenciais]
{"username": "ana@nexus.com", "password": "***"}
→ HTTP 401
{
  "detail": "Credenciais inválidas."
}
```
**E-mail inexistente**
```http
POST /auth/login    [sem credenciais]
{"username": "inexistente@nexus.com", "password": "***"}
→ HTTP 401
{
  "detail": "Credenciais inválidas."
}
```

## Cenário 04 — Tentativa de alteração de permissões
_Esperado: nenhuma alteração efetivada._
**Ana tenta virar Financeiro pela atualização de cadastro**
```http
PATCH /me    [Bearer *** (ana)]
{"role": "FINANCE", "department_id": 3}
→ HTTP 403
{
  "detail": "Perfil, departamento e demais vínculos não podem ser alterados por esta operação."
}
```
**Perfil e departamento continuam os mesmos**
```http
GET /me    [Bearer *** (ana)]
→ HTTP 200
{
  "id": 4,
  "name": "Ana Colaboradora",
  "email": "ana@nexus.com",
  "role": "EMPLOYEE",
  "department_id": 1,
  "active": true
}
```
**Ana forja solicitante/departamento/situação no corpo de uma solicitação**
```http
POST /reimbursements    [Bearer *** (ana)]
{"category": "FOOD", "amount": "180.00", "expense_date": "2026-11-01", "justification": "Almoço com cliente durante visita técnica", "receipt_reference": "NF-FORJADA", "requester_id": 1, "department_id": 3, "status": "APPROVED"}
→ HTTP 422
{
  "detail": [
    {
      "type": "extra_forbidden",
      "loc": [
        "body",
        "requester_id"
      ],
      "msg": "Extra inputs are not permitted",
      "input": 1
    },
    {
      "type": "extra_forbidden",
      "loc": [
        "body",
        "department_id"
      ],
      "msg": "Extra inputs are not permitted",
      "input": 3
    },
    {
      "type": "extra_forbidden",
      "loc": [
        "body",
        "status"
      ],
      "msg": "Extra inputs are not permitted",
      "input": "APPROVED"
    }
  ]
}
```
**Ana tenta usar a rota administrativa**
```http
PATCH /admin/users/4    [Bearer *** (ana)]
{"role": "FINANCE"}
→ HTTP 403
{
  "detail": "Perfil sem permissão para esta operação."
}
```

## Cenário 05 — Aprovação fora da sequência
_Esperado: Financeiro não aprova nem paga solicitação que aguarda o gestor._
**Fábio (Financeiro) tenta aprovar solicitação da Ana**
```http
POST /reimbursements/2/approve    [Bearer *** (fabio)]
{"comment": "adiantando"}
→ HTTP 403
{
  "detail": "Você não tem permissão para acessar esta solicitação."
}
```
**…ou pagar**
```http
POST /reimbursements/2/pay    [Bearer *** (fabio)]
{"payment_reference": "PIX-1"}
→ HTTP 403
{
  "detail": "Você não tem permissão para acessar esta solicitação."
}
```

## Cenário 06 — Manipulação de solicitação (R$ 180,00 → R$ 1.800,00)
_Esperado: valor original preservado._
**Ana tenta alterar o valor após o envio**
```http
PUT /reimbursements/2    [Bearer *** (ana)]
{"category": "FOOD", "amount": "1800.00", "expense_date": "2026-11-01", "justification": "Almoço com cliente durante visita técnica", "receipt_reference": "NF-COM-001"}
→ HTTP 409
{
  "detail": "A solicitação já foi enviada e não pode mais ser alterada ou excluída."
}
```
**…ou excluir**
```http
DELETE /reimbursements/2    [Bearer *** (ana)]
→ HTTP 409
{
  "detail": "A solicitação já foi enviada e não pode mais ser alterada ou excluída."
}
```
**Valor continua 180.00**
```http
GET /reimbursements/2    [Bearer *** (ana)]
→ HTTP 200
{
  "id": 2,
  "requester": {
    "id": 4,
    "name": "Ana Colaboradora"
  },
  "department": {
    "id": 1,
    "name": "Comercial"
  },
  "category": "FOOD",
  "amount": "180.00",
  "expense_date": "2026-11-01",
  "status": "PENDING_MANAGER",
  "justification": "Almoço com cliente durante visita técnica",
  "receipt_reference": "NF-COM-001",
  "created_at": "2026-11-22T16:10:05.068112",
  "updated_at": "2026-11-22T16:10:05.073340",
  "submitted_at": "2026-11-22T16:10:05.073335",
  "version": 2,
  "allowed_actions": []
}
```

## Cenário 07 — Consulta com filtros
_Esperado: gestor vê apenas pendências do próprio departamento._
**(Ana cria um rascunho — não deve aparecer para o gestor)**
```http
POST /reimbursements    [Bearer *** (ana)]
{"category": "FOOD", "amount": "180.00", "expense_date": "2026-11-01", "justification": "Almoço com cliente durante visita técnica", "receipt_reference": "NF-COM-RASCUNHO"}
→ HTTP 201
{
  "id": 3,
  "requester": {
    "id": 4,
    "name": "Ana Colaboradora"
  },
  "department": {
    "id": 1,
    "name": "Comercial"
  },
  "category": "FOOD",
  "amount": "180.00",
  "expense_date": "2026-11-01",
  "status": "DRAFT",
  "justification": "Almoço com cliente durante visita técnica",
  "receipt_reference": "NF-COM-RASCUNHO",
  "created_at": "2026-11-22T16:10:05.465288",
  "updated_at": "2026-11-22T16:10:05.465293",
  "submitted_at": null,
  "version": 1,
  "allowed_actions": [
    "edit",
    "delete",
    "submit"
  ]
}
```
**Patrícia consulta as pendentes de decisão**
```http
GET /reimbursements?status=PENDING_MANAGER    [Bearer *** (patricia)]
→ HTTP 200
[
  {
    "id": 2,
    "requester": {
      "id": 4,
      "name": "Ana Colaboradora"
    },
    "department": {
      "id": 1,
      "name": "Comercial"
    },
    "category": "FOOD",
    "amount": "180.00",
    "expense_date": "2026-11-01",
    "status": "PENDING_MANAGER"
  }
]
```
**Patrícia tenta forçar o filtro de outro departamento**
```http
GET /reimbursements?department_id=2    [Bearer *** (patricia)]
→ HTTP 200
[]
```
**Tiago (Tecnologia) com filtros de situação e categoria**
```http
GET /reimbursements?status=PENDING_MANAGER&category=TRANSPORT    [Bearer *** (tiago)]
→ HTTP 200
[
  {
    "id": 1,
    "requester": {
      "id": 6,
      "name": "Bruno Colaborador"
    },
    "department": {
      "id": 2,
      "name": "Tecnologia"
    },
    "category": "TRANSPORT",
    "amount": "321.55",
    "expense_date": "2026-11-01",
    "status": "PENDING_MANAGER"
  }
]
```

## Cenário 08 — Histórico financeiro (gestor → financeiro → pagamento)
**Patrícia aprova**
```http
POST /reimbursements/2/approve    [Bearer *** (patricia)]
{"comment": "Conferido com a agenda do cliente"}
→ HTTP 200
{
  "id": 2,
  "requester": {
    "id": 4,
    "name": "Ana Colaboradora"
  },
  "department": {
    "id": 1,
    "name": "Comercial"
  },
  "category": "FOOD",
  "amount": "180.00",
  "expense_date": "2026-11-01",
  "status": "PENDING_FINANCE",
  "justification": "Almoço com cliente durante visita técnica",
  "receipt_reference": "NF-COM-001",
  "created_at": "2026-11-22T16:10:05.068112",
  "updated_at": "2026-11-22T16:10:05.483302",
  "submitted_at": "2026-11-22T16:10:05.073335",
  "version": 3,
  "allowed_actions": []
}
```
**Fábio tenta pagar antes de aprovar (RN10)**
```http
POST /reimbursements/2/pay    [Bearer *** (fabio)]
{"payment_reference": "PIX-0001"}
→ HTTP 409
{
  "detail": "O pagamento só pode ser registrado após a aprovação financeira."
}
```
**Fábio aprova financeiramente**
```http
POST /reimbursements/2/approve    [Bearer *** (fabio)]
{"comment": "Valor dentro da política"}
→ HTTP 200
{
  "id": 2,
  "requester": {
    "id": 4,
    "name": "Ana Colaboradora"
  },
  "department": {
    "id": 1,
    "name": "Comercial"
  },
  "category": "FOOD",
  "amount": "180.00",
  "expense_date": "2026-11-01",
  "status": "APPROVED",
  "justification": "Almoço com cliente durante visita técnica",
  "receipt_reference": "NF-COM-001",
  "created_at": "2026-11-22T16:10:05.068112",
  "updated_at": "2026-11-22T16:10:05.492378",
  "submitted_at": "2026-11-22T16:10:05.073335",
  "version": 4,
  "allowed_actions": [
    "pay"
  ]
}
```
**Fernanda registra o pagamento**
```http
POST /reimbursements/2/pay    [Bearer *** (fernanda)]
{"payment_reference": "PIX-0001"}
→ HTTP 200
{
  "id": 2,
  "requester": {
    "id": 4,
    "name": "Ana Colaboradora"
  },
  "department": {
    "id": 1,
    "name": "Comercial"
  },
  "category": "FOOD",
  "amount": "180.00",
  "expense_date": "2026-11-01",
  "status": "PAID",
  "justification": "Almoço com cliente durante visita técnica",
  "receipt_reference": "NF-COM-001",
  "created_at": "2026-11-22T16:10:05.068112",
  "updated_at": "2026-11-22T16:10:05.562771",
  "submitted_at": "2026-11-22T16:10:05.073335",
  "version": 5,
  "allowed_actions": []
}
```
**Histórico completo, visível à solicitante**
```http
GET /reimbursements/2/history    [Bearer *** (ana)]
→ HTTP 200
[
  {
    "id": 2,
    "actor": {
      "id": 4,
      "name": "Ana Colaboradora"
    },
    "actor_role": "EMPLOYEE",
    "stage": "SUBMISSION",
    "decision": "SUBMITTED",
    "comment": null,
    "from_status": "DRAFT",
    "to_status": "PENDING_MANAGER",
    "content_hash": "60c9804123f972bf6f85a508b4ef499d0ee2748f056b93ac7467c5d0b60520b8",
    "created_at": "2026-11-22T16:10:05.074183"
  },
  {
    "id": 3,
    "actor": {
      "id": 1,
      "name": "Patrícia Gestora"
    },
    "actor_role": "MANAGER",
    "stage": "MANAGER",
    "decision": "APPROVED",
    "comment": "Conferido com a agenda do cliente",
    "from_status": "PENDING_MANAGER",
    "to_status": "PENDING_FINANCE",
    "content_hash": "60c9804123f972bf6f85a508b4ef499d0ee2748f056b93ac7467c5d0b60520b8",
    "created_at": "2026-11-22T16:10:05.484731"
  },
  {
    "id": 4,
    "actor": {
      "id": 7,
      "name": "Fábio Financeiro"
    },
    "actor_role": "FINANCE",
    "stage": "FINANCE",
    "decision": "APPROVED",
    "comment": "Valor dentro da política",
    "from_status": "PENDING_FINANCE",
    "to_status": "APPROVED",
    "content_hash": "60c9804123f972bf6f85a508b4ef499d0ee2748f056b93ac7467c5d0b60520b8",
    "created_at": "2026-11-22T16:10:05.493620"
  },
  {
    "id": 5,
    "actor": {
      "id": 8,
      "name": "Fernanda Financeiro"
    },
    "actor_role": "FINANCE",
    "stage": "PAYMENT",
    "decision": "PAID",
    "comment": "ref: PIX-0001",
    "from_status": "APPROVED",
    "to_status": "PAID",
    "content_hash": "60c9804123f972bf6f85a508b4ef499d0ee2748f056b93ac7467c5d0b60520b8",
    "created_at": "2026-11-22T16:10:05.563602"
  }
]
```

## Fluxo de recusa (RN11)
**Patrícia cria despesa própria**
```http
POST /reimbursements    [Bearer *** (patricia)]
{"category": "MATERIALS", "amount": "75.00", "expense_date": "2026-11-01", "justification": "Almoço com cliente durante visita técnica", "receipt_reference": "NF-COM-003"}
→ HTTP 201
{
  "id": 4,
  "requester": {
    "id": 1,
    "name": "Patrícia Gestora"
  },
  "department": {
    "id": 1,
    "name": "Comercial"
  },
  "category": "MATERIALS",
  "amount": "75.00",
  "expense_date": "2026-11-01",
  "status": "DRAFT",
  "justification": "Almoço com cliente durante visita técnica",
  "receipt_reference": "NF-COM-003",
  "created_at": "2026-11-22T16:10:05.573845",
  "updated_at": "2026-11-22T16:10:05.573851",
  "submitted_at": null,
  "version": 1,
  "allowed_actions": [
    "edit",
    "delete",
    "submit"
  ]
}
```
**Patrícia envia**
```http
POST /reimbursements/4/submit    [Bearer *** (patricia)]
→ HTTP 200
{
  "id": 4,
  "requester": {
    "id": 1,
    "name": "Patrícia Gestora"
  },
  "department": {
    "id": 1,
    "name": "Comercial"
  },
  "category": "MATERIALS",
  "amount": "75.00",
  "expense_date": "2026-11-01",
  "status": "PENDING_MANAGER",
  "justification": "Almoço com cliente durante visita técnica",
  "receipt_reference": "NF-COM-003",
  "created_at": "2026-11-22T16:10:05.573845",
  "updated_at": "2026-11-22T16:10:05.579090",
  "submitted_at": "2026-11-22T16:10:05.579085",
  "version": 2,
  "allowed_actions": []
}
```
**Patrícia não aprova a própria solicitação (RN09)**
```http
POST /reimbursements/4/approve    [Bearer *** (patricia)]
→ HTTP 403
{
  "detail": "Você não é o responsável por analisar esta solicitação nesta etapa."
}
```
**Ana cria e envia outra despesa**
```http
POST /reimbursements    [Bearer *** (ana)]
{"category": "FOOD", "amount": "50.00", "expense_date": "2026-11-01", "justification": "Almoço com cliente durante visita técnica", "receipt_reference": "NF-COM-004"}
→ HTTP 201
{
  "id": 5,
  "requester": {
    "id": 4,
    "name": "Ana Colaboradora"
  },
  "department": {
    "id": 1,
    "name": "Comercial"
  },
  "category": "FOOD",
  "amount": "50.00",
  "expense_date": "2026-11-01",
  "status": "DRAFT",
  "justification": "Almoço com cliente durante visita técnica",
  "receipt_reference": "NF-COM-004",
  "created_at": "2026-11-22T16:10:05.589527",
  "updated_at": "2026-11-22T16:10:05.589532",
  "submitted_at": null,
  "version": 1,
  "allowed_actions": [
    "edit",
    "delete",
    "submit"
  ]
}
```

```http
POST /reimbursements/5/submit    [Bearer *** (ana)]
→ HTTP 200
{
  "id": 5,
  "requester": {
    "id": 4,
    "name": "Ana Colaboradora"
  },
  "department": {
    "id": 1,
    "name": "Comercial"
  },
  "category": "FOOD",
  "amount": "50.00",
  "expense_date": "2026-11-01",
  "status": "PENDING_MANAGER",
  "justification": "Almoço com cliente durante visita técnica",
  "receipt_reference": "NF-COM-004",
  "created_at": "2026-11-22T16:10:05.589527",
  "updated_at": "2026-11-22T16:10:05.594513",
  "submitted_at": "2026-11-22T16:10:05.594509",
  "version": 2,
  "allowed_actions": []
}
```
**Recusa sem justificativa**
```http
POST /reimbursements/5/reject    [Bearer *** (patricia)]
→ HTTP 422
{
  "detail": [
    {
      "type": "missing",
      "loc": [
        "body",
        "justification"
      ],
      "msg": "Field required",
      "input": {}
    }
  ]
}
```
**Recusa com justificativa**
```http
POST /reimbursements/5/reject    [Bearer *** (patricia)]
{"justification": "Comprovante ilegível"}
→ HTTP 200
{
  "id": 5,
  "requester": {
    "id": 4,
    "name": "Ana Colaboradora"
  },
  "department": {
    "id": 1,
    "name": "Comercial"
  },
  "category": "FOOD",
  "amount": "50.00",
  "expense_date": "2026-11-01",
  "status": "REJECTED",
  "justification": "Almoço com cliente durante visita técnica",
  "receipt_reference": "NF-COM-004",
  "created_at": "2026-11-22T16:10:05.589527",
  "updated_at": "2026-11-22T16:10:05.602780",
  "submitted_at": "2026-11-22T16:10:05.594509",
  "version": 3,
  "allowed_actions": []
}
```
**Reuso da mesma referência de comprovante (RN05)**
```http
POST /reimbursements    [Bearer *** (ana)]
{"category": "FOOD", "amount": "50.00", "expense_date": "2026-11-01", "justification": "Almoço com cliente durante visita técnica", "receipt_reference": "nf-com-004"}
→ HTTP 409
{
  "detail": "Você já registrou uma despesa com esta referência de comprovante."
}
```

## Persistência e integridade no banco
**Verificação da cadeia de auditoria (somente ADMIN)**
```http
GET /audit/verify    [Bearer *** (admin)]
→ HTTP 200
{
  "valid": true,
  "checked": 31,
  "first_invalid_id": null
}
```
**Leitura direta do arquivo SQLite (conexão independente da API):**
```
reimbursement_requests: 5 linhas | decisions: 8 linhas
  id=1 status=PENDING_MANAGER amount_cents=32155 version=2
  id=2 status=PAID amount_cents=18000 version=5
  id=3 status=DRAFT amount_cents=18000 version=1
  id=4 status=PENDING_MANAGER amount_cents=7500 version=2
  id=5 status=REJECTED amount_cents=5000 version=3
```
```
decisions (solicitação 2): responsável → etapa → decisão
  2 | Ana Colaboradora | SUBMISSION | SUBMITTED | DRAFT | PENDING_MANAGER | 2026-11-22 16:10:05.074183
  3 | Patrícia Gestora | MANAGER | APPROVED | PENDING_MANAGER | PENDING_FINANCE | 2026-11-22 16:10:05.484731
  4 | Fábio Financeiro | FINANCE | APPROVED | PENDING_FINANCE | APPROVED | 2026-11-22 16:10:05.493620
  5 | Fernanda Financeiro | PAYMENT | PAID | APPROVED | PAID | 2026-11-22 16:10:05.563602
```
