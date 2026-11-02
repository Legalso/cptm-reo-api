# Deploy — Azure for Students

Decisão registrada em `docs/CONTEXTO.md`, seção "Decisões tomadas":

```
GitHub (main) ──CI──► ghcr.io/legalso/cptm-reo-api:sha-<commit>
                                  │  (az containerapp update)
                                  ▼
Site (GitHub Pages) ──HTTPS──► Azure Container Apps ──SSL──► PostgreSQL Flexible Server (B1ms)
App (Expo)          ──HTTPS──┘   (escala a zero)
```

- **API:** Azure Container Apps, no plano de consumo, roda o `Dockerfile` do repositório.
  O HTTPS vem pronto, com um domínio `*.azurecontainerapps.io`.
- **Banco:** Azure Database for PostgreSQL Flexible Server, Burstable `Standard_B1ms`, PostgreSQL 16.
- **Imagem:** o CI publica no ghcr.io a cada push na `main` (job "Publicar imagem"), com as tags
  `latest` e `sha-<7 primeiros caracteres do commit>`.
- **Atualização de versão:** feita à mão, com um comando (seção 8). O CI não faz deploy automático.

Os comandos abaixo são para **PowerShell** (Windows). No bash, troque a crase do fim de linha
por `\` e `$VAR = "x"` por `VAR="x"`.

## 0. Pré-requisitos (uma vez)
1. Assinatura **Azure for Students** ativa (https://azure.microsoft.com/free/students). Ela vem
   com crédito e sem cartão. Quando o crédito acaba, os recursos param; nada é cobrado.
2. Azure CLI instalada: `winget install Microsoft.AzureCLI`. Depois:
   ```powershell
   az login
   az extension add --name containerapp --upgrade
   az provider register --namespace Microsoft.App
   az provider register --namespace Microsoft.OperationalInsights
   az provider register --namespace Microsoft.DBforPostgreSQL
   ```
3. Um **token do GitHub** (classic PAT) com o escopo `read:packages`, criado em
   https://github.com/settings/tokens. O repositório é privado, então a imagem no ghcr.io
   também é, e o Azure precisa desse token para baixá-la.
4. A imagem já publicada: depois do merge na `main`, confira em
   *GitHub → repositório → Packages* que existe `cptm-reo-api` com uma tag `sha-...`.

## 1. Variáveis
```powershell
$RG       = "rg-reo"
$LOCATION = "eastus2"             # ver "Região" logo abaixo
$PG       = "reo-db-caio"         # nome único no Azure inteiro (só minúsculas, números e -)
$PG_USER  = "reoadmin"
$PG_PASS  = "<senha forte do banco>"
$ENVNAME  = "reo-env"
$APP      = "reo-api"
$IMAGE    = "ghcr.io/legalso/cptm-reo-api:sha-<commit>"   # tag publicada pelo CI
```

**Região:** a assinatura de estudante só deixa criar recursos em algumas regiões. Se algum
comando falhar com `RequestDisallowedByAzure` ou "location is restricted", troque `$LOCATION`
(por exemplo `eastus2`, `centralus` ou `brazilsouth`) e repita. Banco e API devem ficar na
**mesma região**.

## 2. Grupo de recursos
```powershell
az group create -n $RG -l $LOCATION
```
Tudo fica dentro desse grupo. Para apagar tudo depois, veja a seção 11.

## 3. Banco (PostgreSQL Flexible Server B1ms)
```powershell
az postgres flexible-server create -g $RG -n $PG -l $LOCATION `
  --tier Burstable --sku-name Standard_B1ms --storage-size 32 --version 16 `
  --admin-user $PG_USER --admin-password $PG_PASS `
  --public-access 0.0.0.0 --yes

az postgres flexible-server db create -g $RG -s $PG -d reo

# Libera o seu IP só durante as migrations (a regra é removida na seção 5)
$MYIP = Invoke-RestMethod https://api.ipify.org
az postgres flexible-server firewall-rule create -g $RG -n $PG `
  --rule-name meu-ip --start-ip-address $MYIP --end-ip-address $MYIP
```
- `--public-access 0.0.0.0` libera o acesso **a partir de serviços do Azure**, como o Container
  Apps. Não libera a internet inteira.
- **Não troque o SKU:** só o `Standard_B1ms` com até 32 GB está na camada gratuita.

## 4. String de conexão
O Azure exige SSL (`?ssl=require`). A senha precisa ir **codificada na URL**:
```powershell
$PG_PASS_URL = [uri]::EscapeDataString($PG_PASS)
$DATABASE_URL = "postgresql+asyncpg://${PG_USER}:${PG_PASS_URL}@$PG.postgres.database.azure.com:5432/reo?ssl=require"
```

## 5. Migrations e seed (da sua máquina, na raiz do repositório)
```powershell
$env:DATABASE_URL = $DATABASE_URL
$env:SEED_ADMIN_PASSWORD = "<senha do admin de produção>"   # não use a do .env de dev
uv run alembic upgrade head
uv run python -m app.scripts.seed
Remove-Item Env:DATABASE_URL, Env:SEED_ADMIN_PASSWORD

az postgres flexible-server firewall-rule delete -g $RG -n $PG --rule-name meu-ip --yes
```
- O e-mail e a matrícula do admin vêm do seu `.env` (`SEED_ADMIN_EMAIL`, `SEED_ADMIN_REGISTRATION`).
- O seed é idempotente: rodar de novo não duplica nem troca a senha.

## 6. Ambiente e app do Container Apps
```powershell
az containerapp env create -g $RG -n $ENVNAME -l $LOCATION

$JWT = uv run python -c "import secrets; print(secrets.token_urlsafe(64))"

az containerapp create -g $RG -n $APP --environment $ENVNAME `
  --image $IMAGE `
  --registry-server ghcr.io --registry-username <seu-usuario-github> --registry-password <PAT read:packages> `
  --ingress external --target-port 4000 `
  --min-replicas 0 --max-replicas 1 --cpu 0.25 --memory 0.5Gi `
  --secrets "jwt-secret=$JWT" "database-url=$DATABASE_URL" `
  --env-vars APP_ENV=prod LOG_LEVEL=INFO `
    JWT_SECRET=secretref:jwt-secret DATABASE_URL=secretref:database-url `
    "CORS_ORIGINS=https://mplihd.github.io,http://localhost:5173" `
    INVITE_BASE_URL=https://mplihd.github.io
```
- **Segredos:** `JWT_SECRET` e `DATABASE_URL` entram como *secrets* do Container Apps, nunca como
  variável em texto. Trocar o `JWT_SECRET` desloga todo mundo.
- **CORS:** `CORS_ORIGINS` precisa listar toda origem que chama a API. Inclua a do app Expo
  quando ele rodar na web.

## 7. Testar
```powershell
$FQDN = az containerapp show -g $RG -n $APP --query properties.configuration.ingress.fqdn -o tsv
Invoke-RestMethod "https://$FQDN/monitoramento/status"    # status=ok, database=ok
start "https://$FQDN/docs"
```
Depois configure no site (aba "APIs & Integrações") e no app a URL base `https://<FQDN>`. O site
está em HTTPS, então a API também precisa estar, e o Container Apps já entrega isso.

**Primeira requisição lenta:** com `--min-replicas 0`, a primeira chamada depois de um tempo
parado pode levar alguns segundos enquanto o container sobe (cold start). O app e o site devem
usar timeout de pelo menos 30 s.

## 8. Publicar uma versão nova
1. Faça o merge na `main` e espere o CI publicar a tag `sha-<commit>`.
2. **Se o PR trouxe migration nova**, repita a seção 5 (liberar IP, `alembic upgrade head`,
   remover a regra) **antes** de trocar a imagem.
3. Troque a imagem:
   ```powershell
   az containerapp update -g $RG -n $APP --image ghcr.io/legalso/cptm-reo-api:sha-<commit>
   ```
   Cada update cria uma revisão nova. Para voltar à anterior, rode o mesmo comando com a tag antiga.

Use sempre uma tag `sha-...`, não `latest`: assim fica claro qual commit está no ar, e o rollback
é trocar a tag.

## 9. Logs
```powershell
az containerapp logs show -g $RG -n $APP --follow            # saída do uvicorn
az containerapp revision list -g $RG -n $APP -o table        # revisões e estado
```

## 10. Custos e cuidados
| Recurso | Camada gratuita (referência) | Como não estourar |
|---|---|---|
| PostgreSQL Flexible B1ms | 750 h/mês + 32 GB por 12 meses | Um único servidor, `Standard_B1ms`, 32 GB. Parado: `az postgres flexible-server stop -g $RG -n $PG` (volta sozinho após 7 dias) |
| Container Apps (consumo) | Cota mensal de vCPU-s, GiB-s e requisições | `--min-replicas 0` e `--cpu 0.25`. Com `min-replicas 1` o container fica ligado 24 h e passa da cota |
| Log Analytics (criado pelo ambiente) | Alguns GB/mês de ingestão | `LOG_LEVEL=INFO`. Não ligue `DEBUG` em produção |
| ghcr.io | Incluído no plano do GitHub | Apague tags antigas de vez em quando em *Packages* |

- Os limites mudam com o tempo. Confira os atuais em https://azure.microsoft.com/free/students.
- **Orçamento:** crie um no portal (*Cost Management → Budgets*), por exemplo de US$ 10 com
  alerta por e-mail, para saber cedo se algo está gastando crédito.
- **`/docs` público:** fica aberto em produção. Ele não expõe dados, porque toda rota exige token,
  mas mostra o contrato da API. Se quiser escondê-lo, abra uma tarefa.

## 11. Apagar tudo
```powershell
az group delete -n $RG --yes
```
O banco vai junto, sem volta. Faça um `pg_dump` antes se os dados importarem.

## Próximos passos possíveis
- **Deploy automático:** acrescentar ao CI um passo `az containerapp update` com login no Azure
  por OIDC. Exige criar um *service principal*, o que a conta de estudante (tenant da faculdade)
  às vezes não permite. Teste antes.
- **Migrations sem abrir o firewall:** rodar `alembic upgrade head` como *Container Apps job*
  dentro do Azure.
