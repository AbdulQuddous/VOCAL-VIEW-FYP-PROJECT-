"""
SpaCy NLP Service - CLEAN PRODUCTION VERSION
=============================================

REMOVED (not saved to DB, not used anywhere):
  - _extract_entities()     — nobody calls it / no DB column
  - _extract_main_topics()  — nobody calls it / no DB column
  - _analyze_sentiment()    — nobody calls it / no DB column

KEPT (all used by analyze_content → saved to ContentAnalysis DB):
  - _analyze_keywords()          → keyword_matches, keyword_score
  - _count_filler_words()        → filler_word_count
  - _check_grammar()             → grammar_issues (used by clarity + relevance)
  - _calculate_clarity_score()   → clarity_score
  - _calculate_overall_relevance() → relevance_score
"""

import spacy
import logging
from django.conf import settings
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class SpacyNLPService:
    """
    Linguistic quality analysis for interview answers.

    Called by: process_answer_step_3_spacy_analysis() in views.py
    Saves to:  ContentAnalysis model

    Fields produced → saved to DB:
      filler_word_count, word_count, unique_word_count,
      clarity_score, relevance_score, grammar_issues,
      keyword_matches, improvement_tips
    """

    FILLER_WORDS = {
        'um', 'uh', 'like', 'you know', 'so', 'actually', 'basically',
        'literally', 'right', 'okay', 'well', 'i mean', 'kind of',
        'sort of', 'you see', 'anyway', 'honestly', 'essentially',
        'pretty much', 'i guess', 'you know what i mean',
    }

    def __init__(self):
        self.nlp = None
        self.model_name = settings.AI_MODELS['SPACY']['MODEL']
        self._keyword_service = None
        logger.info("SpaCyNLPService initialized")

    # ------------------------------------------------------------------
    # LAZY LOADERS
    # ------------------------------------------------------------------

    def _load_model(self):
        if self.nlp is None:
            logger.info(f"Loading SpaCy model: {self.model_name}")
            self.nlp = spacy.load(self.model_name)
            logger.info("SpaCy model loaded")

    def _get_keyword_service(self):
        if self._keyword_service is None:
            from interviews.ai_services.keyword_service import get_keyword_service
            self._keyword_service = get_keyword_service()
        return self._keyword_service

    # ------------------------------------------------------------------
    # MAIN ENTRY POINT
    # ------------------------------------------------------------------

    def analyze_content(
        self,
        text: str,
        expected_keywords: Optional[List[str]] = None,
        question_text: Optional[str] = None,
        job_role: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict:
        """
        Run full linguistic analysis on a transcribed answer.

        Returns a dict whose keys map directly to ContentAnalysis model fields.
        Called by process_answer_step_3_spacy_analysis() in views.py.
        """
        self._load_model()

        if not text or len(text.strip()) < 5:
            return self._empty_analysis()

        try:
            doc = self.nlp(text.lower())

            # keyword analysis — delegated to KeywordService
            keyword_result = self._analyze_keywords(
                text=text,
                expected_keywords=expected_keywords,
                question_text=question_text,
                job_role=job_role,
                session_id=session_id,
            )

            # linguistic metrics
            filler_count   = self._count_filler_words(text)
            word_count     = len([t for t in doc if not t.is_punct])
            unique_words   = len(set(
                t.text for t in doc if not t.is_punct and not t.is_stop
            ))
            grammar_issues = self._check_grammar(doc)
            clarity_score  = self._calculate_clarity_score(doc, filler_count)
            relevance_score = self._calculate_overall_relevance(
                keyword_score=keyword_result.get('score', 0.0),
                word_count=word_count,
                unique_words=unique_words,
                filler_count=filler_count,
                grammar_issues=grammar_issues,
            )

            result = {
                # saved to ContentAnalysis
                'filler_word_count': filler_count,
                'word_count':        word_count,
                'unique_words':      unique_words,   # mapped → unique_word_count in step 3
                'grammar_issues':    grammar_issues,
                'clarity_score':     clarity_score,
                'relevance_score':   relevance_score,

                # keyword fields (saved via keyword_matches column)
                'keyword_matches':  keyword_result.get('matched_keywords', []),
                'keyword_score':    keyword_result.get('score', 0.0),
                'missing_keywords': keyword_result.get('missing_keywords', []),
                'keyword_density':  keyword_result.get('keyword_density', 0.0),
            }

            logger.debug(
                f"[{session_id}] SpaCy done — "
                f"kw={keyword_result.get('score', 0):.1f}% "
                f"relevance={relevance_score:.1f}% "
                f"clarity={clarity_score:.1f}%"
            )
            return result

        except Exception as e:
            logger.error(f"analyze_content failed: {e}", exc_info=True)
            return self._empty_analysis()

    # ------------------------------------------------------------------
    # KEYWORD DELEGATION  → KeywordService
    # ------------------------------------------------------------------

    def _analyze_keywords(
        self,
        text: str,
        expected_keywords: Optional[List[str]],
        question_text: Optional[str],
        job_role: Optional[str],
        session_id: Optional[str],
    ) -> Dict:
        """Delegate to KeywordService (safe, no crash, no index errors)."""
        try:
            result = self._get_keyword_service().analyze_answer(
                answer_text=text,
                expected_keywords=expected_keywords,
                question_text=question_text,
                job_role=job_role,
                session_id=session_id,
            )
            logger.debug(
                f"[{session_id}] keywords {result['score']:.1f}% "
                f"({len(result['matched_keywords'])}/{len(expected_keywords or [])} matched)"
            )
            return result

        except Exception as e:
            logger.error(f"keyword delegation failed: {e}", exc_info=True)
            return {
                'score': 0.0,
                'matched_keywords': [],
                'missing_keywords': expected_keywords or [],
                'keyword_density':  0.0,
            }

    # ------------------------------------------------------------------
    # FILLER WORDS  → filler_word_count
    # ------------------------------------------------------------------

    def _count_filler_words(self, text: str) -> int:
        text_lower = text.lower()
        count = 0
        for filler in self.FILLER_WORDS:
            count += text_lower.count(f" {filler} ")
            count += text_lower.count(f"{filler} ")   # start of text
            count += text_lower.count(f" {filler}")   # end of text
        return count

    # ------------------------------------------------------------------
    # GRAMMAR CHECK  → grammar_issues (JSONField)
    # ------------------------------------------------------------------

    def _check_grammar(self, doc) -> List[Dict]:
        """
        Detects 3 issue types:
          missing_verb  — sentence with >4 tokens but no verb
          long_sentence — sentence longer than 40 tokens
          fragment      — sentence shorter than 3 tokens
        Returns max 5 issues.
        """
        issues = []
        for sent in doc.sents:
            tokens = list(sent)
            if len(tokens) < 2:
                continue

            if not any(t.pos_ == 'VERB' for t in tokens) and len(tokens) > 4:
                issues.append({
                    'type':     'missing_verb',
                    'sentence': sent.text[:80],
                    'severity': 'medium',
                })

            if len(tokens) > 40:
                issues.append({
                    'type':     'long_sentence',
                    'sentence': sent.text[:80] + '...',
                    'severity': 'low',
                })

            if len(tokens) < 3 and sent.text.strip():
                issues.append({
                    'type':     'fragment',
                    'sentence': sent.text,
                    'severity': 'low',
                })

        return issues[:5]

    # ------------------------------------------------------------------
    # CLARITY SCORE  → clarity_score
    # ------------------------------------------------------------------

    def _calculate_clarity_score(self, doc, filler_count: int) -> float:
        """
        Clarity score 0–100.

        +40  sentence length in ideal range (12–20 words)
        +30  vocabulary diversity
        +30  base
        −5   per grammar issue
        −2.5 per filler word (capped at −15)
        """
        sentences = list(doc.sents)
        if not sentences:
            return 50.0

        avg_len = sum(len(list(s)) for s in sentences) / len(sentences)

        if 12 <= avg_len <= 20:
            length_score = 40
        elif 8 <= avg_len <= 25:
            length_score = 30
        elif 6 <= avg_len <= 30:
            length_score = 20
        else:
            length_score = 10

        total_words  = len([t for t in doc if not t.is_punct])
        unique_words = len(set(t.text for t in doc if not t.is_punct and not t.is_stop))
        diversity    = min(30, (unique_words / total_words * 100) if total_words else 0)

        grammar_penalty = len(self._check_grammar(doc)) * 5
        filler_penalty  = min(15, filler_count * 2.5)

        score = length_score + diversity + 30 - grammar_penalty - filler_penalty
        return round(max(0.0, min(100.0, score)), 2)

    # ------------------------------------------------------------------
    # OVERALL RELEVANCE  → relevance_score
    # ------------------------------------------------------------------

    def _calculate_overall_relevance(
        self,
        keyword_score: float,
        word_count: int,
        unique_words: int,
        filler_count: int,
        grammar_issues: List,
    ) -> float:
        """
        Relevance score 0–100.

        50% keyword score
        25% content depth (word count bands)
        15% vocabulary diversity
        10% base
        penalties: filler words, grammar issues
        """
        kw_component = keyword_score * 0.5

        if 50 <= word_count <= 200:
            depth = 25
        elif 30 <= word_count <= 250:
            depth = 20
        elif 20 <= word_count < 30:
            depth = 15
        elif word_count < 20:
            depth = 10
        else:
            depth = 18

        vocab = min(15, (unique_words / word_count * 30) if word_count else 0)

        filler_penalty  = min(10, filler_count * 1.5)
        grammar_penalty = min(8,  len(grammar_issues) * 2)

        score = kw_component + depth + vocab + 10 - filler_penalty - grammar_penalty
        return round(max(0.0, min(100.0, score)), 2)

    # ------------------------------------------------------------------
    # EMPTY FALLBACK
    # ------------------------------------------------------------------

    def _empty_analysis(self) -> Dict:
        return {
            'filler_word_count': 0,
            'word_count':        0,
            'unique_words':      0,
            'grammar_issues':    [],
            'clarity_score':     0.0,
            'relevance_score':   0.0,
            'keyword_matches':   [],
            'keyword_score':     0.0,
            'missing_keywords':  [],
            'keyword_density':   0.0,
        }


# ------------------------------------------------------------------
# SINGLETON
# ------------------------------------------------------------------

_spacy_service = None


def get_spacy_service() -> SpacyNLPService:
    global _spacy_service
    if _spacy_service is None:
        _spacy_service = SpacyNLPService()
        logger.info("SpacyNLPService singleton created")
    return _spacy_service