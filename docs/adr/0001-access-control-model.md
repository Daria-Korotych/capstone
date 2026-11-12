# ADR-0001: Модель контролю доступу для мультитенантних бакетів капстоуна

Status: Accepted

## Context

Капстоун — serverless key-value store. З M2 таблиці реєструються через API, і кожна таблиця належить своєму tenant. З M3 дані tenant потрапляють в S3 (лог реплікації, у M4 також snapshots). Розкладку вирішують у M2/M3: або бакет на tenant (`capstone-kv-<tenant>`), або префікс на tenant в одному бакеті. Кількість tenant не фіксована.

Вимога до моделі: principal одного tenant не читає й не пише дані іншого, і додавання tenant не змінює жодної policy. Створення бакета чи префікса для нового tenant — це автоматизований крок provisioning зі своїми дозволами, а не правка policy.

Обмеження середовища: Sandbox Environment курсу AWS Academy, очікувано, не дозволяє створювати власні IAM role і policy (`design.md`, Context); підтвердження буде в `docs/labrole.md`. Тому в M1 модель тільки описується. Read-only роль з R2/R3 (`infra/iam.yaml`) — окреме питання: це роль оператора для перегляду ресурсів, а не доступ tenant до даних.

Варіанти взято з практики 2 (`Class activities/1 CA task.md`, завдання 1–3; конспект `Практика 2.md`, §8–10).

## Options considered

1. **RBAC: role на кожен tenant і bucket policy.** Як `lab-hr` у завданні 1: `Principal` у bucket policy — ARN ролі tenant.
   - За: найпростіше пояснити, і в одній bucket policy видно, хто має доступ.
   - Проти: N tenant означає N roles і N правок policy. На питання практики «скільки політик змінити при 500 проєктах» відповідь — 500. Конспект (§9) називає це вибухом кількості ролей.
2. **PBAC / умови.** Як у завданні 2: `s3:prefix` у `Condition` для `ListBucket` і `s3:ExistingObjectTag/<key>` для `GetObject`.
   - За: в одному бакеті можна розділити tenant префіксами.
   - Проти: значення умов літеральні (`public/*`, `classification=public`), тож на кожен tenant потрібен ще один statement, і масштабується це не краще за RBAC. `ExistingObjectTag` перевіряє тільки вже записаний об'єкт, тому запис не захищає.
3. **ABAC: ресурс у policy залежить від тегу principal.** Як `lab-atlas` / `lab-nebula` у завданні 3: одна policy, principals різняться тільки тегом.
   - За: новий tenant — це нове значення тегу, policy не змінюється (`orion` у фіналі практики).
   - Проти: безпека тримається на тегах. Хто може поставити тег, той отримує чужий доступ (конспект, §9). Аудит складніший: «хто бачить X» означає зіставити policy з тегами, а не прочитати одну bucket policy.

## Decision

Обрано **ABAC** (варіант 3) з ключем тегу `tenant`. ARN ресурсу або умова виводиться з `${aws:PrincipalTag/tenant}`, і це однаково працює для обох розкладок:

- бакет на tenant: `Resource` `arn:aws:s3:::capstone-kv-${aws:PrincipalTag/tenant}` і `.../*`;
- префікс на tenant: `Resource` `arn:aws:s3:::capstone-kv-data/${aws:PrincipalTag/tenant}/*`, а `ListBucket` обмежено умовою `s3:prefix` = `${aws:PrincipalTag/tenant}/*`. Ім'я `capstone-kv-data` тут умовне.

Coordinator — один сервіс для всіх tenant, тому тег він ставить на сесію:

- identity policy ролі coordinator дозволяє `sts:AssumeRole` і `sts:TagSession` на роль доступу до даних. Обмеження «тільки coordinator» забезпечує не вона, а `Principal` у trust policy ролі доступу;
- trust policy ролі доступу — один statement: `Principal` — ARN ролі coordinator, `Action: ["sts:AssumeRole", "sts:TagSession"]`, `Condition`: `Null` `aws:RequestTag/tenant` = `false` (тег присутній) і `ForAllValues:StringEquals` `aws:TagKeys` = `["tenant"]`. Умови стоять на тому самому statement, що й `sts:AssumeRole`, тому `AssumeRole` без тегу `tenant` не збігається з жодним Allow і відхиляється;
- зміна цих policy і тегів ролей — тільки через деплой стеку інфраструктурною роллю.

Отже, межа довіри — coordinator. Ізоляція tenant тримається на тому, що coordinator ставить правильний `tenant` з автентифікованого запиту. Помилка в цьому коді дає доступ до чужих даних, і IAM цього не зупинить.

Головний аргумент — масштабування на N tenant без правок policy, ключова теза практики 2. Капстоун — greenfield, тож теги закладаються з першого ресурсу, і застереження конспекту (§9) щодо brownfield тут не діє.

## Consequences

- У M1 рішення існує тільки в цьому ADR. З M2 policy і roles описуються кодом у стеку `kv-app` (ADR-0003). Якщо пісочниця відмовить створювати IAM, відмову документують, як для `kv-iam`, а не обходять.
- Розкладка бакетів (бакет чи префікс на tenant) лишається рішенням M2/M3. Модель доступу від неї не залежить, змінюється тільки рядок `Resource`. Обидва варіанти вкладаються в область `capstone-kv-*` read-only policy з `infra/iam.yaml`.
- Сесію без тегу `tenant` взяти неможливо: trust policy її відхиляє. Тому «забутий тег» закриває доступ, а не відкриває.
- Кожен `AssumeRole` з тегом сесії потрапляє в CloudTrail, тож аудит доступу tenant — це пошук сесій з `tenant=X`.
- Код coordinator, що визначає `tenant`, — критичний для безпеки, і в M2 його покривають тестами на cross-tenant доступ.
