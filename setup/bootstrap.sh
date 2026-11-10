#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Одноразовая подготовка лаборатории (вариант Bicep). Запускается ВАМИ после `az login`.
# Нужны права: Owner (или User Access Administrator + Contributor) на подписке
# и право создавать регистрации приложений в Entra ID.
#
# Что делает:
#   1. Группа ресурсов для лаборатории.
#   2. Регистрация приложения в Entra ID = идентичность pipeline.
#   3. Federated credentials (OIDC) для GitHub-окружений infra, dev, prod.
#   4. Роли RBAC по принципу минимальных прав.
# Хранилище state НЕ нужно: Bicep не хранит файл состояния (в отличие от Terraform).
#
# Использование:
#   GITHUB_REPO="my-org/foundry-cicd-lab-bicep" LOCATION="swedencentral" ./setup/bootstrap.sh
# ---------------------------------------------------------------------------
set -euo pipefail

# Windows/Git Bash (MSYS2) превращает аргументы вида "/subscriptions/..." в пути
# Windows ("C:\Program Files\Git\subscriptions\..."), и Azure получает неверный scope.
# Отключаем это преобразование. На Linux и в Cloud Shell переменная ни на что не влияет.
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL="*"

: "${GITHUB_REPO:?Укажите GITHUB_REPO в формате owner/repo}"
: "${LOCATION:?Укажите LOCATION (регион, где доступна выбранная модель)}"
RG="${RG:-rg-foundry-cicd-lab-bicep}"
APP_NAME="${APP_NAME:-sp-foundry-cicd-lab-bicep}"

SUBSCRIPTION_ID="$(az account show --query id -o tsv)"
TENANT_ID="$(az account show --query tenantId -o tsv)"
RG_ID="/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RG}"

echo "== 1. Группа ресурсов ${RG} (регион ${LOCATION} станет регионом Foundry)"
az group create --name "$RG" --location "$LOCATION" -o none

echo "== 2. Идентичность pipeline (регистрация приложения)"
APP_ID="$(az ad app create --display-name "$APP_NAME" --query appId -o tsv)"
az ad sp create --id "$APP_ID" -o none 2>/dev/null || true
SP_OBJECT_ID="$(az ad sp show --id "$APP_ID" --query id -o tsv)"

echo "== 3. Federated credentials (OIDC): доверяем GitHub-окружениям infra, dev, prod"
for ENV in infra dev prod; do
  az ad app federated-credential create --id "$APP_ID" --parameters "{
    \"name\": \"github-${ENV}\",
    \"issuer\": \"https://token.actions.githubusercontent.com\",
    \"subject\": \"repo:${GITHUB_REPO}:environment:${ENV}\",
    \"audiences\": [\"api://AzureADTokenExchange\"]
  }" -o none
done

echo "== 4. Роли RBAC (минимально необходимые)"
assign() {  # $1 = роль, $2 = scope
  az role assignment create --assignee-object-id "$SP_OBJECT_ID" \
    --assignee-principal-type ServicePrincipal --role "$1" --scope "$2" -o none
}
# Control plane: развёртывать Bicep (Foundry, проекты, модель)
assign "Contributor" "$RG_ID"
# Data plane: создавать версии агентов и вызывать их (Owner/Contributor этого НЕ дают)
assign "Foundry User" "$RG_ID" || {
  echo "   Роль 'Foundry User' не найдена — пробую старое имя 'Azure AI User'"
  assign "Azure AI User" "$RG_ID"
}

# Вам самим — для локальных запусков скриптов
ME="$(az ad signed-in-user show --query id -o tsv)"
az role assignment create --assignee-object-id "$ME" --assignee-principal-type User \
  --role "Foundry User" --scope "$RG_ID" -o none 2>/dev/null || \
az role assignment create --assignee-object-id "$ME" --assignee-principal-type User \
  --role "Azure AI User" --scope "$RG_ID" -o none

cat <<EOF

===========================================================================
Готово. Добавьте в GitHub → Settings → Secrets and variables → Actions → Variables:

  AZURE_CLIENT_ID        = ${APP_ID}
  AZURE_TENANT_ID        = ${TENANT_ID}
  AZURE_SUBSCRIPTION_ID  = ${SUBSCRIPTION_ID}
  AZURE_RESOURCE_GROUP   = ${RG}

Или командами GitHub CLI:
  gh variable set AZURE_CLIENT_ID       --body ${APP_ID}
  gh variable set AZURE_TENANT_ID       --body ${TENANT_ID}
  gh variable set AZURE_SUBSCRIPTION_ID --body ${SUBSCRIPTION_ID}
  gh variable set AZURE_RESOURCE_GROUP  --body ${RG}

Это НЕ секреты: это идентификаторы. Секрета (пароля) у pipeline нет вообще.
Не забудьте создать окружения GitHub: infra, dev, prod (для prod — Required reviewers).
Назначение ролей вступает в силу через несколько минут.
===========================================================================
EOF
