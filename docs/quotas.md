# Квоти

Джерела: `scripts/quotas.sh` зберігає `aws service-quotas list-service-quotas` у `docs/evidence/quotas/{ec2,vpc,cloudformation}.json` (читання дозволене, відмов немає) і пробу типів інстансів у `docs/evidence/quotas/instance-types.txt`. Регіон `us-east-1`, роль `voclabs`. M2 = coordinator + 2 шарди = 3 інстанси найдешевшого дозволеного типу `t3.micro` (2 vCPU, ціна в [budget.md](budget.md)).

| Quota | Value | Source (CLI/sandbox) | Needed in M2 | Risk |
|---|---|---|---|---|
| Running On-Demand Standard (A, C, D, H, I, M, R, T, Z) instances, `L-1216C47A` (ліміт vCPU) | 256 vCPU | CLI (`ec2.json`) | 3 × 2 vCPU = 6 vCPU (арифметика) | Ні: 6 з 256 |
| Дозволені типи інстансів | `t2.micro`, `t3.micro`, `t3.small`, `t3.medium`, `t2.medium` дозволені; `m5.large`, `c5.large` заборонені | sandbox (`ec2 run-instances --dry-run`, `instance-types.txt`) | 3 × `t3.micro` | Ні для t-серії; Так для m5/c5: явна заборона (explicit deny) в identity-based policy |
| Дозволені регіони | `us-east-1`, `us-west-2` | sandbox (`docs/sandbox.md`) | `us-east-1` | Ні |
| VPCs per Region, `L-F678F1CE` | 5 | CLI (`vpc.json`) | 1 (`kv-network`) | Ні: у регіоні зараз 2 VPC (default + `kv-network`, `describe-vpcs`), 3 вільні |
| EC2-VPC Elastic IPs, `L-0263D0A3` | 5 | CLI (`ec2.json`) | 0: NAT Gateway у M1 немає (ADR-0004); 1 EIP, якщо M2 додасть NAT | Ні: 0 з 5 |
| Network interfaces per Region, `L-DF5E4CA3` | 5000 | CLI (`vpc.json`) | 3 первинні ENI інстансів, до 4 з одним endpoint | Ні |
| VPC security groups per Region, `L-E79EC296` | 2500 | CLI (`vpc.json`) | 2–3 (coordinator, shard, за потреби endpoint) | Ні |
| Security groups per network interface, `L-2AFB9258` | 5 | CLI (`vpc.json`) | 1–2 на інстанс | Ні |
| Stacks (CloudFormation), `L-0485CB21` | 2000 | CLI (`cloudformation.json`) | 3 (`kv-network`, `kv-iam` — шаблон не розгортається, `kv-app`) | Ні |

Усі значення прочитані з сервісу квот, тож запасних джерел не знадобилося. Квоти vCPU і типів не є вузьким місцем; реальні обмеження M2 — кредитна стеля і тривалість сесії (див. [budget.md](budget.md)).
