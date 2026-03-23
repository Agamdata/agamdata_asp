from app.config import settings


def resolve_model(quality_tier: str) -> str:
    """Map quality_tier to Claude model name. Reads from settings — no DB call required."""
    mapping = {
        "standard": settings.MODEL_STANDARD,
        "enhanced": settings.MODEL_ENHANCED,
        "premium": settings.MODEL_PREMIUM,
    }
    return mapping.get(quality_tier, settings.MODEL_STANDARD)
