import requests
import json

url = "http://localhost:8002/embed"
payload = {
    "user_id": "test",
    "articles": [
        {
            "id": "1",
            "title": "Тест",
            "text": "Это тестовый текст для векторизации",
            "source": "test",
            "published_at": "2026-07-22T00:00:00"
        }
    ]
}

response = requests.post(url, json=payload)
print(response.status_code)
print(response.json())