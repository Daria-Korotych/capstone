# Spec Delta: benchmark

## Purpose

Фіксує базову лінію продуктивності шардованого сховища, з якою M3 і M5 порівнюватимуть свої результати.

## ADDED Requirements

### Requirement: YCSB runs against the REST API
Проєкт SHALL містити власний Java binding до YCSB, що виконує `insert`, `read`, `update`, `delete` через REST API coordinator, мапить ключ запису на таблицю та partition key і запускає workloads A (50% читання, 50% оновлення) і C (100% читання).

#### Scenario: Load and run complete
- **GIVEN** розгорнутий стек і створена таблиця для YCSB
- **WHEN** виконано фази load і run для workload A, потім для workload C
- **THEN** кожна фаза завершується без помилок операцій, а YCSB друкує підсумок із throughput і затримками

### Requirement: Numbers are stored with their conditions
Для кожного прогону проєкт SHALL зберігати сирий вивід YCSB і запис умов: workload, кількість записів і операцій, кількість потоків, тип і кількість інстансів, кількість шардів, кількість віртуальних вузлів, SHA коміту.

#### Scenario: Run is reproducible
- **GIVEN** запис умов прогону
- **WHEN** інший учасник повторює прогін з тих самих умов
- **THEN** він має всі параметри, потрібні для запуску, без звернення до автора

#### Scenario: Baseline is comparable later
- **GIVEN** збережена базова лінія
- **WHEN** в M3 запускають той самий workload з тими самими параметрами
- **THEN** результати можна порівняти за throughput і p50/p95/p99 затримками

### Requirement: Workload choice is justified
Документ бенчмарка SHALL пояснювати, чому обрано workloads A і C як представницькі для key-value store, відповідаючи на контрольне питання 8.

#### Scenario: Justification is present
- **GIVEN** `docs/m2/benchmark.md`
- **WHEN** викладач читає секцію про вибір workload
- **THEN** вона пояснює частку читань і записів кожного workload і чому scan-workload не обрано
