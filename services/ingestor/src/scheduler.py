from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
from .settings import settings
from .tasks import run_parsing_task
import pytz
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# scheduler = AsyncIOScheduler()

scheduler = None
_current_sources = []
_current_cron = "0 5 * * *"
_current_timezone = "UTC"

# Глобальная переменная для списка сайтов (будет обновляться при инициализации)
_current_sources = settings.SOURCES

async def scheduled_job():
    """Функция, запускаемая по расписанию для пользователя admin"""
    logger.info("Запуск плановой задачи для пользователя admin")
    await run_parsing_task("admin", _current_sources, 5)

# def init_scheduler(cron: str = None, sources: list = None):
#     """Инициализирует планировщик с переданным расписанием и списком сайтов."""
#     global _current_sources
#     if cron is None:
#         cron = settings.SCHEDULE_CRON
#     if sources is not None:
#         _current_sources = sources  # сохраняем переданный список
    
#     trigger = CronTrigger.from_crontab(cron)
#     scheduler.add_job(scheduled_job, trigger=trigger, id="weekly_parsing")
#     scheduler.start()
#     logger.info(f"Планировщик запущен с расписанием: {cron}, сайтов: {len(_current_sources)}")

def init_scheduler(cron: str = None, sources: list = None, timezone: str = None):
    global scheduler, _current_sources, _current_cron, _current_timezone
    if scheduler:
        scheduler.shutdown()
    _current_sources = sources or settings.SOURCES
    _current_cron = cron or settings.SCHEDULE_CRON
    _current_timezone = timezone or settings.DEFAULT_TIMEZONE
    tz = pytz.timezone(_current_timezone)
    trigger = CronTrigger.from_crontab(_current_cron, timezone=tz)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(scheduled_job, trigger=trigger, id="weekly_parsing")
    scheduler.start()
    logger.info(f"Планировщик запущен: cron={_current_cron}, timezone={_current_timezone}")

# Функция для перезапуска с новыми параметрами
def restart_scheduler(cron: str = None, sources: list = None, timezone: str = None):
    """Останавливает текущий планировщик и запускает новый с переданными параметрами."""
    global scheduler
    if scheduler:
        scheduler.shutdown()
    init_scheduler(cron, sources, timezone)