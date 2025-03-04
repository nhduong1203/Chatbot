import os
import redis
import numpy as np
from redis.exceptions import ResponseError
import logging
from redis.commands.search.query import Query

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

class RedisManager:
    def __init__(self, redis_host=None, redis_port=None, vector_dimension=384):
        """
        Initialize the RedisIndexManager class.

        Args:
            redis_host (str): Hostname for Redis. Defaults to "localhost".
            redis_port (int): Port for Redis. Defaults to 6379.
            vector_dimension (int): Dimension of vector embeddings. Defaults to 384.
        """
        self.redis_host = redis_host or os.getenv("REDIS_HOST", "localhost")
        self.redis_port = redis_port or int(os.getenv("REDIS_PORT", 6379))
        self.redis_client = redis.Redis(host=self.redis_host, port=self.redis_port, decode_responses=False)
        self.vector_dimension = vector_dimension
        self.embedder = Embedder()
        self.logger = logging.getLogger(__name__)

    def check_index_exists(self, index_name):
        """
        Check if an index exists in Redis.

        Args:
            index_name (str): Name of the index to check.

        Returns:
            bool: True if the index exists, False otherwise.
        """
        try:
            self.redis_client.execute_command("FT.INFO", index_name)
            return True
        except ResponseError:
            return False
        
    def retrieve_contexts(self, query, user_id="user123", chat_id="chat456", top_k=3):
        """
        Retrieve relevant contexts from the Redis index based on a query.

        Args:
            query (str): The query to search for.
            embedder (object): An object with an `embed` method to generate embeddings.
            user_id (str): User ID for identifying the index. Defaults to "user123".
            chat_id (str): Chat ID for identifying the index. Defaults to "chat456".
            top_k (int): Number of top results to retrieve. Defaults to 3.

        Returns:
            list: A list of relevant documents.
        """
        index_name = f"reference:{user_id}:{chat_id}"

        if not self.check_index_exists(index_name):
            self.logger.info(f"Index {index_name} does not exist.")
            return None

        try:
            encoded_query = self.embedder.embed(query)
            search_query = (
                Query(f'(*)=>[KNN {top_k} @vector $query_vector AS vector_score]')
                .sort_by('vector_score')
                .return_fields('vector_score', 'text')
                .dialect(2)
            )
            results = self.redis_client.ft(index_name).search(
                search_query,
                {'query_vector': np.array(encoded_query, dtype=np.float32).tobytes()}
            )
            return results.docs if results.docs else []
        except Exception as e:
            self.logger.error(f"Error while retrieving data from {index_name}: {e}")
            return []
