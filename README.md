# Capstone

A light DynamoDB-like key-value store capstone for Cloud Architectures 2026/27.

## Network

VPC, subnets and routing: see [docs/network.md](docs/network.md).

## Access

Доступ тільки для читання описано в `infra/iam.yaml`: політика `ReadOnlyPolicy` і роль `ReadOnlyRole`, яку може взяти лише principal, переданий параметром `TrustedPrincipalArn`. Рецензент викликає `sts:AssumeRole` і отримує тимчасові креденшели з правами перегляду (мережа, стеки проєкту, метадані бакетів, моніторинг, квоти) без запису й без вмісту об'єктів; це краще за групу користувачів, бо креденшели самі спливають, а не лишаються постійним членством. Пісочниця не дозволила створити цей стек (`iam:CreatePolicy` заборонено), подробиці й точний текст відмови: [docs/labrole.md](docs/labrole.md#deploying-kv-iam).
