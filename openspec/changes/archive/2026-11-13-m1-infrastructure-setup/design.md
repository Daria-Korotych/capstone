# Design: M1 — Infrastructure setup

## Context

Мотивація — у `proposal.md` (Why). Тут тільки обмеження, які формують підхід.

- **Середовище:** Sandbox Environment курсу AWS Academy Cloud Architecting (`ACAv3EN-US-LTI13-187070`). Learner Lab не використовується, особистий акаунт теж. Де первинна спека пише «Learner Lab», мається на увазі ця пісочниця.
- **Роль:** «LabRole» у завданні — умовна назва. Досліджується роль, під якою реально працює сесія; її ім'я береться з `aws sts get-caller-identity` (сегмент після `assumed-role/`) і в коді не прописується. Якщо в акаунті окремо існує роль `LabRole`, її розбирають теж.
- **Регіон:** `us-east-1`, задається в одному місці (`scripts/env.sh`); якщо пісочниця його не дозволяє, регіон міняється там.
- **Креденшели** тимчасові (AWS Details → CLI), сесія обмежена таймером.
- **IAM:** власні policy і role створювати/прив'язувати не можна — це очікується, і саме це документується.
- **Бюджет:** кредитна стеля з AWS Details; записується фактичне значення, не припущення.
- **AI-політика курсу:** генерувати код можна тільки після спеки й ADR.

## Goals / Non-Goals

**Goals:**

- Інфраструктурні вимоги (R2–R4, R7) перевіряються скриптом, що падає з ненульовим кодом, якщо умова не виконана: спершу пишемо перевірку, бачимо, що вона падає, потім шаблон.
- R1, R5, R6 і пояснення в README — документні артефакти; їх перевіряють читанням (кожне твердження має посилання на evidence).
- Сирий вивід команд, що доводять твердження, лежить у `docs/evidence/<тема>/`, і документи на нього посилаються.

**Non-Goals:**

- Автоматизація кроків, що вимагають браузера або консолі пісочниці (старт сесії, Pricing Calculator, ручна зміна тегу для drift) — їх робить оператор.

## Decisions

| Рішення | Вибір | Відкинуто | ADR |
|---|---|---|---|
| IaC-інструмент | AWS CloudFormation (YAML) | Terraform/OpenTofu: state backend треба бутстрепити поза IaC, і не гарантовано, що він переживе сесію пісочниці; курс показує CFN; change sets і drift detection — частина контрольних питань | ADR-0002 |
| Розбиття на стеки | `kv-network` (static, рідко змінюється) окремо від `kv-iam` (шаблон-демонстрація) і майбутнього `kv-app` (M2, dynamic) | Один стек: зміна застосунку зачіпала б мережу; поділ за частотою змін, як у лекції 3 §10 | ADR-0003 |
| CIDR | VPC `10.20.0.0/16`; public `10.20.0.0/24`, `10.20.1.0/24`; private `10.20.10.0/24`, `10.20.11.0/24`; 2 AZ | `/28` підмережі: мало запасу (11 адрес, менше за `/27`, який AWS вимагає для підмереж ALB), а CIDR підмережі незмінний; одна AZ: M3 потребує реплік у різних зонах | ADR-0004 |
| Модель доступу | ADR-001 з домашки практики 2 (RBAC / PBAC / ABAC для мультитенантних бакетів): ABAC за тегом `tenant` | RBAC (role на tenant: N ролей і N правок policy), PBAC / умови (літеральні значення, statement на tenant) | ADR-0001 |

### Decision: AZ не прописуються

AZ підмереж — `!Select [0|1, !GetAZs '']`, а не жорсткі імена: жорстко прописана AZ може бути недоступна в акаунті пісочниці.

### Decision: Без NAT Gateway

Private route table не має маршрутів, крім `local`. NAT коштує щогодини, а в M1 private підмережам інтернет не потрібен (ADR-0004).

### Decision: Перевірки — bash + AWS CLI + jq

Кожна перевірка — окремий рядок `PASS/FAIL <назва>`, exit 1 якщо є FAIL. Перевірку пишуть раніше за шаблон і спершу бачать, що вона падає.

### Відповідність вимог реалізації

| Capability | Реалізація | Перевірка |
|---|---|---|
| `access-control` (R1) | `scripts/labrole-dissect.sh [role]`: `sts get-caller-identity`, `iam get-role`, `list-attached-role-policies`, `list-role-policies`, `get-policy` + `get-policy-version` / `get-role-policy`, спроби `iam create-user|create-group|create-policy|create-role` з іменем `kv-probe-*`, `iam simulate-principal-policy` для `ec2:RunInstances ec2:CreateVpc iam:CreateRole s3:CreateBucket cloudformation:CreateStack`; не зупиняється на `AccessDenied` | `docs/labrole.md`, `docs/evidence/labrole/` |
| `access-control` (R2, R3) | `infra/iam.yaml`: `ReadOnlyPolicy` (`AWS::IAM::ManagedPolicy`; `Describe*`/`List*`/`Get*` метаданих для `ec2`, `cloudformation`, `s3` без `s3:GetObject*`, `servicequotas`; `cloudwatch:Describe*`/`List*` — аларми й перелік метрик, без точок даних метрик. `Resource: "*"` — тільки для `List*`/`Describe*` без resource-level permissions (`ec2:Describe*`, `s3:ListAllMyBuckets`, `cloudformation:ListStacks`, `cloudwatch`, `servicequotas`), з YAML-коментарем, чому. `s3:GetBucket*` обмежено `arn:aws:s3:::capstone-kv-*`, `cloudformation:Describe*`/`Get*` — `arn:aws:cloudformation:${AWS::Region}:${AWS::AccountId}:stack/kv-*/*`) і `ReadOnlyRole` (`AWS::IAM::Role`, trust `Principal: { AWS: !Ref TrustedPrincipalArn }`, `sts:AssumeRole`) | `scripts/verify-iam.sh`: `cfn-lint`, `validate-template`, `cfn-flip` → `iam simulate-custom-policy`; якщо симулятор заборонений — `SKIP` і статична перевірка префіксів дій. Спроба `deploy --stack-name kv-iam --capabilities CAPABILITY_NAMED_IAM`, `describe-stack-events` → `docs/evidence/iam/deploy-attempt.json`, далі `delete-stack` |
| `network` (R4) | `infra/network.yaml`: `AWS::EC2::VPC`, `InternetGateway` + `VPCGatewayAttachment`, 4 × `Subnet`, `PublicRouteTable` з `Route 0.0.0.0/0 → IGW` (`DependsOn` attachment), `PrivateRouteTable` без маршрутів, 4 × `SubnetRouteTableAssociation`; параметри `Environment` (default `dev`), `ApplicationName` (default `kv`), `Owner` (без default); імена `!Sub '${ApplicationName}-${Environment}-...'`; exports `kv-network-VpcId`, `-PublicSubnet1Id`, `-PublicSubnet2Id`, `-PrivateSubnet1Id`, `-PrivateSubnet2Id`. Деплой — `scripts/deploy-network.sh <Owner>` (`aws cloudformation deploy`, видаляє стек у `ROLLBACK_COMPLETE`) | `scripts/verify-network.sh`: 11 перевірок — (1) стан стеку, (2) CIDR VPC, (3) 4 CIDR підмереж, (4) різні AZ, (5) `MapPublicIpOnLaunch=true` у public і `false` у private, (6) маршрут `0.0.0.0/0` на `igw-`, (7) тільки `local` у private, (8) 4 теги, (9) 5 exports, (10) у VPC немає NAT Gateway (`describe-nat-gateways`), (11) тег `Name` кожного позначеного ресурсу починається з `${ApplicationName}-${Environment}-`. Схема — Mermaid у `docs/network.md`, звірена з `describe-subnets` |
| `capacity-and-cost` (R5, R6) | `scripts/quotas.sh`: `service-quotas list-service-quotas` для `ec2`, `vpc`, `cloudformation` → `docs/evidence/quotas/`. Pricing Calculator (`us-east-1`): 3 × найдешевший дозволений тип; 730 год/міс і `<N>` год/міс сесій. Припущення, які `docs/budget.md` має явно перелічити: 3 × gp3 8 GiB, 10 GB transfer на місяць, CloudWatch basic + 10 метрик, `<N>` годин сесій | `docs/quotas.md`, `docs/budget.md`, кредитна стеля з `docs/sandbox.md` |
| `recreatability` (R7) | `scripts/recreate.sh`: `delete-stack kv-network` → `wait stack-delete-complete` → `resourcegroupstaggingapi get-resources --tag-filters Key=Project,Values=capstone-kv` → `deploy-network.sh` → `verify-network.sh`, з мітками часу. Change set: `create-change-set` / `describe-change-set` / `delete-change-set` на правці default `Environment`. Drift: ручна зміна тегу `Owner` на VPC → `detect-stack-drift` → `describe-stack-resource-drifts` (VPC `MODIFIED`) → тег повертається вручну (консоль або `aws ec2 create-tags`) → повторний `detect-stack-drift` (`IN_SYNC`). `aws cloudformation deploy` з незміненим шаблоном — no-op і drift не прибирає | `docs/recreate-log.md`, `docs/evidence/recreate/` |

Теги на всіх ресурсах, що їх підтримують: `Project=capstone-kv`, `Environment`, `Milestone=m1`, `Owner`. Інструменти: AWS CLI v2, `cfn-lint`, `cfn-flip` (у `.venv`), bash + jq.

## Risks / Trade-offs

- [Сесія пісочниці протухла посеред деплою] → `scripts/check-session.sh` — перший рядок кожного deploy/verify-скрипта; падає з «Sandbox session missing or expired», а не лишає півстека.
- [Стек у `ROLLBACK_COMPLETE` блокує `create-stack` з тим самим ім'ям] → deploy-скрипт видаляє такий стек перед створенням.
- [Жорстко прописана AZ недоступна] → `!GetAZs`; перевірка, що підмережі одного типу в різних AZ.
- [Команда пішла не в той регіон] → `verify-network.sh` шукає VPC за тегом `Project` саме в регіоні з `scripts/env.sh`.
- [Teardown лишив ресурси поза стеком] → перевірка через Resource Groups Tagging API.
- [Tagging API показує щойно видалені ресурси із затримкою] → перевірка teardown повторює запит з паузою протягом обмеженого часу, перш ніж видати FAIL.
- [Пісочниця може не зберігати ресурси між сесіями] → `scripts/sandbox-facts.sh` перевіряє це в першій сесії після деплою мережі; якщо не зберігає, `deploy-network.sh` стає першим кроком кожної сесії.
- [Пісочниця може не показувати кредитну стелю] → ліміт береться від викладача і записується.

## Open Questions

- Чи зберігає Sandbox Environment ресурси між сесіями — з'ясовується `scripts/sandbox-facts.sh`; відповідь змінює тільки порядок кроків у README.
- Значення кредитної стелі, довжини сесії і квот — записуються з пісочниці, не припускаються.
