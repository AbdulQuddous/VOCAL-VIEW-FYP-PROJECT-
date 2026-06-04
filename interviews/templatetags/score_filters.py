from django import template

register = template.Library()


@register.filter
def score_color(score):
    try:
        score = float(score)
    except (ValueError, TypeError):
        return 'secondary'

    if score >= 90:
        return 'success'
    elif score >= 75:
        return 'primary'
    elif score >= 60:
        return 'info'
    elif score >= 40:
        return 'warning'
    else:
        return 'danger'


@register.filter
def score_interpretation(score):
    try:
        score = float(score)
    except (ValueError, TypeError):
        return 'Score not available'

    if score >= 90:
        return 'Excellent - Outstanding answer with comprehensive coverage!'
    elif score >= 75:
        return 'Good - Strong performance with solid technical depth'
    elif score >= 60:
        return 'Satisfactory - Meets expectations, room for improvement'
    elif score >= 40:
        return 'Needs Improvement - Lacks depth and detail'
    else:
        return 'Poor - Requires significant improvement'


@register.filter
def score_icon(score):
    try:
        score = float(score)
    except (ValueError, TypeError):
        return 'fa-question-circle'

    if score >= 90:
        return 'fa-star'
    elif score >= 75:
        return 'fa-thumbs-up'
    elif score >= 60:
        return 'fa-check-circle'
    elif score >= 40:
        return 'fa-exclamation-triangle'
    else:
        return 'fa-times-circle'


@register.filter
def percentage(value):
    try:
        return f"{float(value):.0f}%"
    except (ValueError, TypeError):
        return "0%"


@register.filter
def weight_percentage(weight):
    try:
        return f"{float(weight) * 100:.0f}%"
    except (ValueError, TypeError):
        return "0%"


# =========================
# FIX FOR TOTAL WORDS
# =========================

@register.filter
def wordcount(text):
    """
    Count words in text

    Usage:
    {{ answer.transcribed_text|wordcount }}
    """
    if not text:
        return 0
    return len(str(text).split())


@register.filter
def join_word_counts(answers):
    """
    Sum all words from all answers

    Usage:
    {{ session.answers.all|join_word_counts }}
    """
    total = 0

    try:
        for answer in answers:
            if answer.transcribed_text:
                total += len(str(answer.transcribed_text).split())
    except:
        return 0

    return total


# =========================
# FIX FOR AVG SPEAKING PACE
# =========================

@register.filter
def get_avg_pace(answers):
    total = 0
    count = 0

    try:
        for answer in answers:
            if (
                hasattr(answer, "prosody_analysis")
                and answer.prosody_analysis
                and answer.prosody_analysis.get("speaking_pace_wpm")
            ):
                total += float(answer.prosody_analysis.get("speaking_pace_wpm", 0))
                count += 1
    except:
        return 0

    return total / count if count else 0


# =========================
# FIX FOR AVG CONFIDENCE
# =========================

@register.filter
def get_avg_confidence(answers):
    total = 0
    count = 0

    try:
        for answer in answers:
            if (
                hasattr(answer, "facial_analysis")
                and answer.facial_analysis
                and answer.facial_analysis.get("confidence_score")
            ):
                total += float(answer.facial_analysis.get("confidence_score", 0))
                count += 1
    except:
        return 0

    return total / count if count else 0


# =========================
# FIX FOR CONTENT SCORE
# =========================

@register.filter
def get_avg_content_score(answers):
    """
    Uses final_content_score instead of fixed 70
    """
    total = 0
    count = 0

    try:
        for answer in answers:
            if hasattr(answer, "final_content_score") and answer.final_content_score:
                total += float(answer.final_content_score)
                count += 1
    except:
        return 0

    return total / count if count else 0

# Add to your existing score_filters.py

@register.filter
def get_avg_clarity_score(answers):
    """Calculate average clarity score from content_analysis"""
    scores = []
    for answer in answers:
        if hasattr(answer, 'content_analysis') and answer.content_analysis:
            try:
                clarity = getattr(answer.content_analysis, 'clarity_score', 0)
                if clarity is not None:
                    scores.append(float(clarity))
            except (ValueError, TypeError, AttributeError):
                pass
    return sum(scores) / len(scores) if scores else 0


@register.filter
def get_avg_relevance_score(answers):
    """Calculate average relevance score from content_analysis"""
    scores = []
    for answer in answers:
        if hasattr(answer, 'content_analysis') and answer.content_analysis:
            try:
                relevance = getattr(answer.content_analysis, 'relevance_score', 0)
                if relevance is not None:
                    scores.append(float(relevance))
            except (ValueError, TypeError, AttributeError):
                pass
    return sum(scores) / len(scores) if scores else 0