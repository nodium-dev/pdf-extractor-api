from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import time
import traceback
import logging

from app.config import settings
from app.controllers.pdf_controller import router as pdf_router
from app.controllers.worker_controller import router as worker_router
from app.database.connection import engine, Base
from app.workers.file_cleanup import file_cleanup_worker

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize the database models
Base.metadata.create_all(bind=engine)

# Initialize the application directories
settings.initialize()

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    version="1.0.0",
    description="API for extracting text, tables, and images from PDF files."
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Application startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Startup event handler."""
    logger.info("Starting application")

    # Print all configuration settings for debugging
    logger.info("Configuration settings:")
    logger.info(f"  DEBUG: {settings.DEBUG}")
    logger.info(f"  API_PREFIX: {settings.API_PREFIX}")
    logger.info(f"  APP_NAME: {settings.APP_NAME}")
    logger.info(f"  HOST: {settings.HOST}")
    logger.info(f"  PORT: {settings.PORT}")
    logger.info(f"  LOG_LEVEL: {settings.LOG_LEVEL}")
    logger.info(f"  UPLOAD_FOLDER: {settings.UPLOAD_FOLDER}")
    logger.info(f"  IMAGE_FOLDER: {settings.IMAGE_FOLDER}")

    # Try to access FILE_RETENTION_MINUTES
    try:
        retention = settings.FILE_RETENTION_MINUTES
        logger.info(f"  FILE_RETENTION_MINUTES: {retention}")
    except Exception as e:
        logger.error(f"  Error accessing FILE_RETENTION_MINUTES: {str(e)}")

    # Log LLM configuration
    logger.info("LLM Configuration:")
    logger.info(f"  LLM_PROVIDER: {settings.LLM_PROVIDER}")
    if settings.LLM_PROVIDER.lower() == "ollama":
        logger.info(f"  OLLAMA_HOST: {settings.OLLAMA_HOST}")
        logger.info(f"  OLLAMA_MODEL: {settings.OLLAMA_MODEL}")
    else:
        logger.info(f"  OPENROUTER_MODEL: {settings.OPENROUTER_MODEL}")
        logger.info(f"  OPENROUTER_API_KEY: {'***' if settings.OPENROUTER_API_KEY else 'Not set'}")

    try:
        # Start the file cleanup worker
        file_cleanup_worker.start()
        logger.info(
            f"File cleanup worker started with retention period: {file_cleanup_worker.retention_minutes} minutes")
    except Exception as e:
        logger.error(f"Error starting file cleanup worker: {str(e)}")
        logger.warning("Application will continue without file cleanup")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler."""
    logger.info("Shutting down application")
    try:
        # Stop the file cleanup worker
        file_cleanup_worker.stop()
        logger.info("File cleanup worker stopped")
    except Exception as e:
        logger.error(f"Error stopping file cleanup worker: {str(e)}")


# Request logging middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response
    except Exception as e:
        print(f"Error processing request: {str(e)}")
        print(traceback.format_exc())
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"}
        )


# Include routers
app.include_router(pdf_router, prefix=f"{settings.API_PREFIX}")
app.include_router(worker_router, prefix=f"{settings.API_PREFIX}")


# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# Root endpoint
@app.get("/")
async def root():
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "documentation": "/docs"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL
    )