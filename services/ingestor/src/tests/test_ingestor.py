import asyncio
import httpx
import json

TEST_SOURCES = [
    "https://lenta.ru",
    # "https://ria.ru",
    # "https://tass.ru"
]
LIMIT = 2   # для теста берём по 2 статьи

async def test_run():
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "http://localhost:8001/run",
            json={
                "user_id": "test_user",
                "sources": TEST_SOURCES,
                "limit": LIMIT
            }
        )
        if resp.status_code != 200:
            print("Ошибка:", resp.text)
            return
        data = resp.json()
        task_id = data["task_id"]
        print(f"Задача запущена: {task_id}")

        # Ждём завершения (опрос статуса)
        while True:
            status_resp = await client.get(f"http://localhost:8001/status/{task_id}")
            if status_resp.status_code != 200:
                print("Ошибка получения статуса:", status_resp.text)
                break
            status_data = status_resp.json()
            print(f"Статус: {status_data['status']}")
            if status_data["status"] in ("completed", "failed"):
                break
            await asyncio.sleep(2)

        if status_data["status"] == "completed":
            print("Результат:", json.dumps(status_data["result"], indent=2))
        else:
            print("Ошибка:", status_data.get("error"))

if __name__ == "__main__":
    asyncio.run(test_run())