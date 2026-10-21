# CLAUDE.md — cptm-reo-api

Backend (API REST) do **Projeto REO / CPTM**: rastreio, movimentação, inventário e
inspeção digital de **dormentes ferroviários** identificados por **tag RFID**.
Contexto de negócio, modelo de domínio e contrato de rotas: `docs/CONTEXTO.md` (leia antes de codar).

## Quem consome esta API
- **App mobile** (Expo/React Native, operador de campo) — repo `1000Tsurus/APP-ProjetoCPTM-REO`.
  O leitor RFID fala **só com o app**; a API recebe apenas o código da tag.
  O app trabalha offline e envia lotes por `POST /sincronizacao/replicar`.
- **Site gerencial** (React + Vite, GitHub Pages) — repo `mpliHD/mpliHD.github.io`.
  Já tem os paths e a URL base `http://localhost:4000` fixados em `src/App.jsx` (const `ENDPOINTS`).
  **Não quebre esses paths.** Rotas novas podem ser adicionadas.

## Stack
- Python 3.12+, gerenciado com **uv** (`uv add`, `uv run`). Nunca use `pip install` direto.
- FastAPI + Uvicorn · Pydantic v2 + pydantic-settings
- SQLAlchemy 2.x **async** (asyncpg) · Alembic para migrations · **PostgreSQL** (Docker local, Azure depois)
- Auth: JWT (PyJWT) access + refresh · hash de senha com Argon2 (pwdlib)
- Qualidade: ruff (lint + format), mypy, pytest + pytest-asyncio + httpx (AsyncClient)

## Comandos
```bash
docker compose up -d db                     # sobe o Postgres
uv sync                                      # instala dependências
uv run alembic upgrade head                  # aplica migrations
uv run python -m app.scripts.seed            # dados iniciais (espécies, locais, admin)
uv run uvicorn app.main:app --reload --port 4000
uv run pytest                                # testes
uv run ruff check . && uv run ruff format --check . && uv run mypy app
```
Docs interativas: `http://localhost:4000/docs`.

## Arquitetura (camadas — respeite a direção das dependências)
```
app/
  main.py            # cria o FastAPI, CORS, routers, handlers de erro
  core/              # config (Settings), security (JWT, hash), logging, errors
  db/                # engine, session, Base, mixins (id UUID, timestamps)
  models/            # ORM SQLAlchemy — um arquivo por agregado
  schemas/           # Pydantic (entrada/saída) — nunca retorne ORM cru
  repositories/      # acesso a dados (queries). Sem regra de negócio
  services/          # regra de negócio, transações, auditoria
  api/
    deps.py          # get_session, get_current_user, require_roles(...)
    routes/          # um router por recurso; só valida/chama service/serializa
  scripts/seed.py
alembic/
tests/               # espelha app/; fixtures em conftest.py
```
Router → Service → Repository → Model. Router nunca acessa o banco direto.
Analogia: o router é o balcão de atendimento, o service é quem decide, o repository é o almoxarife.

## Convenções de código
- **Identificadores em inglês** (classes, funções, variáveis, tabelas, colunas).
  **Paths de URL em português** (contrato com o front). **Comentários e docstrings em português.**
- Toda função pública tem type hints e docstring curta em PT dizendo *o quê* e *por quê*.
  Comente decisões e regras de negócio, não o óbvio.
- PKs `UUID`; todo modelo tem `created_at`/`updated_at` (UTC, `timezone=True`).
- Datas sempre em UTC na API (ISO 8601); conversão de fuso é do front.
- Enums de domínio como `StrEnum` em `app/models/enums.py`, usados nos schemas também.
- Listagens paginadas (`limit`/`offset`, padrão 50, máx 200) e retornam `{items, total, limit, offset}`.
- Erros no formato único `{"detail": str, "code": str}` via exceções de `app/core/errors.py`.
- Nada de `print`; use `logging` configurado em `core/logging.py`.
- Sem lógica em `__init__.py`. Funções pequenas; arquivo > ~300 linhas é sinal para dividir.

## Segurança (inegociável)
- Segredos só via variáveis de ambiente (`.env`, nunca commitado). `.env.example` documenta todas.
- Autorização **no servidor** em toda rota via `require_roles(...)`; o front só esconde botões.
- Senha nunca é logada nem retornada. Tokens com expiração curta (access 15 min, refresh 7 dias).
- CORS restrito à lista `CORS_ORIGINS` do `.env`.
- Toda escrita relevante gera registro em `audit_logs` (quem, o quê, quando, entidade, antes/depois).
- Validar tamanho/tipo de qualquer upload no backend (hoje não há upload; se surgir, valide).

## Banco e migrations
- Toda mudança de modelo vem com migration Alembic gerada **e revisada** (`--autogenerate` erra enums e índices).
- Nunca edite migration já aplicada em `main`; crie outra.
- `rfid_tag` é único e indexado; consultas por tag são o caminho mais quente da API.

## Testes
- Toda rota nova tem teste de: sucesso, validação (422), sem auth (401) e papel errado (403).
- Regras de negócio testadas no service (ex.: não movimentar dormente descartado; sync idempotente).
- Testes rodam contra Postgres de teste (serviço `db-test` do compose), com rollback por teste.

## Git
- Branch por tarefa: `feat/...`, `fix/...`, `chore/...`. PR para `main`.
- Conventional Commits em PT: `feat(dormentes): busca por tag RFID`.
- Antes de commitar: ruff, mypy e pytest passando.

## Como trabalhar neste repo (para o Claude Code)
- Leia `docs/CONTEXTO.md` antes de qualquer tarefa de domínio.
- Mudança que altera contrato de rota usada pelo site/app → pare e pergunte.
- Prefira entregas pequenas e verificáveis; rode os testes ao fim de cada etapa.
- Itens marcados **A DECIDIR** em `docs/CONTEXTO.md` não devem ser inventados: implemente o mínimo e deixe `TODO(decidir)`.
