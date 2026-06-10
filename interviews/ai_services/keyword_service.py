import spacy
import re
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class KeywordMatcher:
    def __init__(self, nlp):
        self.nlp = nlp

    def _normalize(self, text: str) -> str:
        text = text.lower().strip()

        # normalize separators
        text = re.sub(r"[-_/]", " ", text)

        # remove punctuation
        text = re.sub(r"[^\w\s]", " ", text)

        # collapse spaces
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    def match(self, text: str, keywords: List[str]) -> Dict:
        if not text:
            return {"matched": [], "missing": keywords or []}

        text_norm = self._normalize(text)
        text_tokens = set(text_norm.split())

        matched = []
        missing = []

        for kw in keywords:
            if not kw:
                continue

            kw_norm = self._normalize(kw)

            # 1. exact phrase match
            if kw_norm in text_norm:
                matched.append(kw)
                continue

            # 2. token match
            kw_tokens = kw_norm.split()
            if any(token in text_tokens for token in kw_tokens):
                matched.append(kw)
                continue

            missing.append(kw)

        return {
            "matched": matched,
            "missing": missing
        }

class KeywordExtractor:
    def __init__(self, nlp):
        self.nlp = nlp

    def extract(self, text: str, max_keywords=7):
        doc = self.nlp(text.lower())

        keywords = []
        for token in doc:
            if token.pos_ in ["NOUN", "PROPN"] and len(token.text) > 2:
                keywords.append(token.lemma_.lower())

        return list(set(keywords))[:max_keywords]


class KeywordScorer:
    def score(self, matched: List[str], total: int) -> float:
        if total == 0:
            return 0.0

        score = (len(matched) / total) * 100

        # bonus full match
        if len(matched) == total:
            score += 5

        return round(min(score, 100), 2)



class KeywordService:
    """
    FINAL CLEAN PIPELINE
    """

    def __init__(self, nlp_model="en_core_web_sm"):
        self.nlp = spacy.load(nlp_model)

        self.matcher = KeywordMatcher(self.nlp)
        self.extractor = KeywordExtractor(self.nlp)
        self.scorer = KeywordScorer()

        logger.info("KeywordService initialized (FINAL CLEAN VERSION)")

    def analyze_answer(
        self,
        answer_text: str,
        expected_keywords: Optional[List[str]] = None,
        question_text: Optional[str] = None,
        job_role: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Dict:

        try:
            if not answer_text:
                return self._empty(expected_keywords)

            # STEP 1: get keywords
            keywords = expected_keywords or []

            if not keywords and question_text:
                keywords = self.extractor.extract(question_text)

            # STEP 2: match
            match_result = self.matcher.match(answer_text, keywords)

            matched = match_result["matched"]
            missing = match_result["missing"]

            # STEP 3: score
            score = self.scorer.score(matched, len(keywords))

            return {
                "score": score,
                "matched_keywords": matched,
                "missing_keywords": missing,
                "keyword_density": len(matched) / max(len(answer_text.split()), 1),
                "session_id": session_id,
                "extraction_used": not bool(expected_keywords)
            }

        except Exception as e:
            logger.error(f"KeywordService error: {e}", exc_info=True)
            return self._empty(expected_keywords)

    def _empty(self, expected_keywords):
        return {
            "score": 0.0,
            "matched_keywords": [],
            "missing_keywords": expected_keywords or [],
            "keyword_density": 0.0,
            "session_id": None,
            "extraction_used": False
        }


_service = None

def get_keyword_service():
    global _service
    if _service is None:
        _service = KeywordService()
    return _service