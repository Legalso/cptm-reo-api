# Contexto do projeto — REO / CPTM

## Origem
União de dois planos de trabalho da CPTM (resp. técnico: Ricardo Luiz Ciuccio):
1. **Monitoramento em tempo real de dormentes em armazém logístico** — rastreabilidade,
   controle de movimentação, redução de perdas/extravios, indicadores operacionais.
2. **Identificação de madeira e inspeção digital de dormentes** — padronizar o tipo de
   madeira, checklist digital de inspeção, histórico técnico, redução do tempo de inspeção.

Fio condutor: cada dormente recebe uma **tag RFID**; o app lê a tag e registra
movimentações, inventário e inspeções; o site mostra a visão gerencial.

## Equipe e repositórios
| Parte | Responsável | Repo |
|---|---|---|
| API (este repo) | Caio | `Legalso/cptm-reo-api` |
| App mobile (Expo) | Pina | `1000Tsurus/APP-ProjetoCPTM-REO` |
| Site gerencial (React/Vite) | Matheus | `mpliHD/mpliHD.github.io` |

## Fora do escopo (por enquanto)
IA / análise de imagem, data lake, impressora térmica, QR Code e NFC (só RFID).
Hospedagem: agnóstica (Dockerfile); alvo provável Azure (créditos estudantis).

## Papéis (RBAC)
| Papel | Pode |
|---|---|
| `operador` | Registrar entrada/retirada/transferência, inventário, ocorrência; consultar dormentes |
| `tecnico` | Tudo do operador + registrar inspeções |
| `especialista` | Tudo do técnico + classificar/revisar espécie de madeira; manter catálogo de espécies |
| `supervisor` | Leitura total, indicadores, logs de auditoria; manter locais |
| `admin` | Tudo, incluindo usuários e papéis |

Plano de inspeção de referência: identificação na entrada (operador), inspeção visual
mensal (técnico), classificação da madeira única/revisão (especialista), auditoria
trimestral (supervisor).

## Modelo de domínio
- **WoodSpecies** (catálogo): `code` (ex. "01"), `scientific_name`, `common_name`, `active`.
  Seed com a ficha de dormentes da Rua 08: 01 Apuleia leiocarpa · 04 Bowdichia brasiliensis/nitida ·
  05 Bowdichia brasiliensis/nitida/Diplotropis purpurea · 07 Dialium guianense · 09 Dipteryx odorata ·
  10 Dipteryx spp · 11 Enterolobium schomburgkii · 12 Goupia glabra · 13 Hymenaea courbaril ·
  15 Hymenolobium petraeum · 17 Ocotea neesiana · 19 Angelim Vermelho (Promap) ·
  20 Coimmal (dormentes antigos) · 21 Veneer (dormentes antigos) · 22 Astronium graveolens/fraxinifolium.
- **Location**: hierarquia `warehouse` (pátio/armazém, ex. "TG – Três Guri") → `street` (ex. "Rua 08").
  Campos: `name`, `kind`, `parent_id`, `latitude`/`longitude` opcionais.
- **Sleeper** (dormente): `rfid_tag` (único), `registration_record` (ata de registro, ex. "AR00224-02"),
  `species_id`, `wood_class` (ex. "1a"), `length_m` (ex. 2.80), `treatment` (ex. "CCA"),
  `supplier` (ex. "Granoski", "Coimmal"), `inspection_company`, `manufacture_year`,
  `status`, `current_location_id`. Campos vêm da plaqueta física do dormente.
- **SleeperStatus**: `in_stock`, `withdrawn` (retirado p/ via), `in_track`, `quarantine`, `discarded`.
- **Movement**: `sleeper_id`, `kind` (`entry` | `withdrawal` | `transfer`), `from_location_id`,
  `to_location_id`, `requisition_number` (RM, na retirada), `user_id`, `occurred_at`, `client_uuid`.
  Regras: dormente `discarded` não movimenta; `entry` exige destino; `withdrawal` muda status para `withdrawn`.
- **InventoryCount**: contagem por `location_id` + `species_id` + `counted_at` com `quantity`
  (espelha a ficha de papel); opcionalmente lista de tags lidas para conciliar com o sistema.
- **Inspection**: `sleeper_id`, `inspector_id`, `inspected_at`, checklist:
  `conservation` (`good`|`fair`|`poor`), `has_cracks`, `biological_attack`, `moisture` (`dry`|`moist`|`wet`),
  `estimated_life_years`, `species_confirmed` (bool) / `species_corrected_id`, `notes`,
  `result` (`approved` | `rejected`), `duration_seconds` (p/ indicador de tempo médio), `client_uuid`.
  Inspeção reprovada coloca o dormente em `quarantine`.
- **Occurrence**: `sleeper_id` opcional, `location_id`, `kind` (`damage`|`loss`|`misplaced`|`other`),
  `description`, `user_id`, `occurred_at`, `client_uuid`.
- **User**: `name`, `email`, `registration` (matrícula, ex. "RL-8842"), `password_hash`, `role`, `active`.
- **AuditLog**: `user_id`, `action`, `entity`, `entity_id`, `before`/`after` (JSONB), `created_at`.
- **SyncBatch**: registro de cada lote recebido do app (device, contagens, status).

### Sync offline (idempotência)
Todo registro criado no app carrega `client_uuid` (UUID gerado no aparelho) e `occurred_at`.
`POST /sincronizacao/replicar` recebe um lote misto; o servidor faz upsert por `client_uuid`
(reenviar o mesmo lote não duplica nada) e devolve, por item, `accepted` | `duplicate` | `rejected` + motivo.
Analogia: é um protocolo de entrega com número de rastreio — se o carteiro passar duas vezes, o pacote não vira dois.

## Contrato de rotas
Prefixo: nenhum (o site concatena `baseUrl + path`). Porta local: **4000**.

### Já esperadas pelo site (não mudar path)
| Método | Path | Fase | Nota |
|---|---|---|---|
| POST | `/auth/login` | 1 | Fase 1 devolve tokens direto. Fase 2: devolve `tempToken` p/ MFA |
| POST | `/auth/mfa` | 2 | Até lá: 501 com `code="not_implemented"` |
| POST | `/auth/mfa-offline` | 2 | Credencial offline 48h. Até lá: 501 |
| GET | `/usuarios` | 1 | admin, supervisor |
| POST | `/usuarios` | 1 | admin |
| PATCH | `/usuarios/{id}/papel` | 1 | admin |
| POST | `/usuarios/convite` | 1 | Gera token + link de convite; **não envia e-mail** (o site abre o mailto) |
| POST | `/estoque/movimentacao` | 1 | |
| POST | `/estoque/inventario` | 1 | |
| POST | `/estoque/localizacao` | 1 | Atalho de transferência/posicionamento |
| POST | `/estoque/ocorrencias` | 1 | |
| POST | `/sincronizacao/replicar` | 1 | |
| GET | `/sincronizacao/status` | 1 | Último lote do usuário/dispositivo |
| GET | `/monitoramento/status` | 1 | Health: API, banco, versão. Sem auth |
| GET | `/logs` | 1 | supervisor, admin; filtros por usuário/entidade/período |

### Novas
| Método | Path | Fase |
|---|---|---|
| POST | `/auth/refresh` · GET `/auth/me` · POST `/auth/convite/aceitar` | 1 |
| GET/POST/PATCH | `/especies`, `/especies/{id}` | 1 |
| GET/POST/PATCH | `/locais`, `/locais/{id}` | 1 |
| GET/POST/PATCH | `/dormentes`, `/dormentes/{id}` | 1 |
| GET | `/dormentes/tag/{rfid_tag}` | 1 |
| GET | `/dormentes/{id}/historico` | 1 (movimentações + inspeções + ocorrências em ordem) |
| GET | `/estoque/movimentacoes`, `/estoque/inventarios`, `/estoque/ocorrencias` | 1 |
| GET/POST | `/inspecoes`, `/inspecoes/{id}` | 1 |
| GET | `/indicadores` | 1 |

### `/indicadores` (dashboard)
Período via `?de=&ate=`. Devolve: total de dormentes por status, por espécie e por local;
movimentações por dia (7 dias padrão); inspeções por dia; tempo médio de inspeção;
% reprovação; ocorrências por tipo; perdas (`loss`) no período.

## A DECIDIR
- MFA: TOTP (app autenticador) vs código por e-mail.
- Credencial offline de 48h: formato e revogação.
- Envio real de e-mail de convite (provedor).
- Deploy: Azure App Service vs Container Apps; Azure Database for PostgreSQL Flexible Server.
- Regra de conciliação de inventário (contagem física x sistema).
