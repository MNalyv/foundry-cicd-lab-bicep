// ---------------------------------------------------------------------------
// Инфраструктура лаборатории на Bicep (по образцу Microsoft Learn:
// "Create a Foundry resource using a Bicep file")
//
//   Foundry resource  ──►  проекты proj-dev и proj-prod  (окружения)
//         └──────────────►  развёртывание модели "chat" (общее для проектов)
//
// Отличие от Terraform: Bicep НЕ хранит state-файл. Он компилируется в ARM-шаблон,
// и Azure Resource Manager сам сравнивает желаемое состояние с текущим.
// Область развёртывания: группа ресурсов (создаётся setup/bootstrap.sh).
// ---------------------------------------------------------------------------

@description('Регион. Выберите регион, где выбранная модель доступна как GlobalStandard.')
param location string = resourceGroup().location

@description('Имя ресурса Foundry (глобально уникальное, строчные буквы и цифры). Оно же — поддомен endpoint.')
param foundryName string

@description('Отдельный проект Foundry на каждое окружение (опора 1 CI/CD: environments).')
param projectNames array = [
  'proj-dev'
  'proj-prod'
]

@description('Имя развёртывания модели. Его указывают в agent/agent.yaml (поле model).')
param modelDeploymentName string = 'chat'

@description('Имя модели из каталога Foundry (проверьте, что она доступна в вашем регионе).')
param modelName string

@description('Версия модели (тема 3: закрепление версии).')
param modelVersion string

@description('Тип развёртывания (SKU) из темы 2.')
@allowed([
  'GlobalStandard'
  'DataZoneStandard'
  'Standard'
])
param deploymentSku string = 'GlobalStandard'

@description('Ёмкость. Для Standard-типов 1 единица = 1 000 TPM (тема 3: limits).')
@minValue(1)
param capacity int = 10

@description('Политика обновления версии (тема 3).')
@allowed([
  'NoAutoUpgrade'
  'OnceNewDefaultVersionAvailable'
  'OnceCurrentVersionExpired'
])
param versionUpgradeOption string = 'NoAutoUpgrade'

// 1. Ресурс Foundry (control plane: управление)
resource foundry 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: foundryName
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned' // managed identity ресурса (тема безопасности)
  }
  properties: {
    allowProjectManagement: true // разрешает проекты Foundry (не hub!)
    customSubDomainName: foundryName // https://<имя>.services.ai.azure.com
    disableLocalAuth: true // keyless: только Entra ID, без API-ключей
    publicNetworkAccess: 'Enabled' // для учебы; в prod — private endpoints
  }
}

// 2. Отдельный проект на каждое окружение (dev, prod)
resource projects 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = [
  for projectName in projectNames: {
    parent: foundry
    name: projectName
    location: location
    identity: {
      type: 'SystemAssigned'
    }
    properties: {
      displayName: projectName
      description: 'CI/CD lab project: ${projectName}'
    }
  }
]

// 3. Развёртывание модели (тема 3: SKU, версия, политика обновления, ёмкость)
resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: foundry
  name: modelDeploymentName
  sku: {
    name: deploymentSku
    capacity: capacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: modelName
      version: modelVersion
    }
    versionUpgradeOption: versionUpgradeOption
  }
  // Создаём после проектов, чтобы не было параллельных изменений аккаунта.
  dependsOn: [
    projects
  ]
}

// Выходные значения: скопируйте endpoints в config/dev.json и config/prod.json
output foundryResourceId string = foundry.id
output projectEndpoints array = [
  for projectName in projectNames: {
    project: projectName
    endpoint: 'https://${foundryName}.services.ai.azure.com/api/projects/${projectName}'
  }
]
output modelDeploymentName string = modelDeployment.name
