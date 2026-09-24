from dataclasses import dataclass


@dataclass(frozen=True)
class ModelChoice:
    id: str
    label: str
    # Model identifier for the RAG-service `/direct-query` API (Ollama-style tag).
    rag_model: str
    # Model identifier for the DGX/LiteLLM `/v1/chat/completions` API.
    dgx_model: str


# One project-wide model selection, used by every LLM call site (RAG-service and
# DGX/LiteLLM alike) instead of each area picking its own model independently.
# Kept as a small fixed list rather than querying the backends' model catalogs,
# since the two backends use different naming conventions and not every model
# available on one side is necessarily available (or correctly named) on the other.
MODEL_CATALOG: list[ModelChoice] = [
    ModelChoice(
        id="llama3.2-3b",
        label="Llama 3.2 3B (lokal)",
        rag_model="llama3.2:3b",
        # llama3.2:3b läuft nur lokal über den RAG-Service (Ollama) - der
        # DGX/LiteLLM-Proxy lässt dieses Team nur "Qwen3.8-27B-NVFP4" und
        # "openai/gpt-oss-120b" zu (403 team_model_access_denied sonst).
        dgx_model="openai/gpt-oss-120b",
    ),
]

DEFAULT_MODEL_ID = MODEL_CATALOG[0].id


def get_model_choice(model_id: str | None) -> ModelChoice:
    """Resolve a model id to its `ModelChoice`, fail-open to the default entry."""
    for choice in MODEL_CATALOG:
        if choice.id == model_id:
            return choice
    return MODEL_CATALOG[0]
