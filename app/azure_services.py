"""All calls to Azure. Uses Microsoft Entra ID (no keys in code).

- In Azure: the app uses its managed identity (set AZURE_CLIENT_ID for a
  user-assigned identity).
- On your computer: DefaultAzureCredential uses your `az login` session.
"""
from functools import lru_cache

from azure.core.exceptions import ResourceExistsError
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)
from azure.search.documents.models import VectorizedQuery
from azure.storage.blob import BlobServiceClient
from openai import OpenAI

from .config import Settings, get_settings
from .text_utils import chunk_text, safe_key

SYSTEM_PROMPT = (
    "You answer questions using ONLY the sources below. "
    "If the sources do not contain the answer, say you do not know. "
    "Cite sources as [1], [2] etc. Keep answers short and clear."
)


@lru_cache
def _credential() -> DefaultAzureCredential:
    return DefaultAzureCredential()


@lru_cache
def _settings() -> Settings:
    return get_settings()


@lru_cache
def _openai() -> OpenAI:
    s = _settings()
    token_provider = get_bearer_token_provider(
        _credential(), "https://cognitiveservices.azure.com/.default"
    )
    # Azure OpenAI "v1" API: no api-version needed; works with the standard OpenAI client.
    return OpenAI(base_url=s.openai_endpoint.rstrip("/") + "/openai/v1/", api_key=token_provider)


@lru_cache
def _search_client() -> SearchClient:
    s = _settings()
    return SearchClient(s.search_endpoint, s.search_index, _credential())


def ensure_index() -> None:
    """Create the search index if it does not exist."""
    s = _settings()
    client = SearchIndexClient(s.search_endpoint, _credential())
    if s.search_index in [name for name in client.list_index_names()]:
        return
    index = SearchIndex(
        name=s.search_index,
        fields=[
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SimpleField(name="source", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="chunk_no", type=SearchFieldDataType.Int32),
            SearchableField(name="content", type=SearchFieldDataType.String),
            SearchField(
                name="embedding",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=s.embedding_dimensions,
                vector_search_profile_name="vector-profile",
            ),
        ],
        vector_search=VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name="hnsw")],
            profiles=[VectorSearchProfile(name="vector-profile", algorithm_configuration_name="hnsw")],
        ),
    )
    try:
        client.create_index(index)
    except ResourceExistsError:
        pass


def embed(texts: list[str]) -> list[list[float]]:
    s = _settings()
    result = []
    for i in range(0, len(texts), 16):  # small batches stay under limits
        response = _openai().embeddings.create(
            model=s.openai_embedding_deployment, input=texts[i : i + 16]
        )
        result.extend(item.embedding for item in response.data)
    return result


def save_file(name: str, data: bytes) -> None:
    s = _settings()
    service = BlobServiceClient(s.storage_account_url, credential=_credential())
    service.get_blob_client(s.storage_container, name).upload_blob(data, overwrite=True)


def index_document(name: str, text: str) -> int:
    """Split, embed and store a document. Returns the number of chunks."""
    chunks = chunk_text(text)
    if not chunks:
        return 0
    vectors = embed(chunks)
    docs = [
        {
            "id": safe_key(name, str(i)),
            "source": name,
            "chunk_no": i,
            "content": chunk,
            "embedding": vector,
        }
        for i, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
    ]
    for i in range(0, len(docs), 100):
        _search_client().merge_or_upload_documents(docs[i : i + 100])
    return len(docs)


def answer_question(question: str, top: int = 5) -> dict:
    """Hybrid search (keyword + vector), then ask the chat model."""
    s = _settings()
    vector = embed([question])[0]
    results = _search_client().search(
        search_text=question,
        vector_queries=[VectorizedQuery(vector=vector, k_nearest_neighbors=top, fields="embedding")],
        select=["source", "chunk_no", "content"],
        top=top,
    )
    sources = [
        {"source": r["source"], "chunk_no": r["chunk_no"], "content": r["content"]} for r in results
    ]
    if not sources:
        return {"answer": "No documents found. Upload a document first.", "sources": []}

    context = "\n\n".join(
        f"[{i + 1}] (from {src['source']})\n{src['content']}" for i, src in enumerate(sources)
    )
    response = _openai().chat.completions.create(
        model=s.openai_chat_deployment,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Sources:\n{context}\n\nQuestion: {question}"},
        ],
    )
    return {"answer": response.choices[0].message.content, "sources": sources}
