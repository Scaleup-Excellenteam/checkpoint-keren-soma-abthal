from threading import Lock


DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"


class SentenceTransformerEmbeddingBackend:
    def __init__(self, model_name=DEFAULT_EMBEDDING_MODEL):
        self.model_name = model_name
        self._model = None
        self._lock = Lock()

    def encode(self, texts):
        with self._lock:
            if self._model is None:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.model_name)

            embeddings = self._model.encode(
                list(texts),
                normalize_embeddings=True,
                show_progress_bar=False,
            )

        if hasattr(embeddings, "tolist"):
            return embeddings.tolist()
        return embeddings
