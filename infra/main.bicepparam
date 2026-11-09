// Заполните перед первым запуском (значения <...> — обязательные).
using './main.bicep'

// Только ИМЯ ресурса, без https:// и без пути к проекту.
param foundryName = 'test-6124-resource'

// Модель и версия: возьмите из каталога моделей Foundry для вашего региона
// (тип развёртывания Global Standard). Пример формата: 'gpt-4.1-mini' / '2025-04-14'.
param modelName = 'gpt-5.2'
param modelVersion = '2025-12-11'

param deploymentSku = 'GlobalStandard'
param capacity = 10 // 10 единиц = 10 000 TPM для Standard-типов
param versionUpgradeOption = 'NoAutoUpgrade'

// Регион по умолчанию = регион группы ресурсов (задаётся в bootstrap.sh).
