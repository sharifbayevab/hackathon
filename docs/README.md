# Примеры CSV-файлов

Маленький синтетический датасет: бинарная классификация по двум признакам (`x1`, `x2`). Цель — научить модель отличать «класс 0» (точки в верхне-левом углу) от «класса 1» (точки в нижне-правом).

| Файл | Назначение | Кто грузит |
|---|---|---|
| `example_train.csv` | Обучающие данные с ответами (id, x1, x2, target). 20 строк. | **Админ** → в админке поле «Файл с обучением» |
| `example_test_features.csv` | Признаки тестовой части (id, x1, x2). 10 строк. Можно вложить в train-файл вместе или отдельно — на твоё усмотрение, участники сами разберутся. | (опционально, можно вложить в train) |
| `example_sample_submission.csv` | Шаблон сабмита (id, answer). Все ответы заглушки. | **Админ** → в админке поле «Пример сабмита» |
| `example_groundtruth.csv` | Истинные ответы (id, answer, split). 5 public + 5 private. | **Админ** → в админке поле «Groundtruth» |
| `example_submission_perfect.csv` | Идеальный сабмит — даст 1.0 по public и private | **Участник** на /task |
| `example_submission_partial.csv` | Частично правильный сабмит — даст 0.6 на public, 0.8 на private (зависит от метрики) | **Участник** на /task |

## Как протестировать end-to-end

1. Зайди в админку (`/admin/login`, `admin/admin`).
2. Создай задачу:
   - **Title:** `Test classification`
   - **Description:** `Predict target for ids 21-30 based on x1, x2.`
   - **Metric:** `accuracy` (или попробуй `f1_binary`, `roc_auc`)
   - **Deadline:** через час от текущего UTC
   - **ID column:** `id`
   - **Answer column:** `answer`
   - **Train file:** `example_train.csv`
   - **Sample file:** `example_sample_submission.csv`
   - Нажми **Save**.
3. Загрузи **groundtruth** → `example_groundtruth.csv`. Должен показать `5 public, 5 private`.
4. Открой `/` в инкогнито (или другой браузер), войди как `Иван Иванов` / `Группа A`, перейди на `/task`.
5. Загрузи `example_submission_partial.csv` → увидишь public-балл.
6. Загрузи `example_submission_perfect.csv` → public-балл должен стать `1.00000`.
7. Открой `/leaderboard` — увидишь себя на первом месте с лучшим баллом.
8. После дедлайна лидерборд переключится на private-баллы автоматически.

## Формат groundtruth.csv

Обязательны 3 колонки. Имена `id` и `answer` берутся из настроек задачи (по умолчанию так и есть). Имя колонки `split` — фиксированное.

```csv
id,answer,split
1,0,public      # видно на лидерборде во время соревнования
2,1,private     # учитывается только в финале (после дедлайна)
```

- В каждой строке `split` должен быть строго `public` или `private`.
- Должны присутствовать оба типа.
- `id` уникальные.

## Формат сабмита участника

Только две колонки — `id` и `answer` (имена из настроек задачи).

```csv
id,answer
1,0
2,1
```

- Один прогноз на каждый `id` из groundtruth.
- Никаких лишних колонок.
- Для метрик типа `roc_auc`, `log_loss` в `answer` пиши вероятности (0..1), для `accuracy`, `f1_*` — округлённые классы.
