# Spec Delta: delivery

## Purpose

Описує інфраструктуру M2 кодом і конвеєр, що розгортає інфраструктуру й застосунок з коміту, щоб кожна зміна доходила до AWS одним і тим самим відтворюваним шляхом.

## ADDED Requirements

### Requirement: Application infrastructure is code
Стек `kv-app` SHALL описувати три інстанси t3.micro (coordinator і два шарди) у підмережі `kv-dev-public-1` з публічними IP, імпортуючи мережу з експортів `kv-network`; Security Group шардів SHALL приймати трафік на порт 8081 тільки від Security Group coordinator, а coordinator — на порт 8080.

#### Scenario: Template passes lint
- **GIVEN** `infra/app.yaml`
- **WHEN** запущено `cfn-lint`
- **THEN** немає помилок

#### Scenario: Shards are not reachable from outside
- **GIVEN** задеплоєний стек
- **WHEN** з довільної зовнішньої адреси звернутися до порту 8081 шарда
- **THEN** з'єднання не встановлюється, а запит від coordinator проходить

#### Scenario: Resources are tagged
- **GIVEN** задеплоєний стек
- **WHEN** переглянуто теги ресурсів
- **THEN** вони мають `Project=capstone-kv`, `Environment`, `Milestone=m2`, `Owner`

### Requirement: One image, two roles
Збірка SHALL створювати один Docker-образ, що запускає coordinator або шард залежно від ролі в змінній середовища.

#### Scenario: Both roles start from one image
- **GIVEN** зібраний образ
- **WHEN** його запущено з роллю `coordinator`, а потім з роллю `shard`
- **THEN** обидва контейнери відповідають на своєму порту (8080 і 8081)

### Requirement: Pipeline builds, tests and deploys
Пайплайн GitHub Actions SHALL на кожен коміт у `main` запускати lint і тести, збирати образ у GHCR з тегом за SHA коміту, а потім деплоїти стек з цим тегом, замінюючи інстанси.

#### Scenario: Commit reaches AWS
- **GIVEN** коміт у `main`, що проходить тести
- **WHEN** завершується пайплайн
- **THEN** образ з тегом за SHA існує в GHCR, стек у стані `UPDATE_COMPLETE` або `CREATE_COMPLETE`, а `GET /health` coordinator повертає 200

#### Scenario: Failing tests stop the deploy
- **GIVEN** коміт, що ламає тест
- **WHEN** виконується пайплайн
- **THEN** образ не публікується і стек не змінюється

### Requirement: Infrastructure changes are previewed
Пайплайн SHALL створювати change set для стеку `kv-app` перед його застосуванням і зберігати його опис у журналі прогону.

#### Scenario: Change set is visible
- **GIVEN** зміна в `infra/app.yaml`
- **WHEN** виконується пайплайн
- **THEN** у журналі є список змін до виконання деплою
