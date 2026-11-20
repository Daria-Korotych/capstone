# Spec Delta: sharding

## Purpose

Розподіляє записи між шардами за consistent hashing і дає шардам зареєструватися самим, щоб набір шардів міг змінюватись без перезапуску coordinator.

## ADDED Requirements

### Requirement: Shards register themselves
Шард SHALL при старті викликати `POST /shards {id, url}` і повторювати виклик кожні 15 с. Нова реєстрація повертає 201, повторна з тим самим або оновленим `url` — 200, некоректне тіло — 400. `GET /shards` повертає `[{id, url}]`, `DELETE /shards/{id}` — 204.

#### Scenario: Shard joins at start
- **GIVEN** працює coordinator з `KV_MODE=sharded`
- **WHEN** стартує шард
- **THEN** `GET /shards` містить його `id` і `url`, а `GET /health` показує `shards` на одиницю більше

#### Scenario: Heartbeat is idempotent
- **GIVEN** зареєстрований шард
- **WHEN** він повторює реєстрацію з тим самим `url`
- **THEN** відповідь 200, а склад кільця не змінюється

#### Scenario: Shard removed
- **GIVEN** зареєстрований шард, процес якого зупинено
- **WHEN** надіслано `DELETE /shards/{id}`
- **THEN** відповідь 204 і шард зникає з `GET /shards` і з кільця та не повертається, бо heartbeat більше не приходить

#### Scenario: Live shard comes back
- **GIVEN** працюючий шард, якого видалено через `DELETE /shards/{id}`
- **WHEN** минає наступний heartbeat (до 15 с)
- **THEN** шард знову є в `GET /shards` і в кільці

### Requirement: Keys are placed by a consistent hash ring
Coordinator SHALL обирати шард стабільним хешем ключа `table + partition key` на кільці з віртуальними вузлами; sort key у хеші не бере участі, тож усі записи однієї партиції лежать на одному шарді. Хеш SHALL бути однаковим між процесами і перезапусками та SHALL NOT бути вбудованою `hash()` Python; обраний алгоритм — BLAKE2b з 64-бітним дайджестом, як записано в ADR-0006.

#### Scenario: Same key, same shard
- **GIVEN** незмінний набір шардів
- **WHEN** один ключ обчислюють багато разів, у тому числі після перезапуску coordinator
- **THEN** він завжди потрапляє на той самий шард

#### Scenario: Partition stays together
- **GIVEN** записи з однаковим partition key і різними sort key
- **WHEN** обчислено шард кожного
- **THEN** це завжди один шард

#### Scenario: Load is spread
- **GIVEN** кільце з двома шардами і велика кількість різних ключів
- **WHEN** підраховано ключі на шард
- **THEN** розкид відповідає допуску, записаному в ADR-0006

#### Scenario: Adding a shard moves only part of the keys
- **GIVEN** кільце з двома шардами і набір ключів
- **WHEN** додано третій шард
- **THEN** ключі, що змінили власника, всі перейшли на новий шард, а їхня частка близька до 1/3

### Requirement: Writes and reads follow the ring
Coordinator SHALL пересилати `PUT`, `GET`, `HEAD`, `DELETE` на шард, обраний кільцем, і повертати відповідь шарда з тими самими кодами, що й у single-node режимі.

#### Scenario: Round trip through a shard
- **GIVEN** два зареєстровані шарди
- **WHEN** записано, а потім прочитано запис
- **THEN** читання повертає записане значення, а запис є лише на шарді, обраному кільцем

### Requirement: Shard failures surface to the client
Coordinator SHALL викликати шард з connect timeout 0,5 с і read timeout 2,0 с без повторних спроб (M2). Недоступність шарда, timeout чи транспортна помилка SHALL давати 502 з тілом `{error, shard}`; якщо кільце порожнє в sharded режимі — 503.

#### Scenario: Shard is down
- **GIVEN** обраний кільцем шард не відповідає
- **WHEN** надіслано `GET` запису з його ключовою областю
- **THEN** відповідь 502 з `shard`, що вказує на цей шард

#### Scenario: Shard does not answer
- **GIVEN** обраний кільцем шард приймає з'єднання, але не відповідає
- **WHEN** надіслано запит до запису з його ключовою областю
- **THEN** відповідь 502 з `shard` приходить не пізніше ніж через 2,5 с

#### Scenario: No shards left
- **GIVEN** у режимі `sharded` процеси всіх шардів зупинено, а потім їх видалено через `DELETE /shards/{id}`
- **WHEN** надіслано запит до запису
- **THEN** відповідь 503
