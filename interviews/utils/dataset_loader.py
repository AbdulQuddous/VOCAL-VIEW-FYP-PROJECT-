import json
from pathlib import Path
from typing import List, Dict, Optional
from django.conf import settings
from django.core.cache import cache
import random
import logging

logger = logging.getLogger(__name__)


class DatasetLoader:
    """
    FIXED Dataset Loader (MATCHES YOUR DATASET EXACTLY)
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.dataset_dir = Path(settings.DATASET_DIR)
        self.cache_timeout = 3600

    # =====================================================
    # IMPORTANT FIX: correct normalization
    # =====================================================
    def _normalize_role(self, role_name: str) -> str:
        """
        Make role match dataset EXACTLY
        """
        if not role_name:
            return None

        role_name = role_name.lower().strip()

        # ONLY normalize spaces (DO NOT convert to underscore)
        role_name = role_name.replace("_", " ")
        role_name = " ".join(role_name.split())

        return role_name

    # =====================================================
    def load_dataset(self, force_reload: bool = False) -> Dict:

        if not force_reload:
            cached = cache.get('question_dataset')
            if cached:
                logger.debug("Dataset loaded from cache")
                return cached

        logger.info("Loading dataset from files")
        dataset = {}

        for json_file in self.dataset_dir.glob('*.json'):
            if json_file.stem == 'taxonomy':
                continue

            role_name = json_file.stem.replace("_", " ")
            role_name = " ".join(role_name.lower().split())

            with open(json_file, 'r', encoding='utf-8') as f:
                questions = json.load(f)

            dataset[role_name] = questions

        cache.set('question_dataset', dataset, self.cache_timeout)

        logger.info(
            f"Loaded {len(dataset)} roles, "
            f"{sum(len(v) for v in dataset.values())} total questions"
        )

        return dataset

    # =====================================================
    def get_questions(
        self,
        role_name: str,
        difficulty: Optional[str] = None,
        count: int = 5
    ) -> List[Dict]:

        dataset = self.load_dataset()

        role_key = self._normalize_role(role_name)

        if role_key not in dataset:
            logger.warning(f"Role '{role_name}' not found in dataset")
            return []

        questions = dataset[role_key]

        if difficulty:
            questions = [
                q for q in questions
                if q.get('difficulty', '').lower() == difficulty.lower()
            ]

        return random.sample(questions, min(count, len(questions)))

    # =====================================================
    def get_available_roles(self) -> List[str]:
        return list(self.load_dataset().keys())

    # =====================================================
    def clear_cache(self):
        cache.delete('question_dataset')
        logger.info("Dataset cache cleared")


# Singleton
_loader = None

def get_dataset_loader():
    global _loader
    if _loader is None:
        _loader = DatasetLoader()
    return _loader