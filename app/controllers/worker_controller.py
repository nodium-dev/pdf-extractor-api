from fastapi import APIRouter, Depends
from typing import Dict

from app.workers.file_cleanup import file_cleanup_worker
from app.config import settings
from app.services.llm_service import LLMService

# Create router
router = APIRouter(tags=["Worker Status"])


@router.get(
    "/workers/status",
    summary="Get worker status",
    description="Get the status of background workers.",
)
async def get_worker_status() -> Dict:
    """
    Get the status of background workers.

    Returns:
        Dict: Status information about background workers
    """
    return {
        "file_cleanup_worker": {
            "running": file_cleanup_worker.scheduler.running,
            "retention_minutes": file_cleanup_worker.retention_minutes,
            "next_run": file_cleanup_worker.scheduler.get_job("cleanup_old_files").next_run_time.isoformat()
            if file_cleanup_worker.scheduler.running else None,
            "job_count": len(file_cleanup_worker.scheduler.get_jobs())
        }
    }


@router.get(
    "/llm/status",
    summary="Get LLM service status",
    description="Get the status and configuration of the LLM service.",
)
async def get_llm_status() -> Dict:
    """
    Get the status of the LLM service.

    Returns:
        Dict: Status information about the LLM service
    """
    available = await LLMService.is_available()

    return {
        "llm_service": {
            "available": available,
            "provider": settings.LLM_PROVIDER,
            "model": (
                settings.OLLAMA_MODEL
                if settings.LLM_PROVIDER.lower() == "ollama"
                else settings.OPENROUTER_MODEL
            ),
            "host": (
                settings.OLLAMA_HOST
                if settings.LLM_PROVIDER.lower() == "ollama"
                else "https://openrouter.ai/api/v1"
            ),
        }
    }