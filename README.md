# cptm-reo-api

API REST do **Projeto REO / CPTM** — rastreio, movimentação, inventário e inspeção digital
de dormentes ferroviários identificados por RFID. Conecta o app de campo
([APP-ProjetoCPTM-REO](https://github.com/1000Tsurus/APP-ProjetoCPTM-REO)) e o site gerencial
([mpliHD.github.io](https://github.com/mpliHD/mpliHD.github.io)).

> Em construção. Contexto e contrato de rotas: [`docs/CONTEXTO.md`](docs/CONTEXTO.md).
> Regras para quem codar (humano ou Claude Code): [`CLAUDE.md`](CLAUDE.md).
> Prompt de construção: [`PROMPT.md`](PROMPT.md).

## Stack
FastAPI · SQLAlchemy 2 (async) · Alembic · PostgreSQL · JWT · uv · pytest

## Rodando localmente
```bash
cp .env.example .env          # ajuste os valores
docker compose up -d db
uv sync
uv run alembic upgrade head
uv run python -m app.scripts.seed
uv run uvicorn app.main:app --reload --port 4000
```
Documentação interativa: http://localhost:4000/docs

## Equipe
API: Caio · App: Pina · Site: Matheus
