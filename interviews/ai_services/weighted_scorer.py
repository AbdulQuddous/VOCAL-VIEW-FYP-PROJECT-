import logging
import re
from typing import Dict

logger = logging.getLogger(__name__)


class WeightedScorer:
    # FINAL FIXED WEIGHTS
    SEMANTIC_WEIGHT = 0.65
    KEYWORD_WEIGHT = 0.25
    COMPLETENESS_WEIGHT = 0.10

    def __init__(self):
        """Initialize scorer"""
        logger.info("Weighted scorer initialized (FINAL CLEAN VERSION)")

    def _calculate_completeness_score(
        self,
        answer_text: str,
        question_text: str = ""
    ) -> float:

        try:
            if not answer_text or not answer_text.strip():
                return 0.0

            answer_text = answer_text.strip()

            word_count = len(answer_text.split())

            if word_count < 10:
                length_score = 30

            elif 10 <= word_count < 25:
                length_score = 50

            elif 25 <= word_count < 60:
                length_score = 75

            elif 60 <= word_count <= 150:
                length_score = 95

            else:
                # Prevent over-rewarding extremely long answers
                length_score = 90

            # =========================
            # SENTENCE STRUCTURE
            # =========================
            sentences = [
                s.strip()
                for s in re.split(r'[.!?]+', answer_text)
                if s.strip()
            ]

            sentence_count = len(sentences)

            if sentence_count <= 1:
                sentence_score = 40

            elif sentence_count == 2:
                sentence_score = 65

            elif 3 <= sentence_count <= 6:
                sentence_score = 90

            else:
                sentence_score = 95


            has_numbers = bool(re.search(r'\d+', answer_text))
            has_technical_terms = bool(
                re.search(r'\b(API|SQL|Python|Django|AI|ML|LLM|REST|JWT|TensorFlow|Transformer)\b',
                          answer_text,
                          re.IGNORECASE)
            )

            has_examples = any(
                phrase in answer_text.lower()
                for phrase in [
                    "for example",
                    "such as",
                    "for instance",
                    "like"
                ]
            )

            specificity_score = 50

            if has_numbers:
                specificity_score += 15

            if has_technical_terms:
                specificity_score += 20

            if has_examples:
                specificity_score += 15

            specificity_score = min(100, specificity_score)

            completeness_score = (
                (length_score * 0.40) +
                (sentence_score * 0.30) +
                (specificity_score * 0.30)
            )

            completeness_score = max(0, min(100, completeness_score))

            logger.info(
                f"Completeness score calculated: "
                f"{completeness_score:.2f} "
                f"(words={word_count}, sentences={sentence_count})"
            )

            return round(completeness_score, 2)

        except Exception as e:
            logger.error(f"Completeness score failed: {e}", exc_info=True)
            return 50.0

    def calculate_weighted_score(
        self,
        semantic_score: float,
        keyword_score: float,
        answer_text: str,
        question_text: str = "",
        question_type: str = "",
        job_role: str = ""
    ) -> Dict:

        try:
            # =========================
            # SAFETY NORMALIZATION
            # =========================
            semantic_score = max(0, min(100, float(semantic_score)))
            keyword_score = max(0, min(100, float(keyword_score)))

            # =========================
            # COMPLETENESS SCORE
            # =========================
            completeness_score = self._calculate_completeness_score(
                answer_text,
                question_text
            )

            # =========================
            # FINAL SCORE
            # =========================
            semantic_contribution = (
                semantic_score * self.SEMANTIC_WEIGHT
            )

            keyword_contribution = (
                keyword_score * self.KEYWORD_WEIGHT
            )

            completeness_contribution = (
                completeness_score * self.COMPLETENESS_WEIGHT
            )

            final_score = (
                semantic_contribution +
                keyword_contribution +
                completeness_contribution
            )

            final_score = max(0, min(100, final_score))

            logger.info(
                f"Weighted scoring complete | "
                f"Semantic={semantic_score:.1f} "
                f"Keyword={keyword_score:.1f} "
                f"Completeness={completeness_score:.1f} "
                f"Final={final_score:.1f}"
            )

            return {
                'final_score': round(final_score, 2),

                'components': {

                    'semantic_similarity': {
                        'score': round(semantic_score, 2),
                        'weight': self.SEMANTIC_WEIGHT,
                        'contribution': round(
                            semantic_contribution,
                            2
                        )
                    },

                    'keyword_relevance': {
                        'score': round(keyword_score, 2),
                        'weight': self.KEYWORD_WEIGHT,
                        'contribution': round(
                            keyword_contribution,
                            2
                        )
                    },

                    'completeness': {
                        'score': round(completeness_score, 2),
                        'weight': self.COMPLETENESS_WEIGHT,
                        'contribution': round(
                            completeness_contribution,
                            2
                        )
                    }
                },

                'weights_used': {
                    'semantic_similarity': self.SEMANTIC_WEIGHT,
                    'keyword_relevance': self.KEYWORD_WEIGHT,
                    'completeness': self.COMPLETENESS_WEIGHT
                }
            }

        except Exception as e:
            logger.error(f"Weighted score calculation failed: {e}", exc_info=True)

            return {
                'final_score': 0.0,
                'components': {},
                'weights_used': {}
            }

    def get_score_interpretation(self, score: float) -> Dict:

        if score >= 90:
            level = 'Excellent'
            description = 'Outstanding answer with excellent technical depth'
            color = 'success'

        elif score >= 75:
            level = 'Good'
            description = 'Strong answer with solid understanding'
            color = 'primary'

        elif score >= 60:
            level = 'Satisfactory'
            description = 'Good answer but can be improved'
            color = 'info'

        elif score >= 40:
            level = 'Needs Improvement'
            description = 'Partial understanding detected'
            color = 'warning'

        else:
            level = 'Poor'
            description = 'Answer lacks technical clarity'
            color = 'danger'

        return {
            'level': level,
            'description': description,
            'color': color,
            'percentage': int(score)
        }

_weighted_scorer = None


def get_weighted_scorer() -> WeightedScorer:
    """
    Singleton scorer instance
    """

    global _weighted_scorer

    if _weighted_scorer is None:
        _weighted_scorer = WeightedScorer()

    return _weighted_scorer