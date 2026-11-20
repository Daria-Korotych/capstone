# Spec Delta: kv-api

## Purpose

Дає клієнтам один контракт для реєстрації таблиць і CRUD над записами та coordinator, що його виконує, спершу в single-node режимі.

## ADDED Requirements

### Requirement: Contract is written before the implementation
Репозиторій SHALL містити `api/openapi.yaml` (OpenAPI 3.1, англійською), що описує рівно операції M2: створення і перегляд таблиць, `PUT`/`GET`/`HEAD`/`DELETE` записів, реєстрацію шардів і `GET /health`, з кодами відповідей і схемою помилки `{error, detail?}`.

#### Scenario: Contract is valid
- **GIVEN** файл `api/openapi.yaml`
- **WHEN** його перевірено валідатором OpenAPI
- **THEN** валідатор не повертає помилок

#### Scenario: Contract is older than the code
- **GIVEN** історія комітів
- **WHEN** переглянуто коміти, що торкаються `src/kv/`
- **THEN** коміт із `api/openapi.yaml` старший за перший коміт у `src/kv/`

### Requirement: Tables are registered with a key schema
Coordinator SHALL створювати таблицю за `{name, partition_key, sort_key?}`, де `name` відповідає `^[A-Za-z0-9_-]{1,64}$`; повторний ідентичний запит повертає 200, а запит з іншими ключами для наявного імені — 409.

#### Scenario: New table
- **GIVEN** таблиці `users` немає
- **WHEN** надіслано `POST /tables` з коректним тілом
- **THEN** відповідь 201 і `GET /tables/users` повертає визначення

#### Scenario: Identical repeat
- **GIVEN** таблиця `users` з ключем `id`
- **WHEN** надіслано той самий `POST /tables`
- **THEN** відповідь 200 і нічого не змінилось

#### Scenario: Conflicting definition
- **GIVEN** таблиця `users` з ключем `id`
- **WHEN** надіслано `POST /tables` для `users` з іншим `partition_key`
- **THEN** відповідь 409

#### Scenario: Invalid name
- **GIVEN** ім'я таблиці `bad name!`
- **WHEN** надіслано `POST /tables`
- **THEN** відповідь 400 з тілом `{error}`

### Requirement: Items are created and replaced by PUT
`PUT /tables/{table}/items/{pk}` (з `?sk=`, якщо таблиця має `sort_key`) SHALL зберігати тіло запиту як запис за ключем зі шляху і повертати 201 для нового запису та 200 для заміни наявного. Атрибути ключа в тілі необов'язкові; якщо вони є, то SHALL дорівнювати значенням зі шляху, інакше 400. Невідома таблиця — 404; `sk`, що не відповідає схемі таблиці, — 400.

#### Scenario: New and replaced item
- **GIVEN** таблиця `users` з ключем `id`
- **WHEN** двічі надіслано `PUT /tables/users/items/u1`
- **THEN** перша відповідь 201, друга 200, а `GET` повертає другий варіант з `id=u1`

#### Scenario: Body key differs from path
- **GIVEN** таблиця `users` з ключем `id`
- **WHEN** надіслано `PUT /tables/users/items/u1` з тілом `{"id": "u2"}`
- **THEN** відповідь 400

### Requirement: Items are read, checked and deleted by key
`GET`, `HEAD` і `DELETE` за `/tables/{table}/items/{pk}` SHALL приймати `sk` тоді й лише тоді, коли таблиця має `sort_key`. `GET` повертає 200 із записом або 404; `HEAD` — 200 або 404 без тіла; `DELETE` ідемпотентний і повертає 204, навіть якщо запису немає. Невідома таблиця — 404; `sk`, що не відповідає схемі таблиці, — 400.

#### Scenario: Read and exists
- **GIVEN** збережений запис `u1`
- **WHEN** надіслано `GET` і `HEAD` для `u1`
- **THEN** `GET` повертає 200 із записом, `HEAD` повертає 200

#### Scenario: Missing item
- **GIVEN** запису `nope` немає
- **WHEN** надіслано `GET` і `HEAD`
- **THEN** обидві відповіді 404

#### Scenario: Delete is idempotent
- **GIVEN** запис `u1`
- **WHEN** двічі надіслано `DELETE`
- **THEN** обидві відповіді 204 і `HEAD` повертає 404

#### Scenario: Sort key mismatch
- **GIVEN** таблиця з `sort_key`, а запит без `sk`
- **WHEN** надіслано `GET`
- **THEN** відповідь 400

#### Scenario: Compound key
- **GIVEN** таблиця з `partition_key=user` і `sort_key=ts`
- **WHEN** збережено два записи з однаковим `user` і різним `ts`
- **THEN** кожен читається окремо за своєю парою `pk` + `sk`

### Requirement: Coordinator reports health and mode
`GET /health` SHALL повертати 200 з `{status, mode, shards}`, де `mode` — режим, заданий при старті змінною `KV_MODE` (`single` або `sharded`, за замовчуванням `sharded`); автоматичного переходу між режимами немає.

#### Scenario: Single-node mode
- **GIVEN** coordinator запущено з `KV_MODE=single`
- **WHEN** надіслано `GET /health`
- **THEN** `mode` дорівнює `single`, записи зберігаються і читаються самим coordinator, а реєстрація шардів не впливає на маршрутизацію

### Requirement: Error bodies have one shape
Відповіді з помилкою SHALL мати тіло `{error, detail?}`; відповідь 502 додатково містить `shard`.

#### Scenario: Unknown table
- **GIVEN** таблиці `ghost` немає
- **WHEN** надіслано `GET /tables/ghost`
- **THEN** відповідь 404 з тілом `{error}`
