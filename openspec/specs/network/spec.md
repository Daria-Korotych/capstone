# network Specification

## Purpose
Дає мережевий фундамент для M2 і M3: VPC з публічними і ізольованими приватними підмережами у двох зонах доступності, позначену тегами і з опублікованими ідентифікаторами, щоб наступні стеки будувались поверх неї, не змінюючи її.

## Requirements

### Requirement: Address plan across two zones
Мережа SHALL складатися з однієї VPC `10.20.0.0/16` з public підмережами `10.20.0.0/24` і `10.20.1.0/24` та private підмережами `10.20.10.0/24` і `10.20.11.0/24`, де підмережі одного типу лежать у різних зонах доступності.

#### Scenario: Subnets of each type are in different zones
- **GIVEN** задеплоєна мережа
- **WHEN** переглянуто зони доступності підмереж
- **THEN** дві public підмережі лежать у різних зонах і дві private підмережі лежать у різних зонах

#### Scenario: No overlap
- **GIVEN** задеплоєна мережа
- **WHEN** порівняно CIDR усіх чотирьох підмереж
- **THEN** вони не перетинаються і всі лежать у `10.20.0.0/16`

#### Scenario: Deployed in the expected region
- **GIVEN** мережа, позначена тегом проєкту
- **WHEN** її шукають у регіоні проєкту
- **THEN** VPC знайдена саме там, а не в іншому регіоні

### Requirement: Public subnets reach the internet
Кожна public підмережа SHALL мати маршрут `0.0.0.0/0` на Internet Gateway і автоматично призначати публічні IP новим інстансам.

#### Scenario: Public route table points to the gateway
- **GIVEN** задеплоєна мережа
- **WHEN** переглянуто route table public підмережі
- **THEN** є маршрут `0.0.0.0/0` на Internet Gateway
- **AND** підмережа автоматично призначає публічні IP

### Requirement: Private subnets are isolated
Кожна private підмережа SHALL мати тільки локальний маршрут у межах VPC і не призначати публічних IP.

#### Scenario: Private route table has only the local route
- **GIVEN** задеплоєна мережа
- **WHEN** переглянуто route table private підмережі
- **THEN** у ній є тільки маршрут `local` і немає маршруту в інтернет
- **AND** підмережа не призначає публічних IP

#### Scenario: No NAT gateway is created
- **GIVEN** задеплоєна мережа
- **WHEN** переглянуто ресурси мережі
- **THEN** NAT Gateway відсутній

### Requirement: Network resources are tagged
Кожен мережевий ресурс, що підтримує теги, SHALL мати теги `Project=capstone-kv`, `Environment`, `Milestone=m1` і `Owner`.

#### Scenario: Every network resource carries all four tags
- **GIVEN** задеплоєна мережа
- **WHEN** переглянуто VPC, кожну підмережу, кожну route table та Internet Gateway
- **THEN** кожен має `Project=capstone-kv`, `Milestone=m1` і непорожні `Environment` та `Owner`
- **AND** жоден із цих ресурсів не пропущено в пошуку за тегом `Project=capstone-kv`

### Requirement: Names follow application and environment
Імена мережевих ресурсів SHALL утворюватися з назви застосунку і середовища, переданих як параметри розгортання.

#### Scenario: Names reflect parameters
- **GIVEN** мережа, задеплоєна з назвою застосунку і середовищем за замовчуванням
- **WHEN** переглянуто тег `Name` ресурсів
- **THEN** кожне ім'я починається з `<назва застосунку>-<середовище>-`

### Requirement: Network identifiers are published
Мережа SHALL публікувати ідентифікатор VPC і ідентифікатор кожної з чотирьох підмереж як експорти, які може імпортувати наступний стек.

#### Scenario: Exports are listed
- **GIVEN** задеплоєна мережа
- **WHEN** перелічено експорти регіону
- **THEN** серед них є ідентифікатор VPC і ідентифікатори всіх чотирьох підмереж

### Requirement: Network diagram matches deployment
README проєкту SHALL містити схему VPC → зони доступності → підмережі → route tables → Internet Gateway, де кожен CIDR і зона збігаються із задеплоєною мережею.

#### Scenario: Diagram is checked against the stack
- **GIVEN** схема в README проєкту і задеплоєна мережа
- **WHEN** порівняно CIDR і зону кожної підмережі
- **THEN** усі значення збігаються
