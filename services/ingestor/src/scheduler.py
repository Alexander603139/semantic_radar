from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
from .settings import settings
from .tasks import run_parsing_task

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

# Глобальная переменная для списка сайтов (будет обновляться при инициализации)
_current_sources = settings.SOURCES

async def scheduled_job():
    """Функция, запускаемая по расписанию для пользователя admin"""
    logger.info("Запуск плановой задачи для пользователя admin")
    await run_parsing_task("admin", _current_sources, 5)

def init_scheduler(cron: str = None, sources: list = None):
    """Инициализирует планировщик с переданным расписанием и списком сайтов."""
    global _current_sources
    if cron is None:
        cron = settings.SCHEDULE_CRON
    if sources is not None:
        _current_sources = sources  # сохраняем переданный список
    
    trigger = CronTrigger.from_crontab(cron)
    scheduler.add_job(scheduled_job, trigger=trigger, id="weekly_parsing")
    scheduler.start()
    logger.info(f"Планировщик запущен с расписанием: {cron}, сайтов: {len(_current_sources)}")