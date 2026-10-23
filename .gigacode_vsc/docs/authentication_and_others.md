# Аутентификация — текущее состояние

## Короткий ответ: защиты нет нигде

## Что в коде

| Компонент | Статус |
|---|---|
| `ingestor/src/models.py:16` | `user_id: str = "test_user"  # временно, позже из JWT` |
| `user_manager/src/*.py` | Все файлы пустые (0 строк) — `main.py`, `auth.py`, `routes.py`, `config.py` |
| `docker-compose.yml` | Сервис `user_manager` отсутствует |
| Любой сервис (ingestor, analyzer, reporter, embedder, storage, traffic_stats) | Нет middleware, нет `Depends()`, нет проверок |
| Nginx-конфиги в проекте | Отсутствуют |

## Где упоминается JWT

Во всех README — как задача в backlog:

```
- Добавить авторизацию через JWT (проверка токена через `user_manager`).
```

Это: `ingestor`, `embedder`, `analyzer`, `reporter`, `storage`, `traffic_stats` — 6 сервисов, все с одинаковой записью в backlog.

## Что есть на самом деле

- `user_id` передаётся как обычный параметр в `RunRequest` (дефолт `"test_user"`)
- `storage` использует `Depends(get_db)` — но это зависимость от БД, а не от авторизации
- `traffic_stats` использует `Bearer`-токен только для внешнего API Open Pagerank (`opr_client.py`), не для своей защиты
- Ни один эндпоинт ни одного сервиса не требует авторизации

## На стороне nginx

Конфиги nginx в репозитории отсутствуют. Если на сервере есть nginx-конфиг — он находится вне репозитория (обычно `/etc/nginx/`), и я его не вижу.

## Итог

| Вопрос | Ответ |
|---|---|
| Админка защищена? Аутентификация? | Сейчас её нет.
В models.py (ingestor) поле user_id: str = "test_user" — просто заглушка.
В app.js все запросы жёстко передают user_id: 'admin'.
В routes.py эндпоинт /admin/settings не защищён — любой, кто откроет index.html, может менять настройки.
JWT и middleware отсутствуют. |
| JWT-механизм работает? | Нет — `user_manager` пустой, не в docker-compose |
| Nginx-защита в репо? | Nginx (системный, версия 1.18.0 Ubuntu, не в Docker).
Это видно из конфига lithef.twc1.net, который сохранен на сервере: блоки location /ingestor/, /storage/, /analyzer/ и т.д. с proxy_pass на localhost:800X. Traefik и другие прокси не используются. |
| Когда планируется? | В backlog всех сервисов — «Добавить JWT через `user_manager`» |
