import torch
from sentence_transformers import SentenceTransformer

class Embedder:
    def __init__(self, model_name="all-MiniLM-L12-v2"):
        # Explicitly set the device to 'cpu' if CUDA is not available
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = SentenceTransformer(model_name, device=device)

    def embed(self, doc):
        """Embed a single document."""
        return self.model.encode(doc, convert_to_numpy=True)

    def embed_chunks(self, chunks):
        """Embed multiple chunks."""
        return [
            (chunk, self.embed(chunk))
            for chunk in chunks
        ]
