# Guia de integração — app (Pina) e site (Matheus)

URL base local: `http://localhost:4000` (sem prefixo; concatene `baseUrl + path`).
Manual completo, com exemplos de cada corpo: `http://localhost:4000/docs`.

## 1. Login e refresh

```http
POST /auth/login
{"login": "RL-8842", "password": "..."}        ← matrícula OU e-mail (também aceita usuario/senha)
```
Resposta `200`:
```json
{
  "access_token": "eyJ...", "refresh_token": "eyJ...", "token_type": "bearer",
  "expires_at": "2026-10-21T22:15:00Z", "refresh_expires_at": "2026-10-28T22:00:00Z",
  "user": {"id": "...", "name": "Ana Giulia", "registration": "RL-8842", "role": "tecnico", ...}
}
```
- Envie `Authorization: Bearer <access_token>` em todas as rotas (exceto login, refresh,
  aceite de convite e `/monitoramento/status`).
- O access vale **15 min**. Ao receber `401` com `code: "token_expired"` (ou um pouco antes de
  `expires_at`), chame `POST /auth/refresh {"refresh_token": "..."}` → novo par. O refresh vale
  **7 dias**; se ele também expirar, volte para a tela de login.
- O papel vem do banco a cada requisição: trocar o papel de alguém vale na hora.
- Fase 1 **não tem MFA**: `/auth/mfa` e `/auth/mfa-offline` devolvem `501 not_implemented`.
  Na fase 2 o login passará a devolver um `tempToken` (formato ainda A DECIDIR).

## 2. Formato de erro

Todo erro tem o mesmo corpo:
```json
{"detail": "Dormente descartado não movimenta.", "code": "sleeper_discarded"}
```
- `detail` é texto para mostrar; **`code` é estável** — use-o para decidir o fluxo.
- `422` traz também `errors: [{loc, msg, type}]` com os campos inválidos.

| HTTP | `code` | Quando |
|---|---|---|
| 401 | `unauthorized`, `invalid_token`, `token_expired`, `inactive_user`, `invalid_credentials` | Sem token, token ruim/expirado, usuário desativado, login errado |
| 403 | `forbidden` | Papel sem permissão |
| 404 | `not_found`, `sleeper_not_found`, `species_not_found`, `location_not_found`, `inspection_not_found` | Recurso inexistente |
| 409 | `email_taken`, `registration_taken`, `rfid_tag_taken`, `species_code_taken`, `location_name_taken`, `last_admin` | Conflito de unicidade |
| 409 | `sleeper_discarded`, `sleeper_quarantined`, `not_in_stock`, `already_in_yard`, `not_in_yard`, `same_location`, `invalid_status_transition`, `location_inactive`, `species_inactive` | Regra de negócio |
| 422 | `validation_error`, `future_timestamp`, `invalid_period`, `period_too_long`, `location_required`, `registration_required` | Dados inválidos |
| 501 | `not_implemented` | Fase 2 |

## 3. Paginação e filtros

Listagens aceitam `?limit=` (padrão 50, máx. 200) e `?offset=` e respondem:
```json
{"items": [...], "total": 137, "limit": 50, "offset": 0}
```
Período: `?de=2026-10-01T00:00:00Z&ate=2026-10-08T00:00:00Z` (`de` inclusivo, `ate`
exclusivo; sem fuso = UTC). Datas sempre em **UTC**; a conversão de fuso é do front.

## 4. App: leitura de tag

1. Leu a tag → `GET /dormentes/tag/{tag}`.
2. `200` → dormente conhecido (status, local, espécie). `404` com `code: "sleeper_not_found"` →
   abrir o cadastro e enviar `POST /dormentes` (exige `location_id`; já registra a entrada).
3. A tag é normalizada (sem espaços, maiúsculas): `e280 ...` e `E280...` são a mesma.

Regras de status que o app deve respeitar (a API rejeita com `409` se não):

| Operação | Exige | Resultado |
|---|---|---|
| Entrada (`entry`) | dormente fora do pátio (sem local) + `to_location_id` | `in_stock` no local |
| Retirada (`withdrawal`) | `in_stock` + `requisition_number` (RM) | `withdrawn`, sem local |
| Transferência (`transfer`) | dormente no pátio + `to_location_id` diferente do atual | muda o local |
| `/estoque/localizacao` | `location_id` | vira transferência (tem local) ou entrada (não tem) |
| Inspeção reprovada | técnico+ | `quarantine` |
| Inspeção aprovada | técnico+ | libera `quarantine` → `in_stock` se estiver no pátio |
| Qualquer | — | `discarded` não movimenta nem é inspecionado |

## 5. App: sincronização offline

Cada registro criado offline leva `client_uuid` (UUID v4 gerado no aparelho) e a data do evento
(`occurred_at`, ou `inspected_at`/`counted_at`). Ao reconectar:

```http
POST /sincronizacao/replicar
{
  "device_id": "coletor-07",
  "movements":        [ {"client_uuid": "...", "rfid_tag": "E280...", "kind": "transfer", "to_location_id": "...", "occurred_at": "..."} ],
  "inspections":      [ {"client_uuid": "...", "rfid_tag": "E280...", "inspected_at": "...", "conservation": "good", "has_cracks": false, "biological_attack": false, "moisture": "dry", "result": "approved", "duration_seconds": 80} ],
  "occurrences":      [ {"client_uuid": "...", "rfid_tag": "E280...", "kind": "damage", "description": "...", "occurred_at": "..."} ],
  "inventory_counts": [ {"client_uuid": "...", "location_id": "...", "species_id": "...", "quantity": 42, "read_tags": ["E280..."], "counted_at": "..."} ]
}
```
- Cada item tem o **mesmo formato** do POST direto correspondente, com `client_uuid` obrigatório.
  O dormente pode ser referenciado por `rfid_tag` ou `sleeper_id`.
- Até **1000 itens** por lote; acima disso divida em partes.
- A resposta é sempre `200` e traz um resultado por item, com `type` + `index` (posição na lista
  de origem):
  ```json
  {"status": "partial", "accepted": 1, "duplicate": 1, "rejected": 1, "results": [
    {"type": "movement", "index": 0, "client_uuid": "...", "status": "accepted", "id": "..."},
    {"type": "inspection", "index": 0, "client_uuid": "...", "status": "duplicate", "id": "..."},
    {"type": "movement", "index": 1, "client_uuid": "...", "status": "rejected",
     "code": "sleeper_discarded", "reason": "Dormente descartado não movimenta."}
  ]}
  ```
- `accepted` e `duplicate` → pode apagar do cache local. `rejected` → mostrar `reason` ao operador;
  reenviar não adianta sem corrigir o dado.
- **Reenviar o mesmo lote é seguro** (ex.: caiu a conexão antes da resposta): tudo volta `duplicate`.
- Um item ruim não derruba o lote. Os itens são aplicados em **ordem cronológica do evento**,
  misturando as listas (ex.: inspeção reprovada às 9h barra a retirada das 10h).
- Inspeções só são aceitas de técnico/especialista/admin; de operador voltam `rejected`/`forbidden`.
- `GET /sincronizacao/status?device_id=coletor-07` → último lote (`last_batch` ou `null`) e
  `server_time`, útil para mostrar "atualizado há X min".
- Os POSTs diretos (`/estoque/...`, `/inspecoes`, `/dormentes`) também são idempotentes por
  `client_uuid`: `201` quando cria, `200` quando é reenvio.

## 6. Site: mapeamento dos `ENDPOINTS` (src/App.jsx)

| `ENDPOINTS` do site | Rota real | Observação |
|---|---|---|
| `POST /auth/login` | igual | Fase 1 devolve os tokens direto (não há `tempToken` ainda) |
| `POST /auth/mfa` | igual | `501 not_implemented` até a fase 2 |
| `POST /auth/mfa-offline` | igual | `501 not_implemented` até a fase 2 |
| `GET /usuarios` | igual | Paginado: `{items, total, limit, offset}`; supervisor e admin |
| `POST /usuarios` | igual | `{name, email, registration, password, role}` (aceita `nome`, `matricula`, `senha`, `papel`) |
| `PATCH /usuarios/:id/papel` | `PATCH /usuarios/{id}/papel` | `{role}` ou `{papel}` |
| `POST /usuarios/convite` | igual | Ver ajustes abaixo |
| `POST /estoque/movimentacao` | igual | |
| `POST /estoque/inventario` | igual | |
| `POST /estoque/localizacao` | igual | |
| `POST /estoque/ocorrencias` | igual | Listagem em `GET /estoque/ocorrencias` |
| `POST /sincronizacao/replicar` | igual | |
| `GET /sincronizacao/status` | igual | Exige login |
| `GET /monitoramento/status` | igual | Sem login; `email_configured` indica e-mail real (hoje `false`); `503` se o banco cair |
| `GET /logs` | igual | Paginado; supervisor e admin |

Rotas novas úteis para o site: `/indicadores` (dashboard), `/dormentes` (+ `/tag/{tag}`,
`/{id}/historico`), `/especies`, `/locais`, `/inspecoes`, `/estoque/movimentacoes`,
`/estoque/inventarios`, `/auth/me`, `/auth/refresh`.

### Ajustes necessários no site
1. **Convite exige login de admin.** O `InviteSection` chama `POST /usuarios/convite` sem
   `Authorization`; precisa enviar o Bearer, senão recebe `401`.
2. **Corpo do convite:** `{nome, email, papel, link}` continua aceito, mas:
   - `papel` precisa ser um dos papéis do RBAC: `operador`, `tecnico`, `especialista`,
     `supervisor` ou `admin` (maiúsculas e acentos são ignorados). **`Analista` não existe** → `422`.
   - O `link` enviado é ignorado: a API gera o token e devolve `{token, link, expires_at, ...}`.
     Use o `link` da resposta no `mailto`. A tela de aceite (`/convite/<token>`) chama
     `POST /auth/convite/aceitar {"token", "password", "registration"}`, que cria a conta e já
     devolve os tokens.
   - A base do link vem de `INVITE_BASE_URL` no `.env` da API.
3. **Lista de papéis:** trocar `["Operador", "Analista", "Admin"]` pelos 5 papéis acima.
4. **Login:** hoje é demo (`LOGIN_DEMO`). Para ligar à API: `POST /auth/login`, guardar os tokens,
   tratar `401 invalid_credentials`.

## 7. Pontos em aberto
- **Cadastro de dormente novo offline:** o lote de sync não inclui cadastro de dormente
  (`POST /dormentes` precisa estar online). Movimentar uma tag ainda não cadastrada volta
  `rejected`/`sleeper_not_found`. Se o app precisar cadastrar offline, combinamos um tipo
  `sleepers` no lote.
- Itens **A DECIDIR** do `CONTEXTO.md`: MFA, credencial offline 48h, e-mail de convite,
  conciliação de inventário, deploy.
