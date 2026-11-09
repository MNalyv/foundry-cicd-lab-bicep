# Foundry CI/CD Lab (Bicep) — учебный проект к AI-103 (тема 4: CI/CD)

Тот же проект, что и вариант на Terraform, но инфраструктура описана на **Bicep**.
Агент Microsoft Foundry разворачивается через GitHub Actions: вход без секретов (OIDC),
quality gate, продвижение dev → prod, закрепление версии и откат.

> ⚠️ **Это учебный проект.** Он создаёт платные ресурсы Azure (модель тарифицируется за токены).
> После занятий удалите всё (раздел «Уборка»).
> Код написан по документации Microsoft, но я не могла запустить его в вашей подписке —
> если какой-то шаг упадёт, это часть тренировки: прочитайте ошибку и см. «Если что-то не так».

---

## Bicep и Terraform в этой лаборатории — в чём разница

| | **Этот проект (Bicep)** | **Вариант Terraform** |
|---|---|---|
| Язык | Bicep (Microsoft, только Azure) | HCL (HashiCorp, multi-cloud) |
| Файлы | `infra/main.bicep` + `main.bicepparam` | `infra/*.tf` + `lab.tfvars` |
| Состояние (state) | **Нет state-файла** — Azure сам сравнивает с текущим состоянием | **State** в Azure Storage (нужен отдельный storage account) |
| «Что изменится?» | `az deployment group what-if` | `terraform plan` |
| Применить | `az deployment group create` | `terraform apply` |
| Вход в Azure в pipeline | `azure/login` (OIDC) | переменные `ARM_USE_OIDC` и др. (OIDC) |
| Подготовка (`bootstrap.sh`) | группа ресурсов, OIDC, роли | то же **+ Storage для state** |

Всё остальное (агент, скрипты, CI, CD, откат, лабы 2–8) — **одинаковое**. Так удобно сравнить:
меняется только способ описать инфраструктуру, а процесс CI/CD остаётся тем же.

---

## Что вы потренируете

| Что делаете в лабе | Тема курса |
|---|---|
| Описываете Foundry, проекты и развёртывание в **Bicep** | 4 · IaC (Bicep vs Terraform) |
| Храните `agent.yaml`, данные оценки и pipeline в Git | 4 · AI-артефакты = код |
| Pipeline входит в Azure через **OIDC**, без client secret | 4 · Federated Identity |
| Отдельные проекты `proj-dev` и `proj-prod` | 4 · Опора 1: environments |
| `run_eval.py` блокирует выпуск при pass rate ниже порога | 4 · Опора 2: gates |
| Закрепление (pin) версии и откат за секунды | 4 · Опора 3: rollback / 3 · version selector |
| Отчёт в Job summary, (доп.) трассы в Application Insights | 4 · Опора 4: observability |
| SKU `GlobalStandard`, ёмкость (TPM), `NoAutoUpgrade` | 2–3 · Типы и настройки развёртывания |
| Роли: `Contributor` (control plane) + `Foundry User` (data plane), `disableLocalAuth` | Безопасность · RBAC, keyless |

---

## Структура

```
foundry-cicd-lab-bicep/
├── infra/
│   ├── main.bicep             ← Foundry resource, проекты dev/prod, развёртывание модели
│   └── main.bicepparam        ← ВАШИ значения (имя, модель, версия)
├── agent/agent.yaml           ← определение агента (инструкции + имя развёртывания)
├── config/dev.json, prod.json ← endpoint проекта и порог качества для каждого окружения
├── eval/golden_set.jsonl      ← эталонные вопросы для evaluator
├── scripts/
│   ├── deploy_agent.py        ← создать новую версию агента
│   ├── run_eval.py            ← evaluator = quality gate
│   ├── endpoint_routing.py    ← version selector: show / protect / pin
│   └── validate.py            ← статические проверки для CI
├── setup/bootstrap.sh         ← одноразовая настройка: OIDC и роли
└── .github/workflows/
    ├── infra.yml              ← Bicep: what-if (PR) / deployment (main)
    ├── ci.yml                 ← PR: проверки + DEV + gate
    ├── cd.yml                 ← main: DEV → одобрение → PROD (pin, smoke, авто-откат)
    └── rollback.yml           ← ручной откат на выбранную версию
```

Как всё связано:

```
Git (описания)                 GitHub Actions (OIDC)              Azure / Foundry
──────────────                 ─────────────────────              ───────────────
infra/main.bicep    ── infra ──►  az deployment group create ──►  Foundry + proj-dev + proj-prod + "chat"
agent/agent.yaml    ── ci/cd ──►  create_version             ──►  агент travel-helper (версии 1, 2, 3…)
eval/golden_set     ── ci/cd ──►  run_eval (gate)            ──►  PASS → дальше / FAIL → стоп
                    ── cd    ──►  pin version (prod)         ──►  100% трафика prod → версия N
```

---

## 0. Что нужно заранее

- Подписка Azure, где у вас роль **Owner** (нужно назначать роли) и право создавать регистрации приложений в Entra ID.
- Аккаунт GitHub и пустой репозиторий (например, `foundry-cicd-lab-bicep`).
- Локально: **Azure CLI** (Bicep входит в него: `az bicep install`), **Python ≥ 3.10**, (желательно) **GitHub CLI** `gh`.

---

## 1. Выберите модель и регион

1. Откройте каталог моделей в портале Foundry и выберите недорогую чат-модель, доступную в вашем регионе с типом развёртывания **Global Standard**.
2. Запишите **имя модели** и **версию**.
3. Заполните `infra/main.bicepparam`: `foundryName` (уникальное, только строчные буквы и цифры), `modelName`, `modelVersion`.
   Регион берётся из группы ресурсов, которую создаёт `bootstrap.sh`.

> 💡 Тема 3: мы закрепляем конкретную версию и ставим `versionUpgradeOption = 'NoAutoUpgrade'`.
> Помните ловушку: в дату retirement такое развёртывание перестанет работать.

Проверить шаблон локально (необязательно):
```bash
az bicep build --file infra/main.bicep --stdout > /dev/null && echo "Bicep OK"
```

---

## 2. Одноразовая настройка (OIDC и роли)

```bash
az login
GITHUB_REPO="<owner>/<repo>" LOCATION="<регион с вашей моделью>" bash setup/bootstrap.sh
```

Скрипт создаёт группу ресурсов, идентичность pipeline, **federated credentials**
для GitHub-окружений `infra`, `dev`, `prod` и роли:

| Роль | Кому / где | Зачем (плоскость) |
|---|---|---|
| `Contributor` | pipeline → группа ресурсов | Bicep создаёт Foundry, проекты, развёртывание (**control plane**) |
| `Foundry User` | pipeline и вы → группа ресурсов | создавать версии агента и вызывать его (**data plane**) |

> Хранилище state не создаётся — в Bicep его просто нет. Сравните с `bootstrap.sh` в варианте Terraform.

> Если на шаге «pin» будет **403**, добавьте идентичности pipeline роль `Foundry Project Manager`
> на группу ресурсов — это и есть урок «control plane ≠ data plane, нужны правильные роли».

---

## 3. Настройте GitHub

1. Залейте проект в репозиторий:
   ```bash
   git init && git add . && git commit -m "lab: initial"
   git branch -M main && git remote add origin https://github.com/<owner>/<repo>.git
   git push -u origin main
   ```
2. **Settings → Environments**: создайте `infra`, `dev`, `prod`. Для `prod` включите **Required reviewers** (себя) — это ручное одобрение перед продом.
3. **Settings → Secrets and variables → Actions → Variables**: добавьте 4 переменные, которые вывел `bootstrap.sh`
   (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_RESOURCE_GROUP`).
   Обратите внимание: **секретов нет вообще** — только идентификаторы.

---

## Лабораторные задания

### Лаба 1 · Инфраструктура как код (Bicep)
1. **Actions → infra → Run workflow**.
2. Посмотрите шаги: `azure/login` (OIDC) → `bicep build` (компиляция в ARM) → `what-if` → развёртывание.
3. В **Job summary** скопируйте endpoints в `config/dev.json` и `config/prod.json`, закоммитьте.
4. ✔️ Проверьте в портале: один ресурс Foundry, **два проекта**, развёртывание `chat`.
   В группе ресурсов → **Deployments** видна история развёртываний Bicep.

**Вопросы для себя:** где «живёт» информация о текущем состоянии, если state-файла нет?
Что покажет `what-if`, если поменять `capacity` с 10 на 20? (Сделайте это через PR — увидите what-if без изменений.)

### Лаба 2 · Первый выпуск: dev → gate → prod
1. Коммит `config/*.json` в `main` запускает **cd**.
2. Job `dev`: новая версия агента → **quality gate**. Откройте Job summary — таблица кейсов.
3. Job `prod` ждёт вашего **одобрения** (environment `prod`) → одобрите.
4. В `prod`: `protect` → `deploy` (то же определение) → `pin` → smoke-проверка.
5. ✔️ В портале у агента `travel-helper` в **каждом** проекте есть версия; в prod endpoint закреплён.

### Лаба 3 · Quality gate блокирует плохую версию
1. Создайте ветку и «сломайте» агента в `agent/agent.yaml`: например, поменяйте лимит отеля 150 → 300 и удалите правило про HR.
2. Откройте **pull request** → запустится **ci**.
3. ✔️ Ожидаемо: `run_eval.py` показывает FAIL на кейсах `hotel`/`unknown`, pass rate ниже 80 %, PR красный.
4. Верните правильные правила → CI зелёный.

> 💡 В **Settings → Branches** добавьте правило защиты `main` с обязательной проверкой `ci / eval-dev` —
> тогда плохую версию физически нельзя слить.

### Лаба 4 · Promotion, а не пересборка
1. Измените в `agent.yaml` одну безобидную фразу (например, добавьте «Отвечай вежливо») и пройдите PR → merge.
2. ✔️ Сравните: **тот же** `agent.yaml` создал версию и в `proj-dev`, и в `proj-prod`. Номера версий в проектах могут различаться — у каждого проекта своя история.

### Лаба 5 · Откат за секунды
1. **Actions → rollback → Run workflow**: `environment = prod`, `version = <предыдущая версия>`.
2. ✔️ Шаги «Было» / «Стало» показывают смену версии. Это секунды, потому что меняется **маршрутизация**, а не код.
3. Бонус: шаг «Автоматический откат» в `cd.yml` срабатывает сам, если smoke-проверка в prod упала.

### Лаба 6 · Version selector: latest vs pinned (тема 3)
1. Локально (после `az login`, `pip install -r requirements.txt`):
   ```bash
   python scripts/endpoint_routing.py show --env dev    # always use latest
   python scripts/endpoint_routing.py show --env prod   # pinned → N
   ```
2. Создайте новую версию в dev: `python scripts/deploy_agent.py --env dev` — в dev она **сразу** отвечает (latest).
3. Объясните себе, зачем шаг `protect` в `cd.yml`: без него при первом выпуске prod работал бы в режиме latest, и новая версия получала бы трафик **до** проверки.

### Лаба 7 · Observability (дополнительно)
1. Подключите к проекту Foundry ресурс **Application Insights** (портал Foundry → проект → трассировка/мониторинг).
2. Запустите `python scripts/run_eval.py --env prod` и найдите трассы ответов агента.
3. ✔️ Найдите: входы/выходы, задержку, вызовы модели.

### Лаба 8 · Безопасность «на ощупь»
1. В `infra/main.bicep` стоит `disableLocalAuth: true` — ключей API у ресурса нет. Попробуйте найти вкладку ключей в портале.
2. Временно уберите у себя роль `Foundry User` и запустите `deploy_agent.py` — получите отказ доступа, хотя вы Owner подписки. Верните роль.
3. ✔️ Вывод: Owner/Contributor = control plane; без роли data plane агента не создать.

---

## Важно: что по документации отличается от видео

В видео третий режим version selector — **Weighted (например 90/10, canary)**.
В текущей документации Microsoft по управлению агентами сказано, что **разделение трафика между версиями
не поддерживается**, и нужно задавать одно правило `FixedRatio` со 100 % трафика.
Поэтому в лабе есть только **latest** и **pinned**. На экзамене опирайтесь на материал курса,
но знайте, что платформа быстро меняется.

---

## Если что-то не так

| Симптом | Вероятная причина |
|---|---|
| `AADSTS70021: No matching federated identity record` | subject не совпадает: job должен иметь `environment:` ровно `infra`/`dev`/`prod`, а `GITHUB_REPO` в bootstrap — точное `owner/repo` |
| `azure/login` падает сразу | нет `permissions: id-token: write` |
| `bicep build`: ошибка в `.bicepparam` | не заполнены значения `<...>` |
| Развёртывание: модель/версия не найдена, `InvalidResourceProperties` | модель недоступна в регионе для `GlobalStandard` — смените модель или регион группы ресурсов |
| Развёртывание: имя ресурса уже занято | `foundryName` глобально уникален (это поддомен) — выберите другое |
| 403 при вызове агента | нет роли `Foundry User` (Owner/Contributor её не заменяют); роли применяются через несколько минут |
| 403 на `pin` | добавьте `Foundry Project Manager` |
| 429 | исчерпан TPM/RPM развёртывания — увеличьте `capacity` |
| Quality gate падает на правильном агенте | модель ответила другими словами — поправьте `expected_any` в `golden_set.jsonl` |

---

## Уборка

```bash
az group delete --name rg-foundry-cicd-lab-bicep --yes --no-wait
az ad app delete --id <AZURE_CLIENT_ID>
```

После удаления ресурс Foundry какое-то время хранится как «soft-deleted»;
чтобы освободить имя, его можно очистить (purge).

---

## Источники
- Create a Foundry resource using a Bicep file — Microsoft Learn
- Microsoft.CognitiveServices accounts / projects / deployments — Bicep reference (Microsoft Learn)
- Comparing Terraform and Bicep — Microsoft Learn
- Configure and share your Foundry agent / Manage hosted agents (version selector, FixedRatio) — Microsoft Learn
- Azure AI Projects client library for Python (`create_version`, `agent_reference`) — Microsoft Learn
- Connect GitHub Actions to Azure with OpenID Connect — Microsoft Learn
- Role-based access control for Microsoft Foundry — Microsoft Learn
