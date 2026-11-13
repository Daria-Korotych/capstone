# Tasks

## 1. Репозиторій і інструменти

- [x] 1.1 Ініціалізувати репозиторій `capstone` з порожнім README і `.venv` з `cfn-lint`, `cfn-flip`; перевірка: перший коміт на `main`, `.venv/bin/cfn-lint --version` працює

## 2. OpenSpec change для викладача

- [x] 2.1 `openspec init --tools claude` і окремий коміт `chore: initialise openspec`; перевірка: `openspec/config.yaml` існує
- [x] 2.2 Написати цей change (`proposal.md`, `design.md`, `tasks.md`, 4 `specs/*/spec.md`); перевірка: `openspec validate m1-infrastructure-setup --strict` без помилок і warnings
- [x] 2.3 Закомітити change до першого файлу в `infra/`; перевірка: `git log --oneline -- infra/ scripts/` порожній на момент коміту

## 3. ADR-0001…0004

- [x] 3.1 Написати `docs/adr/0001-access-control-model.md`, `0002-iac-tool.md`, `0003-stack-layout.md`, `0004-cidr-scheme.md` зі структурою Context / Options considered / Decision / Consequences; перевірка: `grep -L '## Options considered' docs/adr/*.md` порожній

## 4. Старт пісочниці і перевірка сесії

- [x] 4.1 [оператор] Стартувати Sandbox Environment, покласти CLI-креденшели в `~/.aws/credentials`, записати в `docs/sandbox.md` секції `## Session length`, `## Credit ceiling` (і `## Stated restrictions`, якщо є)
- [x] 4.2 Написати `scripts/env.sh` і `scripts/check-session.sh`; перевірка: з `AWS_SHARED_CREDENTIALS_FILE=/dev/null` exit 1, з реальними креденшелами exit 0 і stdout — одне слово, ім'я ролі
- [x] 4.3 Написати й запустити `scripts/sandbox-facts.sh`; перевірка: у `docs/sandbox.md` секція `## Run …` з роллю, account ID, регіонами (`us-east-1` = `allowed`) і `kv-network absent`

## 5. Розбір ролі сесії (access-control, R1)

- [x] 5.1 Написати й запустити `scripts/labrole-dissect.sh`; перевірка: exit 0, у `docs/evidence/labrole/` ≥ 9 файлів з префіксом ролі сесії
- [x] 5.2 Перевірити `aws iam get-role --role-name LabRole`; якщо роль існує і відрізняється — розібрати окремо, якщо `get-role` заборонений — записати як факт
- [x] 5.3 Видалити будь-який `kv-probe-*` ресурс, створення якого вдалося, і позначити дію як allowed
- [x] 5.4 Написати `docs/labrole.md`: фактична роль, таблиця, точний текст кожної відмови і її причина; перевірка: кожен рядок має evidence-файл і спосіб перевірки
- [x] 5.5 [оператор] Повторити 2–3 перевірки в консолі і додати рядки з `How found = console`

## 6. Мережевий стек (network, R4)

- [x] 6.1 Написати `scripts/verify-network.sh` з 11 перевірками з `design.md` (зокрема `MapPublicIpOnLaunch=false` у private, відсутність NAT Gateway, префікс тегу `Name`); перевірка: до деплою `FAIL stack exists`, exit 1
- [x] 6.2 Написати `infra/network.yaml`; перевірка: `cfn-lint` і `aws cloudformation validate-template` без помилок
- [x] 6.3 Написати `scripts/deploy-network.sh` і задеплоїти `kv-network`; перевірка: `verify-network.sh` 11×PASS, вивід у `docs/evidence/network/`
- [x] 6.4 [оператор + скрипт] Після нової сесії запустити `scripts/sandbox-facts.sh`; перевірка: записано `kv-network present` або `absent`, при `absent` README оновлено

## 7. Схема мережі (network, R4)

- [x] 7.1 Зберегти `describe-subnets` за тегом `Project` у `docs/evidence/network/subnets.json`
- [x] 7.2 Написати Mermaid-схему в `docs/network.md` і вставити в README; перевірка: кожен CIDR і AZ збігається з `subnets.json`

## 8. IAM-шаблон (access-control, R2, R3)

- [x] 8.1 Написати `scripts/verify-iam.sh`; перевірка: до шаблону FAIL
- [x] 8.2 Написати `infra/iam.yaml`; перевірка: `verify-iam.sh` усі PASS (або SKIP симулятора + статична перевірка PASS)
- [x] 8.3 Спробувати задеплоїти `kv-iam`, зберегти події стеку в `docs/evidence/iam/deploy-attempt.json`, видалити стек; перевірка: `describe-stacks --stack-name kv-iam` не знаходить стек
- [x] 8.4 Дописати в `docs/labrole.md` секцію `## Deploying kv-iam`: точний `ResourceStatusReason`, обмеження ролі, що його спричинило, і роль у звичайному акаунті

## 9. Квоти і бюджет (capacity-and-cost, R5, R6)

- [x] 9.1 Написати й запустити `scripts/quotas.sh`; перевірка: 3 файли в `docs/evidence/quotas/`
- [x] 9.2 [оператор] Якщо пісочниця не називає дозволені типи інстансів — перевірити в консолі EC2
- [x] 9.3 Написати `docs/quotas.md` з колонками `Quota | Value | Source | Needed in M2 | Risk`; перевірка: є всі 7 рядків зі спеки
- [x] 9.4 [оператор] Оцінка в AWS Pricing Calculator для двох режимів, share-лінк
- [x] 9.5 Написати `docs/budget.md`; перевірка: є обидва режими, кожен порівняний з кредитною стелею, різниця, що урізати першим, і явний список припущень (години сесій, EBS, transfer, метрики)

## 10. Відтворюваність, change set, drift (recreatability, R7)

- [x] 10.1 Change set на правці default `Environment`; перевірка: `describe-change-set` збережено, change set видалено, правку відкочено
- [x] 10.2 [оператор] Вручну змінити тег `Owner` на VPC; запустити drift detection; перевірка: VPC `MODIFIED`, вивід збережено
- [x] 10.3 Повернути тег вручну (консоль або `aws ec2 create-tags`) і повторити drift detection; перевірка: стек `IN_SYNC`, вивід збережено
- [x] 10.4 Написати й запустити `scripts/recreate.sh` (tagging-запит повторюється з паузою перед FAIL); перевірка: tagging API порожній після delete, `verify-network.sh` 11×PASS після create
- [x] 10.5 Написати `docs/recreate-log.md`: час delete і create, що зламалось і як виправлено, висновки по change set і drift з посиланнями на evidence

## 11. README, AI-критика, підготовка до захисту

- [x] 11.1 README: Prerequisites, Bring it up, Verify, Network, What changed in M1, посилання на ADR, цей change і `docs/*.md`, пояснення ролі проти групи; перевірка: у чистому клоні кроки README дослівно дають `verify-network.sh` 11×PASS
- [x] 11.2 [оператор] AI-критика архітектури в новій сесії, транскрипт у `docs/ai-critique.md` з прийнятими і спростованими пунктами
- [ ] 11.3 [оператор] Пройти 9 контрольних питань M1 вголос без нотаток

## Workflow follow-up

- Після захисту: `openspec archive m1-infrastructure-setup` — вимоги з'являються в `openspec/specs/{network,access-control,capacity-and-cost,recreatability}/spec.md`.
- `openspec validate --strict --all` без помилок, коміт `docs(openspec): archive m1 infrastructure setup`.
