import os
from functools import lru_cache

from langchain_openai import ChatOpenAI


@lru_cache
def get_llm(api_key: str | None = None) -> ChatOpenAI:
    """Get a configured LLM instance.

    Args:
        api_key: Optional API key override. If not provided, will use OPENAI_API_KEY env var.

    Returns:
        ChatOpenAI: Configured LLM instance

    Raises:
        ValueError: If no API key is available
    """
    api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OpenAI API key not found. Set OPENAI_API_KEY environment variable."
        )

    return ChatOpenAI(
        model_name="gpt-4",  # Using standard model name
        temperature=0.2,
        openai_api_key=api_key,
    )
