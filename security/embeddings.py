from threading import Lock
import numpy as np

DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"


class SentenceTransformerEmbeddingBackend:
    def __init__(self, model_name=DEFAULT_EMBEDDING_MODEL):
        self.model_name = model_name
        self._model = None
        self._lock = Lock()

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode(self, texts):
        with self._lock:
            model = self._load_model()
            embeddings = model.encode(
                list(texts),
                normalize_embeddings=True,
                show_progress_bar=False,
                convert_to_numpy=True,
            )

        return np.asarray(embeddings, dtype=np.float32)