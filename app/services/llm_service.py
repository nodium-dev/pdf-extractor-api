import logging
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.config import settings

logger = logging.getLogger(__name__)


class LLMService:
    """Service for LLM-based text summarization."""

    _llm = None

    @classmethod
    def get_llm(cls):
        """Get or create the LLM instance based on configuration."""
        if cls._llm is not None:
            return cls._llm

        provider = settings.LLM_PROVIDER.lower()

        if provider == "ollama":
            from langchain_ollama import ChatOllama

            cls._llm = ChatOllama(
                base_url=settings.OLLAMA_HOST,
                model=settings.OLLAMA_MODEL,
            )
            logger.info(
                f"Initialized Ollama LLM with model {settings.OLLAMA_MODEL} "
                f"at {settings.OLLAMA_HOST}"
            )

        elif provider == "openrouter":
            from langchain_openai import ChatOpenAI

            if not settings.OPENROUTER_API_KEY:
                raise ValueError(
                    "OPENROUTER_API_KEY is required when using OpenRouter provider"
                )

            default_headers = {}
            if settings.OPENROUTER_SITE_URL:
                default_headers["HTTP-Referer"] = settings.OPENROUTER_SITE_URL
            if settings.OPENROUTER_SITE_NAME:
                default_headers["X-Title"] = settings.OPENROUTER_SITE_NAME

            cls._llm = ChatOpenAI(
                api_key=settings.OPENROUTER_API_KEY,
                base_url="https://openrouter.ai/api/v1",
                model=settings.OPENROUTER_MODEL,
                default_headers=default_headers if default_headers else None,
            )
            logger.info(
                f"Initialized OpenRouter LLM with model {settings.OPENROUTER_MODEL}"
            )

        else:
            raise ValueError(
                f"Unsupported LLM provider: {provider}. "
                "Supported providers: ollama, openrouter"
            )

        return cls._llm

    @classmethod
    def reset_llm(cls):
        """Reset the LLM instance (useful for testing or config changes)."""
        cls._llm = None

    @classmethod
    async def summarize_text(cls, text: str, max_length: int = 500) -> Optional[str]:
        """
        Generate a summary of the provided text using the configured LLM.

        Args:
            text: The text content to summarize
            max_length: Maximum length hint for the summary

        Returns:
            A summary string or None if summarization fails
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for summarization")
            return None

        try:
            llm = cls.get_llm()

            system_prompt = """You are a helpful assistant that creates concise summaries of documents.
Your task is to summarize the provided document content clearly and accurately.
Focus on the main points, key information, and important details.
Keep the summary informative but concise."""

            user_prompt = f"""Please summarize the following document content in approximately {max_length} words or less:

---
{text[:15000]}
---

Provide a clear, structured summary that captures the essential information."""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]

            response = llm.invoke(messages)
            summary = response.content.strip()

            logger.info(f"Successfully generated summary of {len(summary)} characters")
            return summary

        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            return None

    @classmethod
    async def is_available(cls) -> bool:
        """Check if the LLM service is available and configured properly."""
        try:
            llm = cls.get_llm()
            return llm is not None
        except Exception as e:
            logger.error(f"LLM service not available: {str(e)}")
            return False
