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

# I-RAG-03 (ASP-OUT-009, 2026-04-18): importing the ontology manager
# module triggers @celery_app.task registration of
# `app.ontology.manager.run_ontology_sync`. No register_task() helper
# exists for this module; the import is the registration side-effect.
import app.ontology.manager  # noqa: F401

# Periodic tasks (Celery beat)
celery_app.conf.beat_schedule = {
    "monthly-cost-aggregation": {
        "task": "asp.cost_aggregator",
        "schedule": crontab(hour=1, minute=0, day_of_month=1),  # 1am on 1st of each month
    },
    # I-RAG-03 — daily ontology sync trigger at 02:00 UTC. Cron invocation
    # passes no args; run_ontology_sync's no-arg path logs a structured
    # no-op. Follow-up spec task extends the cron path to iterate active
    # tenants once the tenant/schema registry is defined.
    "ontology-sync-daily": {
        "task": "app.ontology.manager.run_ontology_sync",
        "schedule": crontab(hour=2, minute=0),
        "options": {"queue": "celery"},
    },
}
