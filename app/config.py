import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    # Base directory
    BASE_DIR: Path = Path(__file__).resolve().parent.parent

    # Environment configurations
    DEBUG: bool = True
    API_PREFIX: str = "/api/v1"
    APP_NAME: str = "PDF Extractor API"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "info"
    FILE_RETENTION_MINUTES: int = 10

    # Database settings
    DATABASE_URL: str = "postgresql://pdfuser:pdfpassword@localhost:5432/pdfdb"

    # LLM Settings
    LLM_PROVIDER: str = "ollama"  # Options: "ollama", "openrouter"

    # Ollama settings
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"

    # OpenRouter settings
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "meta-llama/llama-3.1-8b-instruct:free"
    OPENROUTER_SITE_URL: str = ""
    OPENROUTER_SITE_NAME: str = "PDF Extractor API"

    # Upload directories - define as class variables
    UPLOAD_FOLDER: str = str(Path(__file__).resolve().parent.parent / "uploads" / "pdfs")
    IMAGE_FOLDER: str = str(Path(__file__).resolve().parent.parent / "uploads" / "images")

    def initialize(self):
        """Initialize required directories."""
        os.makedirs(self.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(self.IMAGE_FOLDER, exist_ok=True)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Create a settings instance
settings = Settings()