# Prompt inicial para o Claude Code

> Cole o bloco abaixo no Claude Code, na raiz deste repositório.
> Ele usa o `CLAUDE.md` e o `docs/CONTEXTO.md` como fonte de verdade.

---

Você vai construir a API do Projeto REO/CPTM neste repositório.

**Antes de escrever código:** leia `CLAUDE.md` e `docs/CONTEXTO.md` inteiros.
Depois me mostre um plano curto (arquivos que vai criar por etapa) e espere meu "ok".

**Objetivo da entrega (prazo 23/10):** API da **Fase 1** rodando localmente na porta 4000,
com banco Postgres, migrations, seed, testes passando e documentação OpenAPI completa,
pronta para o app (Expo) e o site (React) se conectarem. Fase 2 fica só com stubs.

Siga as etapas na ordem. Ao fim de **cada** etapa: rode `ruff`, `mypy` e `pytest`,
faça um commit (Conventional Commits em PT) e me dê um resumo de 3 linhas.
Se algo do contrato estiver ambíguo, pergunte em vez de inventar.

### Etapa 0 — Scaffold
- `uv init` (Python 3.12), estrutura de pastas do `CLAUDE.md`, `uv add` das dependências
  (fastapi, uvicorn[standard], sqlalchemy[asyncio], asyncpg, alembic, pydantic-settings,
  pyjwt, pwdlib[argon2], email-validator; dev: pytest, pytest-asyncio, httpx, ruff, mypy, pre-commit).
- `docker-compose.yml` com `db` (Postgres 16, porta 5432) e `db-test` (porta 5433, tmpfs).
- `Dockerfile` multi-stage (uv) para produção. `.pre-commit-config.yaml` com ruff.
- `core/config.py` lendo `.env` (ver `.env.example`), `core/logging.py`, `core/errors.py`.
- `main.py` com CORS por `CORS_ORIGINS`, handler de erro padrão e `GET /monitoramento/status`.
- `ruff` e `mypy` configurados no `pyproject.toml` (line-length 100, regras E,F,I,B,UP,SIM,ASYNC).

### Etapa 1 — Banco e modelos
- `db/` (engine async, sessão, Base, mixin UUID + timestamps).
- Todos os modelos de `docs/CONTEXTO.md` + `enums.py`. Índice único em `rfid_tag`,
  índices em FKs e em `client_uuid` (único onde existir).
- Alembic configurado para async; migration inicial revisada à mão.
- `scripts/seed.py` idempotente: espécies da ficha, pátio "TG – Três Guri" com "Rua 08",
  usuário admin a partir de `SEED_ADMIN_*` do `.env`.

### Etapa 2 — Auth e usuários
- `core/security.py`: hash Argon2, JWT access/refresh (claims: sub, role, type, exp).
- `api/deps.py`: `get_session`, `get_current_user`, `require_roles(*roles)`.
- Rotas: `/auth/login` (aceita matrícula **ou** e-mail), `/auth/refresh`, `/auth/me`;
  `/auth/mfa` e `/auth/mfa-offline` retornando 501 `not_implemented`.
- `/usuarios` (GET/POST), `PATCH /usuarios/{id}/papel`, `POST /usuarios/convite`
  (token assinado com validade de 72h + link; sem envio de e-mail), `POST /auth/convite/aceitar`.
- Serviço de auditoria gravando em `audit_logs`; usado a partir daqui em toda escrita.

### Etapa 3 — Catálogo e dormentes
- CRUD de `/especies` e `/locais` (com permissões do `CONTEXTO.md`).
- `/dormentes`: listagem com filtros (status, espécie, local, busca por ata/tag), detalhe,
  criação, edição, `GET /dormentes/tag/{rfid_tag}` (404 claro se a tag não existir —
  o app usa isso para decidir entre "dormente novo" e "dormente conhecido"),
  `GET /dormentes/{id}/historico`.

### Etapa 4 — Operação de estoque e inspeção
- `/estoque/movimentacao`, `/estoque/localizacao`, `/estoque/inventario`, `/estoque/ocorrencias`
  e as listagens correspondentes, aplicando as regras de negócio do `CONTEXTO.md`.
- `/inspecoes` (POST/GET/detalhe); reprovação → dormente em `quarantine`.
- Todos aceitam `client_uuid` opcional e são idempotentes por ele.

### Etapa 5 — Sincronização offline
- `POST /sincronizacao/replicar`: lote misto (`movements`, `inspections`, `occurrences`,
  `inventory_counts`), processado item a item reaproveitando os services da etapa 4,
  resposta por item (`accepted`/`duplicate`/`rejected` + motivo). Um item ruim não derruba o lote.
- `GET /sincronizacao/status`. Persistir `SyncBatch`.

### Etapa 6 — Indicadores e logs
- `GET /indicadores` conforme `CONTEXTO.md` (queries agregadas no repository, não em Python).
- `GET /logs` paginado com filtros.

### Etapa 7 — Fechamento
- Cobertura de testes nas regras críticas (auth, permissões, idempotência do sync, regras de status).
- Exemplos (`json_schema_extra`) em todos os schemas, `tags` e `summary` em PT em todas as rotas,
  para o `/docs` servir de manual para o Pina (app) e o Matheus (site).
- `README.md` atualizado: como rodar, variáveis, usuários de seed, tabela de rotas.
- `docs/INTEGRACAO.md`: guia curto para o front — fluxo de login/refresh, formato de erro,
  paginação, como montar o lote de sync, e o mapeamento dos `ENDPOINTS` do site para as rotas reais.

**Não faça:** IA/visão computacional, QR/NFC, data lake, envio real de e-mail, deploy.
Deixe `TODO(decidir)` onde o `CONTEXTO.md` marca **A DECIDIR**.
