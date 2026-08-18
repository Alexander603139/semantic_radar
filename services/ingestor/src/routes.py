from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import httpx
from .settings import settings

router = APIRouter()

class UpdateSettingsRequest(BaseModel):
    sources: List[str]
    schedule_cron: Optional[str] = "0 5 * * *"

@router.post("/admin/settings")
async def update_settings(data: UpdateSettingsRequest):
    """
    Обновляет настройки пользователя (список сайтов и расписание) через storage.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.STORAGE_URL}/settings/admin",
            json={"sources": data.sources, "schedule_cron": data.schedule_cron}
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail="Failed to update settings")
        
        # TODO: Перезапустить планировщик с новым cron (если нужно)
        # from .scheduler import scheduler, scheduled_job
        # scheduler.reschedule_job("weekly_parsing", trigger="cron", **parse_cron(data.schedule_cron))
        
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