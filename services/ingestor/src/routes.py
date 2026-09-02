from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import httpx
from .settings import settings

router = APIRouter()

class UpdateSettingsRequest(BaseModel):
    sources: List[str]
    schedule_cron: Optional[str] = "0 5 * * *"
    timezone: Optional[str] = "UTC"

@router.post("/admin/settings")
async def update_settings(data: UpdateSettingsRequest):
    """
    Обновляет настройки пользователя (список сайтов, расписание и часовой пояс) через storage.
    """
    # Сохраняем в storage
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.STORAGE_URL}/settings/admin",
            json={
                "sources": data.sources,
                "schedule_cron": data.schedule_cron,
                "timezone": data.timezone
            }
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail="Failed to update settings")

    # Перезапускаем планировщик с новыми параметрами
    from .scheduler import restart_scheduler
    restart_scheduler(cron=data.schedule_cron, sources=data.sources, timezone=data.timezone)

    return {"status": "ok", "message": "Settings updated successfully"}

@router.get("/admin/settings")
async def get_settings():
    """
    Получает текущие настройки пользователя из storage.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{settings.STORAGE_URL}/settings/admin")
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail="Failed to get settings")
        return resp.json()

# def parse_cron(cron_str: str) -> dict:
#     parts = cron_str.split()
#     if len(parts) != 5:
#         raise ValueError("Invalid cron format")
#     return {
#         "minute": parts[0],
#         "hour": parts[1],
#         "day": parts[2],
#         "month": parts[3],
#         "day_of_week": parts[4]
#     }