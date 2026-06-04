import logging
from typing import Dict, List, Optional

from sentence_transformers import SentenceTransformer, util

logger = logging.getLogger(__name__)


class SemanticAnalyzer:

    def __init__(self):
        try:
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("SemanticAnalyzer initialized (DB mode)")
        except Exception as e:
            logger.error(f"Init failed: {e}")
            self.model = None

    def calculate_similarity(self, answer_text: str, reference_text: str) -> float:

        if not self.model or not answer_text or not reference_text:
            return 0.0

        try:
            a = self.model.encode(answer_text, convert_to_tensor=True)
            b = self.model.encode(reference_text, convert_to_tensor=True)

            score = util.cos_sim(a, b).item()
            return max(0.0, min(1.0, float(score)))

        except Exception as e:
            logger.error(f"Similarity error: {e}")
            return 0.0

    def calculate_similarity_score(
        self,
        answer_text: str,
        question_text: str,
        expected_answer: str = None,
        expected_keywords: List[str] = None
    ) -> Dict:

        if not answer_text:
            return {
                "score": 0.0,
                "percentage": 0,
                "confidence": "very_low",
                "reference_used": "none"
            }
        
        if expected_answer and expected_answer.strip():
            reference_text = expected_answer
            reference_used = "expected_answer_db"

        else:
            reference_text = question_text + " " + " ".join(expected_keywords or [])
            reference_used = "fallback_keywords"

        similarity = self.calculate_similarity(answer_text, reference_text)
        percentage = round(similarity * 100, 2)

        # confidence mapping
        if similarity >= 0.80:
            confidence = "excellent"
        elif similarity >= 0.65:
            confidence = "high"
        elif similarity >= 0.50:
            confidence = "medium"
        elif similarity >= 0.35:
            confidence = "low"
        else:
            confidence = "very_low"

        return {
            "score": similarity,
            "percentage": percentage,
            "confidence": confidence,
            "reference_used": reference_used,
            "details": {
                "answer_words": len(answer_text.split()),
                "reference_words": len(reference_text.split())
            }
        }


# singleton
_analyzer = None

def get_semantic_analyzer():
    global _analyzer
    if _analyzer is None:
        _analyzer = SemanticAnalyzer()
    return _analyzer