# Відтворюваність мережевого стеку kv-network

## Перестворення (delete, потім create)

Скрипт `scripts/recreate.sh korotych`, повний вивід у [run-20261112T183712Z.txt](evidence/recreate/run-20261112T183712Z.txt).

| Фаза | Початок (UTC) | Тривалість |
|---|---|---|
| delete-stack + wait | 2026-11-12T18:37:13Z | 33 с |
| tagging API check | 2026-11-12T18:37:46Z | 1 с, порожньо з першої спроби |
| create (deploy-network.sh) | 2026-11-12T18:37:47Z | 70 с |
| verify-network.sh | 2026-11-12T18:38:57Z | 15 с, 11×PASS |

Разом 119 с. Лаг Tagging API не проявився, тому гілка повторів (одна початкова перевірка плюс до 3 повторів, кожен після паузи 30 с, тобто до 4 перевірок і 90 с очікування, потім exit 1) на практиці не перевірялась. Висновок «жодних ручно створених ресурсів проєкту поза стеком» підтверджений лише запитом за тегом `Project`: ручні ресурси без тегів він не показав би, це відома прогалина.

## Що ламалось з першої спроби

Під час перестворення нічого не зламалось. У Task 6 `verify-network.sh` спершу навмисно запускався проти ще не розгорнутого стеку і давав 11×FAIL (червоний етап TDD), після `deploy-network.sh` усі 11 перевірок стали PASS. Окремих збоїв деплою у звіті Task 6 немає.

## Change set

Default `Environment` у шаблоні тимчасово змінено локально з `dev` на `dev2` і водночас передано як `ParameterValue=dev2`. Change set створено й описано, потім видалено командою `delete-change-set` (не разом зі стеком), а правку шаблону відкочено (`git diff infra/network.yaml` порожній). Результат — change set `env-dev2`: 8× Modify (Vpc, InternetGateway, 4 підмережі, 2 route tables), у всіх `Replacement=False`, `Scope=Properties`, тобто змінюються лише теги, ресурси не перестворюються. Evidence: [change-set-env-dev2.json](evidence/recreate/change-set-env-dev2.json). Change set видалено, шаблон не змінено.

## Drift

Оператор змінив тег `Owner` на VPC в консолі AWS (VPC, Tags, Manage tags) з `korotych` на `manual-edit`. Після цього `detect-stack-drift` дав стек DRIFTED: `Vpc` у `MODIFIED`, решта 8 ресурсів `IN_SYNC`. Різниця: `/Tags/4/Value`, Expected `korotych`, Actual `manual-edit`, `NOT_EQUAL`. Evidence: [drift-modified.json](evidence/recreate/drift-modified.json).

Тег повернуто командою `aws ec2 create-tags`, бо `deploy` з незмінним шаблоном нічого не відкочує. Повторний detect: стек `IN_SYNC`, 9 ресурсів `IN_SYNC`. Evidence: [drift-in-sync.json](evidence/recreate/drift-in-sync.json).

Drift detection лише повідомляє про розбіжність і нічого не виправляє.

Статус на рівні стеку збережено для другого, повного циклу (оператор удруге змінив `Owner` у консолі, бо ідентифікатор першої детекції не зберегли): детекція `0894e140-dece-11f1-ac24-12fffd241d73` о 2026-11-12T19:19:51Z дала `StackDriftStatus` DRIFTED, 1 дрейфнутий ресурс — [drift-status-modified.json](evidence/recreate/drift-status-modified.json), різниця та сама (`/Tags/4/Value`, `korotych` → `manual-edit`) у [drift-modified.json](evidence/recreate/drift-modified.json). Після `aws ec2 create-tags` нова детекція о 19:20:08Z дала IN_SYNC, 0 дрейфнутих ресурсів — [drift-status-in-sync.json](evidence/recreate/drift-status-in-sync.json), [drift-in-sync.json](evidence/recreate/drift-in-sync.json); поточний `DriftInformation` стеку — [stack-drift-information.json](evidence/recreate/stack-drift-information.json).
