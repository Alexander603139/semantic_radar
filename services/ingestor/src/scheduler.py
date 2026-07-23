from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
from .settings import settings
from .tasks import run_parsing_task

logger = logging.getLogger(__name__)

SCHEDULE_CRON = settings.SCHEDULE_CRON
SOURCES = settings.SOURCES

scheduler = AsyncIOScheduler()

async def scheduled_job():
    """Функция, запускаемая по расписанию для тестового пользователя"""
    logger.info("Запуск плановой задачи для тестового пользователя")
    # Для прототипа используем фиксированный список и лимит
    await run_parsing_task("scheduled_user", SOURCES, 5)

def init_scheduler():
    """Инициализирует планировщик и добавляет задачу"""
    trigger = CronTrigger.from_crontab(SCHEDULE_CRON)
    scheduler.add_job(scheduled_job, trigger=trigger, id="weekly_parsing")
    scheduler.start()
    logger.info(f"Планировщик запущен с расписанием: {SCHEDULE_CRON}")