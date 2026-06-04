import pickle
from pathlib import Path
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class EmbeddingCache:
    """
    Pre-compute and cache embeddings for dataset questions
    
    Benefits:
    - 2-3x faster similarity calculation
    - Reduces model inference calls
    - One-time computation cost
    """
    
    def __init__(self):
        self.cache_dir = Path(settings.BASE_DIR) / 'cache' / 'embeddings'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / 'question_embeddings.pkl'
        self.embeddings = {}
        self._load_cache()
    
    def _load_cache(self):
        """Load cached embeddings"""
        if self.cache_file.exists():
            with open(self.cache_file, 'rb') as f:
                self.embeddings = pickle.load(f)
            logger.info(f"Loaded {len(self.embeddings)} cached embeddings")
    
    def save_cache(self):
        """Save embeddings to disk"""
        with open(self.cache_file, 'wb') as f:
            pickle.dump(self.embeddings, f)
        logger.info(f"Saved {len(self.embeddings)} embeddings to cache")
    
    def get_or_compute(self, question_text: str, model):
        """Get cached embedding or compute new one"""
        if question_text in self.embeddings:
            return self.embeddings[question_text]
        
        # Compute
        embedding = model.encode(question_text)
        self.embeddings[question_text] = embedding
        
        return embedding
    
    def precompute_all(self, model):
        """Pre-compute embeddings for all dataset questions"""
        from interviews.utils.dataset_loader import get_dataset_loader
        
        loader = get_dataset_loader()
        dataset = loader.load_dataset()
        
        total = 0
        
        for role, questions in dataset.items():
            for q in questions:
                question_text = q['question_text']
                if question_text not in self.embeddings:
                    self.embeddings[question_text] = model.encode(question_text)
                    total += 1
        
        self.save_cache()
        logger.info(f"Pre-computed {total} new embeddings")