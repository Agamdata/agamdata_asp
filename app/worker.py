"""Celery application entry point."""
from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "asp",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.timezone = "UTC"

# Register tasks
from app.services.doc_intelligence import register_task as _reg_doc
from app.services.prediction import register_task as _reg_pred
from app.cost.aggregator import register_task as _reg_agg

_reg_doc(celery_app)
_reg_pred(celery_app)
_reg_agg(celery_app)

# Periodic tasks (Celery beat)
celery_app.conf.beat_schedule = {
    "monthly-cost-aggregation": {
        "task": "asp.cost_aggregator",
        "schedule": crontab(hour=1, minute=0, day_of_month=1),  # 1am on 1st of each month
    },
}
