«LabRole» у завданні — умовна назва: у цій пісочниці такої ролі немає (`iam get-role --role-name LabRole` повертає `NoSuchEntity`), фактична роль сесії — `voclabs` (акаунт 804122474090).

Сесійне ім'я та UserId містять e-mail студента й скрізь замінені на `<session>`. Усі файли доказів — у `docs/evidence/labrole/`, генерує їх `scripts/labrole-dissect.sh` (повторний запуск перезаписує файли).

## Підсумок

| Action | Allowed/Denied | Evidence file | How found (console/CLI/simulator) |
| --- | --- | --- | --- |
| `sts:GetCallerIdentity` | Allowed | `voclabs-sts-get-caller-identity.txt` | CLI |
| `iam:GetRole` (`voclabs`) | Denied (explicit deny) | `voclabs-iam-get-role.txt` | CLI |
| `iam:GetRole` (`LabRole`) | Role does not exist (`NoSuchEntity`) | `voclabs-iam-get-role-LabRole.txt` | CLI |
| `iam:ListAttachedRolePolicies` | Allowed (`ReadOnlyAccess`) | `voclabs-iam-list-attached-role-policies.txt` | CLI |
| `iam:ListRolePolicies` | Allowed (inline `Pvoclabs`) | `voclabs-iam-list-role-policies.txt` | CLI |
| `iam:GetPolicy` / `iam:GetPolicyVersion` (`ReadOnlyAccess`) | Allowed | `voclabs-iam-get-policy-ReadOnlyAccess.txt`, `voclabs-iam-get-policy-version-ReadOnlyAccess.txt` | CLI |
| `iam:GetRolePolicy` (`Pvoclabs`) | Denied (explicit deny) | `voclabs-iam-get-role-policy-Pvoclabs.txt` | CLI |
| `iam:CreateUser` | Denied (no allow) | `voclabs-iam-create-user.txt` | CLI |
| `iam:CreateGroup` | Denied (no allow) | `voclabs-iam-create-group.txt` | CLI |
| `iam:CreatePolicy` | Denied (no allow) | `voclabs-iam-create-policy.txt` | CLI |
| `iam:CreateRole` | Denied (no allow); simulator: `implicitDeny` | `voclabs-iam-create-role.txt`, `voclabs-iam-simulate-principal-policy.txt` | CLI, simulator |
| `ec2:RunInstances` | Allowed (simulator, unverified) | `voclabs-iam-simulate-principal-policy.txt` | simulator |
| `ec2:CreateVpc` | Allowed (simulator, unverified) | `voclabs-iam-simulate-principal-policy.txt` | simulator |
| `s3:CreateBucket` | Allowed (simulator, unverified) | `voclabs-iam-simulate-principal-policy.txt` | simulator |
| `cloudformation:CreateStack` | Allowed (simulator, unverified) | `voclabs-iam-simulate-principal-policy.txt` | simulator |

Жодна `create-*` проба (`kv-probe-user`, `kv-probe-group`, `kv-probe-policy`, `kv-probe-role`) не вдалася, тому нічого видаляти не довелося і ресурсів не створено.

## Політики ролі

До `voclabs` прикріплена керована політика `arn:aws:iam::aws:policy/ReadOnlyAccess` (читається; усі її statements мають `Effect: Allow`, жодного `Deny`) та inline-політика `Pvoclabs`. Документ `Pvoclabs` прочитати неможливо: `iam:GetRolePolicy` заборонений явно. Тому конкретні statements, що дають `ec2`/`s3`/`cloudformation` та що забороняють `iam`, у документі не цитуються.

## Відмови: точний текст і причина

Помилки `GetRole` і `GetRolePolicy` містять фразу `with an explicit deny in an identity-based policy`. Це explicit deny. Statement назвати не можна: `ReadOnlyAccess` не містить `Deny`, отже заборона міститься в `Pvoclabs` (або іншій ідентифікаційній політиці), але її документ нечитний — причину до конкретного statement віднести неможливо.

- `iam:GetRole`: `User: arn:aws:sts::804122474090:assumed-role/voclabs/<session> is not authorized to perform: iam:GetRole on resource: role voclabs with an explicit deny in an identity-based policy.`
- `iam:GetRolePolicy`: `User: arn:aws:sts::804122474090:assumed-role/voclabs/<session> is not authorized to perform: iam:GetRolePolicy on resource: role voclabs with an explicit deny in an identity-based policy.`

Помилки `CreateUser`, `CreateGroup`, `CreatePolicy`, `CreateRole` містять фразу `because no identity-based policy allows the iam:<Action> action`. Це відсутність allow (implicit deny), а не явна заборона; жодного statement, що її спричиняє, немає за означенням — `ReadOnlyAccess` дає лише читання.

- `iam:CreateUser`: `... is not authorized to perform: iam:CreateUser on resource: arn:aws:iam::804122474090:user/kv-probe-user because no identity-based policy allows the iam:CreateUser action.`
- `iam:CreateGroup`: `... is not authorized to perform: iam:CreateGroup on resource: arn:aws:iam::804122474090:group/kv-probe-group because no identity-based policy allows the iam:CreateGroup action.`
- `iam:CreatePolicy`: `... is not authorized to perform: iam:CreatePolicy on resource: policy kv-probe-policy because no identity-based policy allows the iam:CreatePolicy action.`
- `iam:CreateRole`: `... is not authorized to perform: iam:CreateRole on resource: arn:aws:iam::804122474090:role/kv-probe-role because no identity-based policy allows the iam:CreateRole action.`

## Обмеження симулятора

Результат `simulate-principal-policy` обчислюється за ідентифікаційними політиками ролі й може не відображати SCP організації; реальним викликом він не підтверджений. Реальні create-виклики перевіряються розгортанням `kv-network` у Task 6 (та очікуваною помилкою `kv-iam` у Task 8).

## Console checks

Перевірки виконані в AWS Management Console (регіон N. Virginia, `us-east-1`) 2026-11-12 у тій самій сесії `voclabs`. Скріншоти не зберігаються в репозиторії, бо містять e-mail студента; нижче — точний текст із сесійним ім'ям, заміненим на `<session>`.

| Action | Allowed/Denied | Evidence file | How found (console/CLI/simulator) |
| --- | --- | --- | --- |
| `iam:GetRole` (`voclabs`, IAM → Roles → voclabs) | Denied (explicit deny) | — (текст нижче) | console |
| `iam:ListUsers` (IAM → Users) | Allowed: видно 1 користувача `awsstudent` | — | console |
| `iam:CreateUser` (`kv-probe-console`) | Denied (no allow); користувача не створено | — (текст нижче) | console |
| IAM Policy Simulator (console) | Denied: симулятор не запускається | — (текст нижче) | console |

- `iam:GetRole`: `Access denied to iam:GetRole. User: arn:aws:sts::804122474090:assumed-role/voclabs/<session>. Action: iam:GetRole. Context: an identity-based policy explicitly denies the action.` Збігається з CLI (`voclabs-iam-get-role.txt`).
- `iam:CreateUser`: `User was not created. User: arn:aws:sts::804122474090:assumed-role/voclabs/<session> is not authorized to perform: iam:CreateUser on resource: arn:aws:iam::804122474090:user/kv-probe-console because no identity-based policy allows the iam:CreateUser action.` Збігається з CLI (`voclabs-iam-create-user.txt`).
- Policy Simulator: `You don't have enough permissions to use the IAM Policy Simulator.` Консольний симулятор не запустився (ймовірна причина — явна заборона `iam:GetRole`/`iam:GetRolePolicy`, через яку він не може прочитати політики ролі; точну дію консоль не називає), тоді як CLI `simulate-principal-policy` відпрацював. На панелі симулятора для ролі `voclabs` позначено «AWS Organizations SCPs» — акаунт пісочниці входить до організації з SCP, тому результати CLI-симулятора лишаються непідтвердженими до реального виклику.
