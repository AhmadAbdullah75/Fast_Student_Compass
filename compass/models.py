"""API-only inference. No local embedding fallback or model downloads."""
from langchain_core.embeddings import Embeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from google import genai
from google.genai import types
from google.genai.errors import ServerError
import math

class GeminiEmbeddings(Embeddings):
    # Use the supported SDK through LangChain's Embeddings interface: explicit
    # one-content calls prevent Embedding 2 from aggregating multiple chunks.
    def __init__(self, settings, client=None):
        self.settings = settings
        self.client = client or genai.Client(api_key=settings.require_key(), vertexai=False,
            http_options=types.HttpOptions(timeout=60000, retry_options=types.HttpRetryOptions(attempts=1)))

    def _embed(self, text):
        result = self.client.models.embed_content(model=self.settings.embedding_model, contents=text,
            config=types.EmbedContentConfig(output_dimensionality=self.settings.dimensions))
        vector = list(result.embeddings[0].values)
        if len(vector) != self.settings.dimensions or not all(math.isfinite(v) for v in vector):
            raise ValueError('Embedding API returned an invalid vector.')
        norm = math.sqrt(sum(v*v for v in vector))
        if not norm:
            raise ValueError('Embedding API returned a zero vector.')
        return [v/norm for v in vector]

    def embed_documents(self, texts):
        return [self._embed(f'title: FAST undergraduate reference | text: {text}') for text in texts]

    def embed_query(self, text):
        return self._embed(f'task: question answering | query: {text}')

def transient_chat_retry(model, transport_events=None, *, wait=True):
    """Retry the same API request on selected 5xx errors, never quota or content.

    This does not retry retrieval, validation, or the whole RAG pipeline. Each
    observed server failure is recorded without prompts, credentials or raw errors.
    """
    def retryable(exc):
        allowed=isinstance(exc,ServerError) and exc.code in (500,502,503,504)
        if allowed and transport_events is not None:
            transport_events.append({'stage':'chat_api','http_code':exc.code,'exception_type':type(exc).__name__})
        return allowed
    return model.with_retry(retry_if_exception_type=retryable,
        stop_after_attempt=3,wait_exponential_jitter=wait,
        exponential_jitter_params={'initial':2,'max':8,'exp_base':2,'jitter':1})

def chat_model(settings, transport_events=None):
    model=ChatGoogleGenerativeAI(model=settings.chat_model, api_key=settings.require_key(),
        vertexai=False, max_tokens=1800, timeout=60, max_retries=0)
    return transient_chat_retry(model,transport_events)
