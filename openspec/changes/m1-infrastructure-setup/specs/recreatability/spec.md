# Spec Delta: recreatability

## Purpose

Доводить, що мережу можна знести без залишків і підняти знову з того самого коду, а зміни й ручні відхилення від коду видно до і після розгортання.

## ADDED Requirements

### Requirement: Teardown leaves no tagged resources
Після видалення стеку мережі в регіоні SHALL не лишатися жодного ресурсу з тегом `Project=capstone-kv`.

#### Scenario: Teardown is clean
- **GIVEN** задеплоєна мережа
- **WHEN** стек видалено і видалення завершилось
- **THEN** пошук ресурсів за тегом `Project=capstone-kv` у регіоні повертає порожній список
- **AND** немає ресурсів проєкту, створених руками поза стеком

### Requirement: Network is rebuilt from the same definition
Мережа SHALL підніматися з того самого коду до повністю створеного стану, з виміряною і записаною тривалістю видалення і створення.

#### Scenario: Rebuild succeeds
- **GIVEN** чистий після видалення регіон
- **WHEN** стек створено з того самого коду
- **THEN** стек у стані `CREATE_COMPLETE` і всі перевірки мережі проходять
- **AND** журнал містить виміряний час видалення і створення

### Requirement: Recreation problems are logged
Журнал відтворення SHALL записувати, що зламалось з першої спроби і як це виправлено, а якщо нічого — явно це вказувати.

#### Scenario: Nothing broke
- **GIVEN** перша спроба пройшла без проблем
- **WHEN** викладач читає журнал
- **THEN** журнал явно каже, що нічого не зламалось

### Requirement: Changes are previewed before redeploy
Перед повторним розгортанням проєкт SHALL показувати попередній перегляд змін (change set) для малої правки коду, не застосовуючи її.

#### Scenario: Small edit is previewed
- **GIVEN** мала правка коду мережі
- **WHEN** створено change set
- **THEN** збережено опис змін, які він зробив би
- **AND** change set видалено без застосування, правку відкочено

### Requirement: Manual drift is detected
Проєкт SHALL показувати, що виявлення drift позначає ресурс, змінений вручну поза кодом, і перестає його позначати після повернення значення з коду.

#### Scenario: Manual tag change is detected
- **GIVEN** тег на VPC вручну змінено в консолі
- **WHEN** запущено виявлення drift для стеку мережі
- **THEN** VPC позначена як `MODIFIED`, результат збережено

#### Scenario: Drift is cleared after manual restore
- **GIVEN** VPC позначена як `MODIFIED` через змінений вручну тег
- **WHEN** тег вручну повернуто до значення з коду і виявлення drift запущено повторно
- **THEN** стек і VPC позначені як `IN_SYNC`, результат збережено
