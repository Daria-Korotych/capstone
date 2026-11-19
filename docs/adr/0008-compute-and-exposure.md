# ADR-0008: Обчислення і доступ ззовні — EC2 у public підмережі з публічними IPv4

Status: Accepted

**Рішення коротко:** coordinator і 2 шарди — 3 × `t3.micro` у `kv-dev-public-1` з публічними IPv4. Шарди приймають трафік лише від Security Group coordinator. Доповнює [ADR-0004](0004-cidr-scheme.md): у M2 private підмережі лишаються порожніми, а NAT і далі немає.

## Context

- Блокер M1: private підмережі не мають виходу в інтернет, тож інстанс там не стягне образ (`docs/m1/ai-critique.md`, ADR-0004).
- Потрібно три шляхи: вихід до GHCR, вхід клієнта (YCSB, curl) до coordinator, SSH для дебагу.
- Пісочниця не дає створити роль (`iam:CreateRole` denied, LabRole немає — `docs/m1/labrole.md`). Отже, немає instance profile, і SSM Session Manager не працює (`docs/m2/probes.md`).
- Проби (`docs/m2/probes.md`) усі ✅: P1 — публічний IP, P2 — заміна інстанса, P3 — pull з GHCR, P4 — SSH через EC2 Instance Connect.

## Options considered

Вартість за 3-годинну сесію, лише частина входу/виходу (EC2 однакові в усіх варіантах). Ціни — `docs/m1/budget.md`; NAT і ALB там позначені як приблизні.

| Варіант | Вартість / сесія | Вердикт |
|---|---|---|
| 1. Public підмережа + public IPv4 | 3 × $0.005 × 3 год = **$0.045** | **Обрано**: перевірено пробами P1, P3, P4 |
| 2. Private + NAT Gateway + ALB | NAT ≈ $0.045 × 3 = $0.135, ALB ≈ $0.0225 × 3 = $0.0675 + LCU, разом ≈ $0.20+ | Дорожче щонайменше вчетверо (≈ $0.20 проти $0.045); ALB ще й потребує підмереж у ≥ 2 AZ |
| 3. Private + NAT instance (`t3.micro`) | $0.0104 × 3 = $0.031 + вхід | Вхід для клієнта все одно потрібен (ALB або public IP), source/dest check треба вимкнути, і це ще один вузол в експлуатації |
| 4. Fargate | — | Потрібні IAM-ролі (task execution role для логів, service-linked role ECS), а створення ролей заборонено. Пробою не перевірялось |
| 5. Private + S3 gateway endpoint + власний AMI | $0 | GHCR — не сервіс AWS, endpoint до нього не веде; AMI на кожен коміт ламає ADR-0009 |

## Decision

- Усі 3 інстанси — у `kv-dev-public-1` (`kv-network-PublicSubnet1Id`), `AssociatePublicIpAddress: true` (P1).
- Одна AZ: бенчмарк без міжзонної затримки. Рознесення по AZ прийде з репліками в M3.

| Security Group | Inbound | Джерело |
|---|---|---|
| coordinator | `8080/tcp` | shard SG: реєстрація і heartbeat |
| coordinator | `8080/tcp` | `OperatorCidr` |
| coordinator | `8080/tcp` | `CiCidr`, якщо параметр не порожній |
| shard | `8081/tcp` | лише coordinator SG |
| обидві | `22/tcp` | `OperatorCidr` (P4) |

- Обидва напрямки всередині йдуть на **приватні** IP: шард шле heartbeat на приватну IP coordinator і реєструє свою приватну IP. Правило-посилання на SG діє лише для трафіку на приватні адреси VPC.
- `OperatorCidr` — обов'язковий параметр, **без значення за замовчуванням**, щоб у репозиторії не було особистої IP. Локальний деплой-скрипт передає `/32` того, хто викликає; CI читає GitHub variable `OPERATOR_CIDR`, яку виставляє `scripts/push-session-creds.sh`.
- `CiCidr` — необов'язковий; порожній означає, що правила немає. Deploy-job передає `/32` раннера для smoke-тесту `/health`.

## Consequences

- Плюс: $0.045 за сесію, без NAT і без жодної IAM-ролі.
- Мінус: кожен інстанс має публічну адресу. Порти шардів закриті SG, а API coordinator без автентифікації (non-goal) відкритий для `OperatorCidr` і `CiCidr`; це прийнятий ризик навчального середовища.
- Мінус: відмова однієї AZ кладе весь store (прийнятно до M3).
- Мінус: заміна інстанса під час деплою (P2) змінює публічну IP, тож після кожного деплою адресу coordinator треба брати заново.
- Мінус: `docs/m1/budget.md` рахує public IPv4 як $0 («не використовується»). Тепер стаття = 3 × 60 год × $0.005 = $0.90/міс у режимі сесій.
