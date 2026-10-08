"""App settings. All values come from environment variables."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    storage_account_url: str
    storage_container: str
    search_endpoint: str
    search_index: str
    openai_endpoint: str
    openai_chat_deployment: str
    openai_embedding_deployment: str
    embedding_dimensions: int


def get_settings() -> Settings:
    def need(name: str) -> str:
        value = os.environ.get(name)
        if not value:
            raise RuntimeError(f"Missing environment variable: {name}")
        return value

    return Settings(
        storage_account_url=need("AZURE_STORAGE_ACCOUNT_URL"),
        storage_container=os.environ.get("AZURE_STORAGE_CONTAINER", "documents"),
        search_endpoint=need("AZURE_SEARCH_ENDPOINT"),
        search_index=os.environ.get("AZURE_SEARCH_INDEX", "documents"),
        openai_endpoint=need("AZURE_OPENAI_ENDPOINT"),
        openai_chat_deployment=os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "chat"),
        openai_embedding_deployment=os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "embedding"),
        embedding_dimensions=int(os.environ.get("EMBEDDING_DIMENSIONS", "1536")),
    )
