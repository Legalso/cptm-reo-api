# cptm-reo-api

[![CI](https://github.com/Legalso/cptm-reo-api/actions/workflows/ci.yml/badge.svg)](https://github.com/Legalso/cptm-reo-api/actions/workflows/ci.yml)

API REST do **Projeto REO / CPTM** — rastreio, movimentação, inventário e inspeção digital
de dormentes ferroviários identificados por RFID. Conecta o app de campo
([APP-ProjetoCPTM-REO](https://github.com/1000Tsurus/APP-ProjetoCPTM-REO)) e o site gerencial
([mpliHD.github.io](https://github.com/mpliHD/mpliHD.github.io)).

- Contexto, domínio e contrato: [`docs/CONTEXTO.md`](docs/CONTEXTO.md)
- Guia para o front (login, erros, paginação, sync): [`docs/INTEGRACAO.md`](docs/INTEGRACAO.md)
- Regras para quem codar (humano ou Claude Code): [`CLAUDE.md`](CLAUDE.md)

## Stack
FastAPI · SQLAlchemy 2 (async/asyncpg) · Alembic · PostgreSQL 16 · JWT (PyJWT) · Argon2 · uv · pytest

## Rodando localmente
Pré-requisitos: [uv](https://docs.astral.sh/uv/) e Docker.

```bash
cp .env.example .env          # gere JWT_SECRET e troque SEED_ADMIN_PASSWORD
docker compose up -d db db-test
uv sync
uv run alembic upgrade head
uv run python -m app.scripts.seed
uv run uvicorn app.main:app --reload --port 4000
```

- Documentação interativa: http://localhost:4000/docs (botão **Authorize** aceita o `access_token`)
- Health check: http://localhost:4000/monitoramento/status

> Já tem um Postgres instalado ocupando a 5432? Defina `DB_PORT=5434` no `.env` e ajuste
> `DATABASE_URL` para `...@localhost:5434/reo`.

API em container (opcional): `docker compose --profile app up -d --build`.
As migrations rodam como passo separado (`alembic upgrade head`), não no start do container.

## Qualidade
```bash
uv run pytest                                  # precisa do db-test (porta 5433) no ar
uv run ruff check . && uv run ruff format --check . && uv run mypy app
uv run pre-commit install                      # ruff em todo commit
```
Os testes recriam o schema no `db-test` e cada teste roda numa transação desfeita ao final.

O CI (`.github/workflows/ci.yml`) roda em todo PR e push na `main`:
1. **Lint e tipos:** ruff e mypy.
2. **Migrations e testes**, contra Postgres 16:
   - `alembic upgrade`, `downgrade` e `upgrade` de novo;
   - `alembic check`, que confirma que os modelos batem com as migrations;
   - o seed rodado duas vezes;
   - o pytest.
3. **Build** da imagem Docker.

## Variáveis de ambiente
| Variável | Padrão | Para quê |
|---|---|---|
| `APP_ENV` | `dev` | `dev` · `test` · `prod` |
| `APP_PORT` | `4000` | Porta (informativo; o uvicorn recebe `--port`) |
| `LOG_LEVEL` | `INFO` | Nível de log |
| `DB_PORT` | `5432` | Porta publicada do serviço `db` no compose |
| `DATABASE_URL` | — | `postgresql+asyncpg://...` (obrigatória) |
| `TEST_DATABASE_URL` | — | Banco dos testes (`db-test`, porta 5433) |
| `JWT_SECRET` | — | Obrigatória; ≥ 32 caracteres. A API não sobe com `troque-isto` |
| `JWT_ACCESS_MINUTES` | `15` | Validade do access token |
| `JWT_REFRESH_DAYS` | `7` | Validade do refresh token |
| `INVITE_TOKEN_HOURS` | `72` | Validade do convite |
| `INVITE_BASE_URL` | `http://localhost:5173` | Base do link de convite (`<base>/convite/<token>`) |
| `CORS_ORIGINS` | — | Origens liberadas, separadas por vírgula |
| `SEED_ADMIN_NAME` / `_EMAIL` / `_REGISTRATION` / `_PASSWORD` | — | Admin criado pelo seed (não cria com senha `troque-isto`) |

## Dados do seed
`uv run python -m app.scripts.seed` é idempotente: só cria o que falta e nunca sobrescreve.

- **Espécies** da ficha da Rua 08: 01, 04, 05, 07, 09, 10, 11, 12, 13, 15, 17, 19, 20, 21, 22.
- **Locais:** pátio `TG – Três Guri` com a rua `Rua 08`.
- **Usuário admin:** matrícula/e-mail/senha de `SEED_ADMIN_*` no `.env`. Login aceita matrícula
  **ou** e-mail (`ADM-0001` / `admin@reo.local` no exemplo).

## Papéis
| Papel | Pode |
|---|---|
| `operador` | Cadastrar dormente, movimentar, posicionar, inventário, ocorrência, sync; consultar |
| `tecnico` | Tudo do operador + inspeções + status manual (quarentena, em via, descarte) |
| `especialista` | Tudo do técnico + catálogo de espécies + corrigir espécie do dormente |
| `supervisor` | Leitura total, indicadores, logs, usuários (leitura), manter locais |
| `admin` | Tudo, incluindo usuários, papéis e convites |

## Rotas
Sem prefixo; o site concatena `baseUrl + path`. ✱ = path já usado pelo site (não muda).

| Método | Path | Quem | O quê |
|---|---|---|---|
| POST | `/auth/login` ✱ | público | Login (matrícula ou e-mail) → tokens |
| POST | `/auth/refresh` | público | Novo par de tokens a partir do refresh |
| GET | `/auth/me` | logado | Usuário atual |
| POST | `/auth/convite/aceitar` | token de convite | Cria a conta e já devolve tokens |
| POST | `/auth/mfa` ✱ · `/auth/mfa-offline` ✱ | — | 501 `not_implemented` (fase 2) |
| GET | `/usuarios` ✱ | supervisor, admin | Lista (filtros `role`, `active`, `q`) |
| POST | `/usuarios` ✱ | admin | Cria usuário |
| PATCH | `/usuarios/{id}/papel` ✱ | admin | Troca papel (não rebaixa o último admin) |
| POST | `/usuarios/convite` ✱ | admin | Token + link de convite (sem envio de e-mail) |
| GET · POST · PATCH | `/especies`, `/especies/{id}` | todos · especialista | Catálogo de espécies |
| GET · POST · PATCH | `/locais`, `/locais/{id}` | todos · supervisor | Pátios e ruas |
| GET · POST · PATCH | `/dormentes`, `/dormentes/{id}` | todos · operador+ | Dormentes (filtros `status`, `species_id`, `location_id`, `q`) |
| GET | `/dormentes/tag/{rfid_tag}` | todos | Busca por tag; 404 `sleeper_not_found` se não existe |
| GET | `/dormentes/{id}/historico` | todos | Movimentações + inspeções + ocorrências em ordem |
| POST | `/estoque/movimentacao` ✱ | operador+ | Entrada / retirada / transferência |
| POST | `/estoque/localizacao` ✱ | operador+ | Posicionar (vira transferência ou entrada) |
| POST | `/estoque/inventario` ✱ | operador+ | Contagem por local + espécie |
| POST | `/estoque/ocorrencias` ✱ | operador+ | Dano, perda, extravio, outro |
| GET | `/estoque/movimentacoes` · `/estoque/inventarios` · `/estoque/ocorrencias` | todos | Listagens com filtros e `?de=&ate=` |
| GET · POST | `/inspecoes`, `/inspecoes/{id}` | todos · técnico+ | Inspeções (reprovada → quarentena) |
| POST | `/sincronizacao/replicar` ✱ | operador+ | Lote offline, resultado por item |
| GET | `/sincronizacao/status` ✱ | logado | Último lote do usuário (`?device_id=`) |
| GET | `/indicadores` | supervisor, admin | Dashboard (`?de=&ate=`, padrão 7 dias) |
| GET | `/logs` ✱ | supervisor, admin | Auditoria (filtros usuário, entidade, ação, período) |
| GET | `/monitoramento/status` ✱ | público | Saúde: API, banco, versão |

## Pendências (A DECIDIR no `CONTEXTO.md`)
Marcadas com `TODO(decidir)` no código: MFA (TOTP × e-mail), credencial offline de 48h,
envio real do e-mail de convite, conciliação de inventário (contagem física × sistema) e deploy.

## Equipe
API: Caio · App: Pina · Site: Matheus
