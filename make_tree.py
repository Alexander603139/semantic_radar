import os

# Текст вашей структуры
tree_text = """
semantic-radar/
├── docker-compose.yml
├── .env.example
├── README.md
│
├── services/
│   ├── ingestor/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── .env (опционально)
│   │   └── src/
│   │       ├── __init__.py
│   │       ├── main.py          # FastAPI приложение
│   │       ├── config.py
│   │       ├── models.py        # Pydantic схемы
│   │       ├── parser.py        # логика парсинга (httpx, playwright)
│   │       └── routes.py        # эндпоинты
│   │
│   ├── embedder/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── main.py
│   │       ├── config.py
│   │       ├── models.py
│   │       ├── embedder.py      # загрузка модели MiniLM, вычисление
│   │       └── routes.py
│   │
│   ├── storage/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── main.py
│   │       ├── config.py
│   │       ├── models.py
│   │       ├── file_manager.py  # работа с Parquet, изоляция по user_id
│   │       └── routes.py
│   │
│   ├── analyzer/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── main.py
│   │       ├── config.py
│   │       ├── models.py
│   │       ├── clustering.py    # HDBSCAN + UMAP
│   │       ├── drift.py         # Wasserstein EMD
│   │       └── routes.py
│   │
│   ├── reporter/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── main.py
│   │       ├── config.py
│   │       ├── models.py
│   │       ├── plot_generator.py # Plotly HTML
│   │       ├── yandex_gpt.py    # опционально, вызов YandexGPT
│   │       └── routes.py
│   │
│   └── user_manager/
│       ├── Dockerfile
│       ├── requirements.txt
│       └── src/
│           ├── main.py
│           ├── config.py
│           ├── models.py
│           ├── auth.py          # JWT, хеширование
│           ├── db.py            # SQLite/PostgreSQL
│           └── routes.py
│
├── shared/                      # общие утилиты (опционально)
│   ├── __init__.py
│   └── schemas.py               # общие Pydantic-модели (User, Article и т.п.)
│
└── data/                        # монтируемый том (на сервере) - НЕ в репозитории
    └── users/
        └── {user_id}/
            ├── raw/
            ├── articles/
            ├── vectors/
            ├── clusters/
            └── reports/
"""

current_path = []
is_first_line = True

for line in tree_text.strip().split("\n"):
    # Очищаем строку от комментариев и пробелов
    line_clean = line.split("#")[0].strip()
    if not line_clean:
        continue

    # Считаем уровень вложенности
    raw_indent = len(line) - len(line.lstrip(" │├└─"))
    level = raw_indent // 4

    # Чистим имя файла/папки от символов разметки
    name = line_clean.replace("├──", "").replace("└──", "").replace("│", "").strip()
    name = name.split("(опционально)")[0].strip()
    if not name:
        continue

    # ХАК: Если это самая первая строчка и она является корневой папкой, 
    # мы ее просто пропускаем, чтобы не создавать дубликат
    if is_first_line and (name.endswith("/") or name == "semantic-radar"):
        is_first_line = False
        continue
    is_first_line = False

    # Корректируем текущий путь (с учетом пропуска корня уменьшаем level на 1)
    adjusted_level = max(0, level - 1)
    current_path = current_path[:adjusted_level]
    current_path.append(name)
    full_path = os.path.join(*current_path)

    # Проверяем, файл это или папка
    is_file = "." in name or name in ["Dockerfile", "Makefile"] or name.startswith(".")
    if name.endswith("/"):
        is_file = False
        full_path = full_path.rstrip("/")

    if is_file:
        dir_name = os.path.dirname(full_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write("")  # Создаем пустой файл
        print(f"Файл создан: {full_path}")
    else:
        os.makedirs(full_path, exist_ok=True)
        print(f"Папка создана: {full_path}")
