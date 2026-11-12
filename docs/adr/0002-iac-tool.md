# ADR-0002: IaC-інструмент — AWS CloudFormation

Status: Accepted

## Context

У M1 треба описати кодом мережу і IAM, знести мережу і підняти її знову з того самого коду (R7), показати change set і drift detection (контрольне питання 9). Анти-ціль `proposal.md`: жодних ресурсів, створених руками поза стеком.

Обмеження середовища:

- тільки AWS, у Sandbox Environment курсу AWS Academy Cloud Architecting;
- креденшели тимчасові (AWS Details → CLI), сесія обмежена таймером;
- чи зберігає пісочниця ресурси між сесіями, невідомо: це буде зафіксовано в `docs/sandbox.md` (`design.md`, Open Questions).

Лекція 3 (§6) порівнює два декларативні інструменти: Terraform/OpenTofu і CloudFormation. На прикладах курс показує CloudFormation (§7–10).

## Options considered

1. **AWS CloudFormation (YAML).**
   - За: state зберігає сам сервіс, стек живе в акаунті, і окремого state-файлу немає. Change sets і drift detection є вбудованими командами (`create-change-set`, `detect-stack-drift`). Ресурси типу `AWS::*` не тарифікуються. Курс показує саме цей інструмент.
   - Проти: тільки AWS. YAML багатослівний. Стек, що впав при створенні, лишається в `ROLLBACK_COMPLETE`, і його треба видалити перед повторною спробою.
2. **Terraform / OpenTofu (HCL).**
   - За: cloud-agnostic, є модулі, `terraform plan` — аналог change set. OpenTofu — форк з відкритою ліцензією і тим самим синтаксисом (лекція 3, §6).
   - Проти: state треба бутстрепити і зберігати самим. Remote backend в S3 — бакет, який має існувати до першого `apply`, тобто створюється поза IaC. Не гарантовано, що він переживе сесію пісочниці. Локальний `terraform.tfstate` прив'язаний до однієї машини, і його легко втратити. Втрачений state означає, що Terraform більше не знає про свої ресурси. Мультихмарність тут нічого не дає: середовище тільки AWS.
3. **Консоль або імперативні виклики AWS CLI.**
   - За: найшвидше для разового експерименту.
   - Проти: це не IaC. Немає бажаного стану, з якого можна відтворитися, немає preview змін і немає drift. Порушує анти-ціль «ресурси, створені руками поза стеком».
4. **AWS CDK.**
   - За: справжня мова програмування, цикли й абстракції.
   - Проти: генерує той самий CloudFormation, тобто додає шар і toolchain (Node.js, `cdk bootstrap` створює окремий bootstrap-стек з IAM roles, а саме їх пісочниця, очікувано, не дасть створити). Шаблон, який викладач розбирає рядок за рядком, стає згенерованим, а не написаним.

## Decision

Обрано **AWS CloudFormation, шаблони в YAML**. Деплой через `aws cloudformation deploy`. Перевірка шаблонів: `cfn-lint` і `aws cloudformation validate-template`.

Вирішальний аргумент: state живе в самому сервісі, і бутстрепити backend, який може не пережити сесію пісочниці, не треба. Другий аргумент — change sets і drift detection вбудовані, а їх вимагає R7.

## Consequences

- Рішення живе в коді так: шаблони `infra/network.yaml` і `infra/iam.yaml`, деплой мережі — `scripts/deploy-network.sh`, перевірка IAM-шаблону — `scripts/verify-iam.sh`, change set і drift — `scripts/recreate.sh` (`design.md`, таблиця реалізації).
- `deploy-network.sh` має видаляти стек у `ROLLBACK_COMPLETE` перед створенням (`design.md`, Risks).
- Між стеками дані передаються через Outputs/Exports і `Fn::ImportValue` (ADR-0003). Імпортований export не можна змінити чи видалити, поки його використовує інший стек.
- Перехід в іншу хмару означатиме переписування шаблонів. Це свідомий lock-in: капстоун живе тільки в AWS.
- Drift detection тільки показує відхилення, а не виправляє його. `deploy` з незміненим шаблоном — no-op, тому ручну зміну повертають вручну (`design.md`, recreatability).
