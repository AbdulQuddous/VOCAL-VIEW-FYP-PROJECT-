from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.http import JsonResponse, FileResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.core.files.base import ContentFile
import time
from pathlib import Path
import json
import logging
logger = logging.getLogger(__name__)
import numpy as np
import uuid
import base64
from django.core.mail import send_mail
from django.conf import settings
from .models import PasswordResetToken,User
from .models import (
    InterviewSession, JobRole, Question, Answer,
    ContentAnalysis, FacialAnalysis, ProsodyAnalysis,
    EmotionTimeline, FeedbackReport, UserProfile
)
from .forms import UserRegistrationForm, InterviewConfigForm

# Import AI services
from .ai_services.whisper_stt import get_whisper_service
from .ai_services.spacy_nlp_HYBRID import get_spacy_service
from .ai_services.mediapipe_facial import get_mediapipe_service
from .ai_services.librosa_prosody import get_librosa_service
from .ai_services.question_generator import get_question_generator
from interviews.ai_services.semantic_analyzer import get_semantic_analyzer
from interviews.ai_services.weighted_scorer import get_weighted_scorer
from interviews.ai_services.question_generator import get_question_generator
from interviews.utils.dataset_loader import get_dataset_loader

def index(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'interviews/index.html')


def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Create user profile
            UserProfile.objects.create(
                user=user,
                full_name=form.cleaned_data.get('full_name', '')
            )
            login(request, user)
            messages.success(request, 'Registration successful!')
            return redirect('dashboard')
    else:
        form = UserRegistrationForm()
    
    return render(request, 'auth/register.html', {'form': form})


def user_login(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid credentials')
    
    return render(request, 'auth/login.html')


@login_required
def user_logout(request):
    logout(request)
    return redirect('index')


@login_required
def dashboard(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    recent_sessions = InterviewSession.objects.filter(
        user=request.user
    ).order_by('-created_at')[:5]
    
    context = {
        'profile': profile,
        'recent_sessions': recent_sessions,
    }
    return render(request, 'interviews/dashboard.html', context)

@login_required
def interview_config(request):

    job_roles = JobRole.objects.all()

    if request.method == 'GET':
        return render(request, 'interviews/config.html', {
            'job_roles': job_roles
        })

    try:
        role_id = request.POST.get('role') or request.POST.get('job_role')
        difficulty = request.POST.get('difficulty', 'medium')
        question_count = int(request.POST.get('question_count', 5))

        if not role_id:
            messages.error(request, "Please select a job role")
            return render(request, 'interviews/config.html', {
                'job_roles': job_roles
            })

        job_role = JobRole.objects.filter(role_id=role_id).first()

        if not job_role:
            logger.error(f"Invalid job role selected: {role_id}")

            messages.error(request, f"Invalid job role selected: {role_id}")
            return render(request, 'interviews/config.html', {
                'job_roles': job_roles
            })

        session = InterviewSession.objects.create(
            user=request.user,
            job_role=job_role,
            status='pending'
        )

        # question generation start
        generator = get_question_generator()

        questions_data = generator.generate_questions(
            role_name=job_role.role_name,   # IMPORTANT FIX
            difficulty=difficulty,
            count=question_count
        )

        if not questions_data:
            session.delete()
            return JsonResponse({
                'error': f'No questions available for {job_role.role_name}'
            }, status=404)

        # question saved
        for q_data in questions_data:
            Question.objects.create(
                session=session,
                question_text=q_data['question_text'],
                expected_keywords=q_data.get('keywords', []),
                expected_answer=q_data.get('expected_answer', ''),
                difficulty=q_data.get('difficulty', difficulty)
            )

        messages.success(
            request,
            f'Interview created with {len(questions_data)} questions!'
        )

        return redirect('interview_conduct', session_id=session.session_id)

    except Exception as e:
        logger.error(f"Interview config error: {str(e)}")

        if 'session' in locals():
            session.delete()

        messages.error(request, f"Error: {str(e)}")

        return render(request, 'interviews/config.html', {
            'job_roles': job_roles
        })
    
@login_required
def interview_conduct(request, session_id):
    session = get_object_or_404(InterviewSession, session_id=session_id, user=request.user)
    
    if session.status == 'pending':
        session.start_interview()
    
    questions = session.questions.all()
    
    if not questions.exists():
        messages.error(request, 'No questions generated for this interview. Please try again.')
        session.delete()
        return redirect('interview_config')
    
    # Format questions for JavaScript
    questions_data = []
    for q in questions:
        questions_data.append({
            'question_id': str(q.question_id),
            'question_text': q.question_text,
            'question_type': q.question_type,
            'difficulty': q.difficulty
        })
    
    context = {
        'session': session,
        'max_duration': session.max_duration_minutes,
        'questions_json': json.dumps(questions_data),
        'questions_count': len(questions_data)
    }
    
    return render(request, 'interviews/conduct.html', context)


@login_required
@csrf_exempt
def save_answer(request, session_id):
    """
    API endpoint to save answer with audio/video and ENHANCED AI scoring
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    
    try:
        session = get_object_or_404(InterviewSession, session_id=session_id, user=request.user)
        
        question_id = request.POST.get('question_id')
        question = get_object_or_404(Question, question_id=question_id, session=session)
        
        # Get uploaded files
        video_file = request.FILES.get('video')
        audio_file = request.FILES.get('audio')
        
        if not audio_file:
            return JsonResponse({'error': 'Audio file required'}, status=400)
        
        logger.info(f"Creating answer for question {question_id}")
        
        # Create answer record (using your existing model fields)
        answer = Answer.objects.create(
            question=question,
            session=session,
            transcribed_text='',  # Will be filled by STT
            audio_file=audio_file,
            video_file=video_file,
            duration=0,
            is_processed=False
        )
        
        logger.info(f"Answer {answer.answer_id} created, waiting for file write...")
        
        # Wait for file to be fully written
        time.sleep(0.5)
        
        # Verify audio file exists
        audio_path = Path(answer.audio_file.path)
        if not audio_path.exists():
            logger.error(f"Audio file not found: {audio_path}")
            return JsonResponse({'error': 'Audio file not saved properly'}, status=500)
        
        # Check file size
        file_size = audio_path.stat().st_size
        if file_size == 0:
            logger.error("Audio file is empty")
            return JsonResponse({'error': 'Audio file is empty'}, status=400)
        
        logger.info(f"Audio file verified: {file_size} bytes")
        
        # === ENHANCED AI PROCESSING ===
        try:
            logger.info(f"Starting enhanced AI processing for answer {answer.answer_id}")
            process_answer_with_enhanced_scoring(answer, question)
            
            logger.info(f"Answer {answer.answer_id} processed successfully")
            logger.info(f"Final Score: {answer.final_content_score}%")
            
            return JsonResponse({
                'success': True,
                'answer_id': answer.answer_id,
                'message': 'Answer saved and processed successfully',
                'scores': {
                    'final': float(answer.final_content_score),
                    'semantic': float(answer.semantic_similarity_score),
                    'keywords': float(answer.keyword_relevance_score),
                    'completeness': float(answer.completeness_score)
                }
            })
            
        except Exception as e:
            logger.error(f"AI processing failed for answer {answer.answer_id}: {str(e)}")
            logger.error(f"Traceback:", exc_info=True)
            
            # Save error info but don't fail completely
            answer.transcribed_text = f"[Processing Error: {str(e)}]"
            answer.is_processed = False
            answer.save()
            
            return JsonResponse({
                'success': True,
                'answer_id': answer.answer_id,
                'message': 'Answer saved but AI processing failed',
                'error': str(e)
            })
        
    except Exception as e:
        logger.error(f"Error in save_answer: {str(e)}")
        logger.error(f"Traceback:", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


"""
process_answer — UPDATED to use SpaCy service properly
=======================================================

PIPELINE ORDER:
  Step 1  Whisper         → transcribed_text
  Step 2  KeywordService  → keyword_relevance_score, detected_keywords
  Step 3  SpaCyService    → content_analysis (filler, clarity, grammar, relevance)
  Step 4  SemanticAnalyzer→ semantic_similarity_score
  Step 5  WeightedScorer  → final_content_score
  Step 6  MediaPipe       → FacialAnalysis (if video)
  Step 7  Librosa         → ProsodyAnalysis (if audio)
"""

import logging
import numpy as np
from django.conf import settings

logger = logging.getLogger(__name__)


# ======================================================================
# STEP 2 — KEYWORD ANALYSIS  (KeywordService)
# ======================================================================

def process_answer_step_2_keyword_analysis(answer, question):
    """
    Keyword matching via clean KeywordService.
    Stores: answer.keyword_relevance_score, answer.detected_keywords
    """
    try:
        logger.info("Step 2: Keyword analysis...")

        from interviews.ai_services.keyword_service import get_keyword_service

        result = get_keyword_service().analyze_answer(
            answer_text=answer.transcribed_text,
            expected_keywords=question.expected_keywords,
            question_text=question.question_text,
            job_role=(
                answer.session.job_role.role_name
                if answer.session and answer.session.job_role
                else None
            ),
        )

        answer.keyword_relevance_score = result.get('score', 0)
        answer.detected_keywords       = result.get('matched_keywords', [])

        if hasattr(answer, 'keyword_analysis_details'):
            answer.keyword_analysis_details = {
                'missing_keywords': result.get('missing_keywords', []),
                'keyword_density':  result.get('keyword_density', 0),
                'extraction_used':  result.get('extraction_used', False),
            }

        logger.info(
            f"Keyword score: {answer.keyword_relevance_score:.1f}% | "
            f"matched {len(result.get('matched_keywords', []))} / "
            f"{len(question.expected_keywords or [])}"
        )

    except Exception as e:
        logger.error(f"Step 2 failed: {e}", exc_info=True)
        answer.keyword_relevance_score = 0
        answer.detected_keywords       = []


# ======================================================================
# STEP 3 — CONTENT ANALYSIS  (SpaCyService)  ← NEW STEP
# ======================================================================

"""
FIXED: process_answer_step_3_spacy_analysis
============================================

ROOT CAUSE OF ERROR:
  Code tried to save these fields that DO NOT EXIST in ContentAnalysis model:
    - key_entities        ✗
    - keyword_score       ✗
    - main_topics         ✗
    - missing_keywords    ✗
    - sentence_count      ✗
    - sentiment           ✗
    - unique_words        ✗  (model uses 'unique_word_count')

ACTUAL ContentAnalysis model fields:
    - relevance_score       ✓  DecimalField
    - clarity_score         ✓  DecimalField
    - filler_word_count     ✓  IntegerField
    - keyword_matches       ✓  JSONField  (list of matched keywords)
    - grammar_issues        ✓  JSONField  (list of grammar issues)
    - improvement_tips      ✓  TextField
    - word_count            ✓  IntegerField
    - unique_word_count     ✓  IntegerField  ← note: NOT 'unique_words'

FIX: Map SpaCy output keys → correct model field names.
     Drop fields that don't exist in the model.
"""

import logging
logger = logging.getLogger(__name__)


# ======================================================================
# STEP 3  (FIXED)
# ======================================================================

def process_answer_step_3_spacy_analysis(answer, question):
    """
    Run SpaCy linguistic analysis and save to ContentAnalysis model.

    Only saves fields that actually exist in ContentAnalysis.
    Extra SpaCy output (entities, topics, sentiment) is logged but not persisted
    — the model doesn't have columns for them.
    """
    try:
        logger.info("Step 3: SpaCy content analysis...")

        from interviews.ai_services.spacy_nlp_HYBRID import get_spacy_service
        from interviews.models import ContentAnalysis

        spacy_service = get_spacy_service()

        # ── run SpaCy analysis ──────────────────────────────────────────
        analysis = spacy_service.analyze_content(
            text=answer.transcribed_text,
            expected_keywords=question.expected_keywords,
            question_text=question.question_text,
            job_role=(
                answer.session.job_role.role_name
                if answer.session and answer.session.job_role
                else None
            ),
            session_id=str(answer.session.session_id),
        )

        # ── build improvement tips text ─────────────────────────────────
        # ContentAnalysis.improvement_tips is a TextField (plain string).
        # We generate tips here from the analysis dict.
        tips_list = _build_improvement_tips(analysis)
        improvement_tips_text = "\n".join(f"• {t}" for t in tips_list)

        # ── map SpaCy output → ACTUAL model fields ──────────────────────
        # Only keys that exist as columns in ContentAnalysis are included.
        model_defaults = {
            # ✓ exists in model
            'relevance_score':   analysis.get('relevance_score',   0.0),
            'clarity_score':     analysis.get('clarity_score',     0.0),
            'filler_word_count': analysis.get('filler_word_count', 0),
            'keyword_matches':   analysis.get('keyword_matches',   []),   # JSONField
            'grammar_issues':    analysis.get('grammar_issues',    []),   # JSONField
            'improvement_tips':  improvement_tips_text,                   # TextField
            'word_count':        analysis.get('word_count',        0),

            # ✓ model field is 'unique_word_count', SpaCy returns 'unique_words'
            'unique_word_count': analysis.get('unique_words',      0),
        }

        # ── persist ─────────────────────────────────────────────────────
        ContentAnalysis.objects.update_or_create(
            answer=answer,
            defaults=model_defaults,
        )

        # ── log extra SpaCy fields (not saved — model has no columns) ───
        logger.debug(
            f"[Step 3] SpaCy extras (not saved): "
            f"entities={len(analysis.get('key_entities', []))} | "
            f"topics={analysis.get('main_topics', [])} | "
            f"sentiment={analysis.get('sentiment', 'neutral')}"
        )

        logger.info(
            f"Step 3 done — "
            f"filler={analysis.get('filler_word_count', 0)} | "
            f"clarity={analysis.get('clarity_score', 0):.1f}% | "
            f"relevance={analysis.get('relevance_score', 0):.1f}%"
        )

    except Exception as e:
        logger.error(f"Step 3 failed: {e}", exc_info=True)
        # Non-fatal: pipeline continues without ContentAnalysis record


# ======================================================================
# IMPROVEMENT TIPS  (produces the TextField value)
# ======================================================================

def _build_improvement_tips(analysis: dict) -> list:
    """
    Convert SpaCy analysis dict into a list of human-readable tip strings.
    Result is joined and stored in ContentAnalysis.improvement_tips (TextField).
    """
    tips = []

    filler_count   = analysis.get('filler_word_count', 0) or 0
    keyword_score  = analysis.get('keyword_score',     0) or 0
    clarity_score  = analysis.get('clarity_score',     0) or 0
    grammar_issues = analysis.get('grammar_issues',    []) or []
    word_count     = analysis.get('word_count',        0) or 0
    unique_words   = analysis.get('unique_words',      0) or 0

    if filler_count > 5:
        tips.append(
            "Reduce filler words (um, uh, like) — pause briefly instead"
        )

    if keyword_score < 60:
        tips.append(
            "Include more relevant technical terms from the job description"
        )
    elif keyword_score < 75:
        tips.append(
            "Good keyword usage — try to add more domain-specific terminology"
        )

    if clarity_score < 70:
        tips.append(
            "Improve clarity by using shorter sentences (12–20 words is ideal)"
        )

    if len(grammar_issues) > 2:
        tips.append(
            "Pay attention to sentence structure — each sentence needs a subject and verb"
        )

    if word_count < 30:
        tips.append(
            "Provide more detail — aim for 50–150 words per answer"
        )
    elif word_count > 250:
        tips.append(
            "Keep answers concise — aim for 50–150 words per answer"
        )

    if word_count > 0 and unique_words / word_count < 0.4:
        tips.append(
            "Vary your vocabulary — avoid repeating the same words"
        )

    if not tips:
        tips.append(
            "Good performance — keep practicing to maintain consistency"
        )

    return tips[:5]


# ======================================================================
# MAIN PIPELINE
# ======================================================================

def process_answer_with_enhanced_scoring(answer, question):
    """
    Full AI analysis pipeline for a single interview answer.

    Steps:
      1  Whisper transcription
      2  Keyword analysis        (KeywordService)
      3  SpaCy content analysis  (SpaCyNLPService)  ← uses SpaCy
      4  Semantic similarity     (SemanticAnalyzer)
      5  Weighted scoring        (WeightedScorer)
      6  Facial analysis         (MediaPipe, if video)
      7  Prosody analysis        (Librosa, if audio)
    """
    logger.info("=== Enhanced AI Analysis START ===")

    # STEP 1: TRANSCRIPTION
    try:
        logger.info("Step 1: Transcribing audio...")

        from interviews.ai_services.whisper_stt import get_whisper_service

        whisper            = get_whisper_service()
        transcription      = whisper.transcribe_audio(answer.audio_file.path)
        answer.transcribed_text = transcription['text']
        answer.duration         = float(transcription.get('duration', 0))
        answer.save()

        logger.info(f"Transcribed: {len(answer.transcribed_text)} chars")

        if not answer.transcribed_text or len(answer.transcribed_text.strip()) < 10:
            logger.warning("Transcription too short — setting low default scores")
            answer.keyword_relevance_score  = 10
            answer.semantic_similarity_score = 10
            answer.completeness_score        = 10
            answer.final_content_score       = 10
            answer.is_processed              = True
            answer.save()
            return

    except Exception as e:
        logger.error(f"Step 1 failed: {e}", exc_info=True)
        raise


    # STEP 2: KEYWORD ANALYSIS
    process_answer_step_2_keyword_analysis(answer=answer, question=question)

    # STEP 3: SPACY CONTENT ANALYSIS  
    process_answer_step_3_spacy_analysis(answer=answer, question=question)

    # STEP 4: SEMANTIC SIMILARITY
    try:
        logger.info("Step 4: Semantic similarity...")

        from interviews.ai_services.semantic_analyzer import get_semantic_analyzer

        semantic_result = get_semantic_analyzer().calculate_similarity_score(
            answer_text=answer.transcribed_text,
            question_text=question.question_text,
            expected_answer=question.expected_answer,
            expected_keywords=question.expected_keywords,
        )

        answer.semantic_similarity_score = semantic_result['percentage']
        logger.info(f"Semantic: {semantic_result['percentage']:.1f}%")

    except Exception as e:
        logger.error(f"Step 4 failed: {e}", exc_info=True)
        answer.semantic_similarity_score = 0

    # STEP 5: WEIGHTED SCORING
    try:
        logger.info("Step 5: Weighted scoring...")

        from interviews.ai_services.weighted_scorer import get_weighted_scorer

        weighted_result = get_weighted_scorer().calculate_weighted_score(
            semantic_score=float(answer.semantic_similarity_score),
            keyword_score=float(answer.keyword_relevance_score),
            answer_text=answer.transcribed_text,
            question_text=question.question_text,
            question_type=question.question_type,
            job_role=answer.session.job_role.role_name,
        )

        answer.final_content_score = weighted_result['final_score']
        answer.completeness_score  = weighted_result['components']['completeness']['score']
        answer.score_breakdown     = weighted_result

        logger.info(f"Final content score: {answer.final_content_score:.1f}%")

    except Exception as e:
        logger.error(f"Step 5 failed: {e}", exc_info=True)
        # Fallback: average of semantic + keyword
        answer.final_content_score = (
            float(answer.semantic_similarity_score) +
            float(answer.keyword_relevance_score)
        ) / 2
        answer.completeness_score = 50

    # STEP 6: FACIAL ANALYSIS 
    try:
        if answer.video_file:
            logger.info("Step 6: Facial analysis...")

            from interviews.ai_services.mediapipe_facial import get_mediapipe_service
            from interviews.models import FacialAnalysis

            facial = get_mediapipe_service().analyze_video(answer.video_file.path)

            FacialAnalysis.objects.update_or_create(
                answer=answer,
                defaults={
                    'confidence_score':  float(facial.get('confidence_score', 50)),
                    'stress_score':      float(facial.get('stress_score', 50)),
                    'dominant_emotion':  facial.get('dominant_emotion', 'neutral'),
                    'emotion_timeline':  facial.get('emotion_timeline', {}),
                    'eye_contact_score': float(facial.get('eye_contact_score', 50)),
                }
            )
            logger.info("Facial analysis done")
        else:
            logger.info("Step 6: No video file — skipping facial analysis")

    except Exception as e:
        logger.error(f"Step 6 failed: {e}", exc_info=True)


    # STEP 7: PROSODY ANALYSIS 
    try:
        if answer.audio_file:
            logger.info("Step 7: Prosody analysis...")

            from interviews.ai_services.librosa_prosody import get_librosa_service
            from interviews.models import ProsodyAnalysis

            def _to_python(obj):
                """Recursively convert numpy types to Python native types."""
                if isinstance(obj, np.integer):
                    return int(obj)
                if isinstance(obj, np.floating):
                    return float(obj)
                if isinstance(obj, np.ndarray):
                    return obj.tolist()
                if isinstance(obj, dict):
                    return {k: _to_python(v) for k, v in obj.items()}
                if isinstance(obj, list):
                    return [_to_python(i) for i in obj]
                return obj

            prosody = get_librosa_service().analyze_audio(
                audio_path=answer.audio_file.path,
                transcription_text=answer.transcribed_text,
            )

            ProsodyAnalysis.objects.update_or_create(
                answer=answer,
                defaults={
                    # Speech metrics
                    'speaking_pace_wpm':     float(prosody.get('speaking_pace_wpm', 120)),
                    'average_pitch_hz':      float(prosody.get('average_pitch_hz', 150)),
                    'pitch_variation':       float(prosody.get('pitch_variation', 20)),
                    'volume_consistency':    float(prosody.get('volume_consistency', 70)),
                    
                    # NEW: Energy and vocal metrics
                    'energy_stability':      float(prosody.get('energy_stability', 70)),
                    'vocal_confidence':      float(prosody.get('vocal_confidence', 70)),
                    
                    # Pause analysis
                    'pause_count':           int(prosody.get('pause_count', 0)),
                    'average_pause_duration': float(prosody.get('average_pause_duration', 0)),
                    
                    # NEW: Detailed pause types
                    'natural_pauses':        int(prosody.get('natural_pauses', 0)),
                    'hesitation_pauses':     int(prosody.get('hesitation_pauses', 0)),
                    'long_pauses':           int(prosody.get('long_pauses', 0)),
                    
                    # NEW: Duration metrics
                    'speech_duration':       float(prosody.get('speech_duration', 0)),
                    'audio_duration':        float(prosody.get('audio_duration', 0)),
                    
                    # Timeline data
                    'pace_timeline':         _to_python(prosody.get('pace_timeline', {})),
                    'pitch_timeline':        _to_python(prosody.get('pitch_timeline', {})),
                    
                    # NEW: Energy timeline
                    'energy_timeline':       _to_python(prosody.get('energy_timeline', {})),
                }
            )
            logger.info(
                f"Prosody analysis done — "
                f"pace={prosody.get('speaking_pace_wpm', 0)}wpm, "
                f"energy={prosody.get('energy_stability', 0)}%, "
                f"confidence={prosody.get('vocal_confidence', 0)}%, "
                f"pauses={prosody.get('pause_count', 0)}"
            )
        else:
            logger.info("Step 7: No audio file — skipping prosody analysis")
    except Exception as e:
        logger.error(f"Step 7 failed: {e}", exc_info=True)

    # ------------------------------------------------------------------
    # DONE
    # ------------------------------------------------------------------
    answer.is_processed = True
    answer.save()

    logger.info(
        f"=== Enhanced AI Analysis COMPLETE === "
        f"final={answer.final_content_score:.1f}% | "
        f"semantic={answer.semantic_similarity_score:.1f}% | "
        f"keywords={answer.keyword_relevance_score:.1f}%"
    )
 
# =====================================================
# COMPARISON/TESTING FUNCTION
# =====================================================
 
def compare_old_vs_new_keyword_scoring(answer, question):
    logger.info("\n" + "="*80)
    logger.info("OLD vs NEW KEYWORD SCORING COMPARISON")
    logger.info("="*80)
    
    # Test OLD system
    process_answer_step_2_keyword_analysis(
        answer=answer,
        question=question,
        use_new_pipeline=False
    )
    old_score = float(answer.keyword_relevance_score)
    old_keywords = list(answer.detected_keywords)
    
    logger.info(f"OLD System: {old_score:.1f}% | Matched: {old_keywords}")
    
    # Test NEW system
    process_answer_step_2_keyword_analysis(
        answer=answer,
        question=question,
        use_new_pipeline=True
    )
    new_score = float(answer.keyword_relevance_score)
    new_keywords = list(answer.detected_keywords)
    
    logger.info(f"NEW System: {new_score:.1f}% | Matched: {new_keywords}")
    
    # Calculate difference
    diff = new_score - old_score
    logger.info(f"Difference: {diff:+.1f}%")
    
    logger.info("="*80 + "\n")
    
    return {
        'old_score': old_score,
        'old_keywords': old_keywords,
        'new_score': new_score,
        'new_keywords': new_keywords,
        'difference': diff
    }

@login_required
def complete_interview(request, session_id):
    """Complete interview and generate report"""
    session = get_object_or_404(InterviewSession, session_id=session_id, user=request.user)
    
    # End the interview
    session.end_interview()
    
    # Generate comprehensive feedback report
    generate_feedback_report(session)
    
    # Update user statistics
    profile = request.user.profile
    profile.update_statistics()
    
    messages.success(request, 'Interview completed! Your feedback report is ready.')
    return redirect('feedback_report', session_id=session.session_id)


"""
generate_feedback_report — UPDATED to read SpaCy ContentAnalysis
=================================================================

WHAT CHANGED:
  - Reads content_analysis.filler_word_count  (set by SpaCy in step 3)
  - Reads content_analysis.clarity_score      (set by SpaCy in step 3)
  - Reads content_analysis.sentiment          (set by SpaCy in step 3)
  - Reads content_analysis.grammar_issues     (set by SpaCy in step 3)
  - Generates improvement tips from SpaCy data (was in SpaCy service before)
  - generate_improvement_tips() moved HERE from SpaCy service (correct place)
"""

import logging
from django.conf import settings

logger = logging.getLogger(__name__)


# ======================================================================
# IMPROVEMENT TIPS  (moved from SpaCyNLPService — this is where it belongs)
# ======================================================================

def generate_improvement_tips_from_analysis(content_analysis) -> list:
    """
    Generate human-readable tips from a ContentAnalysis DB object.

    Previously lived in SpaCyNLPService.generate_improvement_tips().
    Moved here because this is the only place it was ever needed.

    Args:
        content_analysis: ContentAnalysis model instance (or None)

    Returns:
        list of tip strings (max 5)
    """
    if content_analysis is None:
        return ["Continue practicing regularly to improve your interview skills."]

    tips = []

    filler_count  = getattr(content_analysis, 'filler_word_count', 0) or 0
    keyword_score = getattr(content_analysis, 'keyword_score', 0)     or 0
    clarity_score = getattr(content_analysis, 'clarity_score', 0)     or 0
    grammar_issues = getattr(content_analysis, 'grammar_issues', [])  or []
    word_count    = getattr(content_analysis, 'word_count', 0)        or 0
    unique_words  = getattr(content_analysis, 'unique_words', 0)      or 0

    # Filler words
    if filler_count > 5:
        tips.append(
            "Reduce filler words (um, uh, like) — pause briefly instead to gather your thoughts"
        )

    # Keyword usage
    if keyword_score < 60:
        tips.append(
            "Include more relevant technical terms and keywords from the job description"
        )
    elif keyword_score < 75:
        tips.append(
            "Good keyword usage — try to incorporate even more domain-specific terminology"
        )

    # Clarity
    if clarity_score < 70:
        tips.append(
            "Improve clarity by using shorter, structured sentences (12–20 words is ideal)"
        )

    # Grammar
    if len(grammar_issues) > 2:
        tips.append(
            "Pay attention to sentence structure — ensure each sentence has a clear subject and verb"
        )

    # Word count
    if word_count < 30:
        tips.append(
            "Provide more detailed answers — aim for 50–150 words per question"
        )
    elif word_count > 250:
        tips.append(
            "Keep answers concise — aim for 50–150 words per question"
        )

    # Vocabulary diversity
    if word_count > 0 and (unique_words / word_count) < 0.4:
        tips.append(
            "Expand your vocabulary to avoid repetition — use synonyms and varied expressions"
        )

    if not tips:
        tips.append(
            "Excellent performance! Continue practicing to maintain consistency across all interviews."
        )

    return tips[:5]


# ======================================================================
# MAIN REPORT FUNCTION
# ======================================================================

def generate_feedback_report(session):
    """
    Generate comprehensive feedback report.

    Reads all analysis results stored by the 7-step pipeline and
    compiles them into a FeedbackReport saved to the database.
    """
    from interviews.models import FeedbackReport

    try:
        all_answers       = session.answers.all()
        processed_answers = session.answers.filter(is_processed=True)

        if not all_answers.exists():
            raise ValueError("No answers found for this session")

        if not processed_answers.exists():
            logger.warning(f"No processed answers for session {session.session_id}")
            return _create_default_report(session)

        logger.info(
            f"Generating report for session {session.session_id}: "
            f"{processed_answers.count()}/{all_answers.count()} answers processed"
        )

        content_scores    = []
        delivery_scores   = []
        confidence_scores = []
        strengths         = []
        improvements      = []

        for answer in processed_answers:
            try:
                # ------------------------------------------------------
                # CONTENT SCORE  (from weighted_scorer, step 5)
                # ------------------------------------------------------
                if getattr(answer, 'final_content_score', None):
                    content_score = float(answer.final_content_score)
                    content_scores.append(content_score)

                    if content_score >= 80:
                        strengths.append("Excellent content quality and relevance")
                    elif content_score >= 70:
                        strengths.append("Strong content quality in responses")

                    if getattr(answer, 'semantic_similarity_score', None):
                        sem = float(answer.semantic_similarity_score)
                        if sem >= 70:
                            strengths.append("Exceptional understanding of question context")
                        elif sem >= 60:
                            strengths.append("Good semantic understanding")
                        elif sem < 40:
                            improvements.append("Ensure answers directly address the question")

                    if content_score < 60:
                        improvements.append("Provide more detailed and relevant answers")
                    elif content_score < 70:
                        improvements.append("Enhance answer depth with specific examples")

                # ------------------------------------------------------
                # SPACY CONTENT ANALYSIS  (from step 3)  ← reads SpaCy data
                # ------------------------------------------------------
                content_analysis = None
                if hasattr(answer, 'content_analysis'):
                    try:
                        content_analysis = answer.content_analysis
                    except Exception:
                        content_analysis = None

                if content_analysis:
                    filler_count = getattr(content_analysis, 'filler_word_count', 0) or 0
                    clarity      = getattr(content_analysis, 'clarity_score', 0)     or 0
                    sentiment    = getattr(content_analysis, 'sentiment', 'neutral') or 'neutral'

                    # Strengths from SpaCy data
                    if filler_count <= 2:
                        strengths.append("Minimal use of filler words — speaks clearly")
                    if clarity >= 80:
                        strengths.append("Excellent answer clarity and sentence structure")
                    elif clarity >= 65:
                        strengths.append("Good communication clarity")
                    if sentiment == 'positive':
                        strengths.append("Positive and confident tone throughout")

                    # Improvements from SpaCy data
                    if filler_count > 6:
                        improvements.append("Reduce use of filler words (um, uh, like)")
                    if clarity < 60:
                        improvements.append("Use shorter, clearer sentences (12–20 words ideal)")

                    # Generate tips from SpaCy analysis
                    spacy_tips = generate_improvement_tips_from_analysis(content_analysis)
                    improvements.extend(spacy_tips)

                # ------------------------------------------------------
                # DELIVERY SCORE  (from prosody analysis, step 7)
                # ------------------------------------------------------
                # ------------------------------------------------------
# DELIVERY SCORE  (from prosody analysis, step 7)
# ------------------------------------------------------
                if hasattr(answer, 'prosody_analysis'):
                    try:
                        prosody = answer.prosody_analysis
                        if prosody:
                            pace             = float(getattr(prosody, 'speaking_pace_wpm', 120))
                            volume_score     = float(getattr(prosody, 'volume_consistency', 75))
                            energy_score     = float(getattr(prosody, 'energy_stability', 75))
                            vocal_confidence = float(getattr(prosody, 'vocal_confidence', 75))

                            volume_score     = max(40, min(100, volume_score))
                            energy_score     = max(40, min(100, energy_score))
                            vocal_confidence = max(40, min(100, vocal_confidence))

                            if 115 <= pace <= 155:
                                pace_score = 95
                            elif 100 <= pace <= 170:
                                pace_score = 88
                            elif 85 <= pace <= 185:
                                pace_score = 75
                            else:
                                pace_score = 60

                            weighted_delivery = (
                                pace_score       * 0.25 +
                                volume_score     * 0.20 +
                                energy_score     * 0.25 +
                                vocal_confidence * 0.30
                            )

                            # Use new detailed pause fields
                            hesitation = int(getattr(prosody, 'hesitation_pauses', 0))
                            long_p     = int(getattr(prosody, 'long_pauses', 0))
                            total_p    = hesitation + long_p

                            if total_p <= 5:
                                pause_penalty = 0
                            elif total_p <= 10:
                                pause_penalty = 3
                            elif total_p <= 15:
                                pause_penalty = 6
                            elif total_p <= 20:
                                pause_penalty = 10
                            else:
                                pause_penalty = 15

                            delivery = round(max(55, min(100, weighted_delivery - pause_penalty)), 2)
                            delivery_scores.append(delivery)

                            logger.debug(
                                f"Delivery {delivery:.1f}% | pace={pace:.0f}wpm "
                                f"vol={volume_score:.0f} energy={energy_score:.0f} "
                                f"conf={vocal_confidence:.0f} pauses={total_p} pen=-{pause_penalty}"
                            )

                            # Delivery strengths / improvements
                            if delivery >= 85:
                                strengths.append("Excellent communication delivery and speaking clarity")
                            elif delivery >= 75:
                                strengths.append("Strong speaking delivery with confident communication")
                            elif delivery >= 65:
                                strengths.append("Good communication and understandable speaking style")

                            if pace < 90:
                                improvements.append("Speak slightly faster to improve engagement")
                            elif pace > 185:
                                improvements.append("Slow down slightly for better clarity")
                            if total_p > 15:
                                improvements.append("Reduce hesitation pauses for smoother communication")
                            if vocal_confidence < 60:
                                improvements.append("Practice speaking with stronger vocal confidence")
                            if energy_score < 60:
                                improvements.append("Maintain more vocal energy throughout your answer")
                            if volume_score < 60:
                                improvements.append("Maintain more consistent speaking volume")

                    except Exception as e:
                        logger.warning(f"Prosody read error for answer {answer.pk}: {e}")

                # ------------------------------------------------------
                # CONFIDENCE SCORE  (from facial analysis, step 6)
                # ------------------------------------------------------
                if hasattr(answer, 'facial_analysis'):
                    try:
                        facial = answer.facial_analysis
                        if facial:
                            conf  = float(getattr(facial, 'confidence_score', 70))
                            eye   = float(getattr(facial, 'eye_contact_score', 70) or 70)
                            stress = float(getattr(facial, 'stress_score', 50) or 50)

                            confidence_scores.append(conf)

                            if conf >= 80:
                                strengths.append("Exceptional confidence and composure")
                            elif conf >= 70:
                                strengths.append("Good confidence and composure")
                            elif conf < 50:
                                improvements.append("Practice to build confidence for interviews")

                            if eye >= 75:
                                strengths.append("Maintained excellent eye contact")
                            elif eye < 50:
                                improvements.append("Maintain better eye contact with the camera")

                            if stress > 65:
                                improvements.append("Practice relaxation techniques to reduce interview stress")

                    except Exception as e:
                        logger.warning(f"Facial read error for answer {answer.pk}: {e}")

            except Exception as e:
                logger.error(f"Error processing answer {getattr(answer, 'pk', '?')}: {e}", exc_info=True)
                continue

        # ------------------------------------------------------------------
        # AGGREGATE SCORES
        # ------------------------------------------------------------------
        content_score    = sum(content_scores)    / len(content_scores)    if content_scores    else 50.0
        delivery_score   = sum(delivery_scores)   / len(delivery_scores)   if delivery_scores   else 70.0
        confidence_score = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 70.0

        overall_score = (
            content_score    * 0.50 +
            delivery_score   * 0.30 +
            confidence_score * 0.20
        )

        # Deduplicate and cap lists
        strengths    = list(dict.fromkeys(strengths))[:6]
        improvements = list(dict.fromkeys(improvements))[:6]

        if not strengths:
            strengths = [
                "Completed the interview successfully",
                f"Answered {processed_answers.count()} questions",
            ]
        if not improvements:
            improvements = [
                "Continue practicing regularly to improve skills",
                "Record more practice interviews for better feedback",
            ]

        # ------------------------------------------------------------------
        # SUMMARY
        # ------------------------------------------------------------------
        processed_count = processed_answers.count()
        total_count     = all_answers.count()

        if overall_score >= 85:
            summary = (
                f"Outstanding performance! Score: {overall_score:.1f}%. "
                "You demonstrated excellent interview skills across all areas."
            )
        elif overall_score >= 75:
            summary = (
                f"Excellent work! Score: {overall_score:.1f}%. "
                "Strong communication skills with solid content knowledge."
            )
        elif overall_score >= 65:
            summary = (
                f"Good effort! Score: {overall_score:.1f}%. "
                "You showed good understanding with room for improvement."
            )
        elif overall_score >= 50:
            summary = (
                f"Fair performance. Score: {overall_score:.1f}%. "
                "You have a foundation to build on — keep practicing."
            )
        else:
            summary = (
                f"Keep practicing! Score: {overall_score:.1f}%. "
                "Review the feedback carefully and dedicate time to improvement."
            )

        if processed_count < total_count:
            summary += f" Note: {processed_count} of {total_count} answers were analysed."

        # ------------------------------------------------------------------
        # DETAILED AVERAGES  (for report metadata)
        # ------------------------------------------------------------------
        avg_filler = avg_pace = avg_word_count = 0.0
        try:
            ca_list = [
                getattr(a, 'content_analysis', None)
                for a in processed_answers
                if getattr(a, 'content_analysis', None)
            ]
            if ca_list:
                filler_vals = [getattr(c, 'filler_word_count', 0) or 0 for c in ca_list]
                word_vals   = [getattr(c, 'word_count', 0)         or 0 for c in ca_list]
                avg_filler      = sum(filler_vals) / len(filler_vals)
                avg_word_count  = sum(word_vals)   / len(word_vals)

            pa_list = [
                getattr(a, 'prosody_analysis', None)
                for a in processed_answers
                if getattr(a, 'prosody_analysis', None)
            ]
            if pa_list:
                pace_vals = [getattr(p, 'speaking_pace_wpm', 0) or 0 for p in pa_list]
                avg_pace  = sum(pace_vals) / len(pace_vals)

        except Exception as e:
            logger.warning(f"Average calculation error: {e}")

        # ------------------------------------------------------------------
        # SAVE REPORT
        # ------------------------------------------------------------------
        report = FeedbackReport.objects.create(
            session=session,
            overall_score    = round(overall_score,    2),
            content_score    = round(content_score,    2),
            delivery_score   = round(delivery_score,   2),
            confidence_score = round(confidence_score, 2),
            summary_feedback = summary,
            strengths             = strengths,
            areas_for_improvement = improvements,
            detailed_analysis={
                'total_answers':     total_count,
                'processed_answers': processed_count,
                'avg_filler_words':  round(avg_filler,     2),
                'avg_speaking_pace': round(avg_pace,        2),
                'avg_word_count':    round(avg_word_count,  1),
                'avg_content_score': round(content_score,   2),
                'status':            'complete',
                'scoring_version':   '2.1',
            }
        )

        logger.info(
            f"Report {report.report_id} created — "
            f"overall={overall_score:.1f}% "
            f"content={content_score:.1f}% "
            f"delivery={delivery_score:.1f}% "
            f"confidence={confidence_score:.1f}%"
        )
        return report

    except Exception as e:
        logger.error(f"generate_feedback_report failed: {e}", exc_info=True)
        raise


# ======================================================================
# DEFAULT REPORT (incomplete session)
# ======================================================================

def _create_default_report(session):
    from interviews.models import FeedbackReport

    return FeedbackReport.objects.create(
        session=session,
        overall_score    = 0.0,
        content_score    = 0.0,
        delivery_score   = 0.0,
        confidence_score = 0.0,
        summary_feedback = (
            "No processed answers available. Please complete the interview "
            "and ensure answers are processed before viewing this report."
        ),
        strengths             = ["Interview initiated"],
        areas_for_improvement = [
            "Complete all interview questions",
            "Ensure clear audio/video quality",
            "Wait for processing to complete before viewing the report",
        ],
        detailed_analysis={
            'total_answers':     session.answers.count(),
            'processed_answers': 0,
            'status':            'incomplete',
        }
    )

@login_required
@login_required
def interview_history(request):
    """View interview history with filters"""
    # Get all sessions for the user
    sessions = InterviewSession.objects.filter(user=request.user).select_related('job_role', 'feedback_report')
    
    # Apply filters
    status_filter = request.GET.get('status', '')
    job_role_filter = request.GET.get('job_role', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search_query = request.GET.get('search', '')
    
    # Status filter
    if status_filter:
        sessions = sessions.filter(status=status_filter)
    
    # Job role filter
    if job_role_filter:
        sessions = sessions.filter(job_role__role_id=job_role_filter)
    
    # Date range filter
    if date_from:
        from datetime import datetime
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            sessions = sessions.filter(created_at__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        from datetime import datetime
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            # Add one day to include the end date
            from datetime import timedelta
            date_to_obj = date_to_obj + timedelta(days=1)
            sessions = sessions.filter(created_at__lt=date_to_obj)
        except ValueError:
            pass
    
    # Search filter (job role name)
    if search_query:
        sessions = sessions.filter(job_role__role_name__icontains=search_query)
    
    # Order by most recent
    sessions = sessions.order_by('-created_at')
    
    # Get all unique job roles for filter dropdown
    all_job_roles = JobRole.objects.filter(
        interviewsession__user=request.user
    ).distinct().order_by('role_name')
    
    context = {
        'sessions': sessions,
        'all_job_roles': all_job_roles,
        'status_filter': status_filter,
        'job_role_filter': job_role_filter,
        'date_from': date_from,
        'date_to': date_to,
        'search_query': search_query,
    }
    return render(request, 'interviews/history.html', context)

def create_default_report(session):
    """Create a default report when AI processing fails"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Creating default report for session {session.session_id}")
    
    # Count answers
    total_answers = session.answers.count()
    processed_answers = session.answers.filter(is_processed=True).count()
    
    # Get any transcriptions that exist
    transcribed_answers = session.answers.exclude(transcribed_text='').count()
    
    # Basic strengths and improvements
    strengths = [
        f"Completed the interview with {total_answers} questions",
        "Demonstrated commitment to interview preparation",
    ]
    
    if transcribed_answers > 0:
        strengths.append(f"Provided verbal responses to {transcribed_answers} questions")
    
    improvements = [
        "Ensure good audio quality for better AI analysis",
        "Practice speaking clearly and at a moderate pace",
        "Try another interview for comprehensive AI feedback",
    ]
    
    if processed_answers > 0:
        improvements.append(f"{processed_answers} answers were successfully analyzed")
    
    # Create summary
    if processed_answers == 0:
        summary = (
            f"You completed an interview with {total_answers} questions. "
            f"Unfortunately, the AI analysis could not be completed due to technical issues. "
            f"This may be due to audio quality or file format issues. "
            f"Please try recording another interview for full AI-powered feedback."
        )
    else:
        summary = (
            f"You completed an interview with {total_answers} questions. "
            f"{processed_answers} answers were successfully analyzed by AI. "
            f"Review the feedback below and consider practicing more for better results."
        )
    
    # Create report with default values
    report = FeedbackReport.objects.create(
        session=session,
        overall_score=70.0,
        content_score=70.0,
        delivery_score=70.0,
        confidence_score=70.0,
        summary_feedback=summary,
        strengths=strengths,
        areas_for_improvement=improvements,
        detailed_analysis={
            'total_answers': total_answers,
            'processed_answers': processed_answers,
            'transcribed_answers': transcribed_answers,
            'status': 'default_report',
            'note': 'AI processing incomplete - default values used',
            'reason': 'Technical issues with audio processing'
        }
    )
    
    logger.info(f"Created default report {report.report_id} for session {session.session_id}")
    return report

@login_required
def feedback_report(request, session_id):
    """View feedback report with correct stats"""
    import logging
    logger = logging.getLogger(__name__)
    
    session = get_object_or_404(InterviewSession, session_id=session_id, user=request.user)
    
    # Try to get existing report
    report = None
    try:
        report = session.feedback_report
        logger.info(f"Found existing report for session {session_id}")
    except FeedbackReport.DoesNotExist:
        logger.warning(f"No report exists for session {session_id}, attempting to generate")
        
        # Check if interview is completed
        if session.status != 'completed':
            messages.error(request, 'Interview not yet completed. Please finish the interview first.')
            return redirect('interview_conduct', session_id=session_id)
        
        # Check answers
        total_answers = session.answers.count()
        processed_answers = session.answers.filter(is_processed=True).count()
        
        logger.info(f"Session {session_id}: {processed_answers}/{total_answers} answers processed")
        
        if total_answers == 0:
            messages.error(request, 'No answers recorded for this interview.')
            return redirect('dashboard')
        
        # Try to generate report
        try:
            if processed_answers == 0:
                messages.warning(request, 
                    f'AI processing failed for all answers. Generating basic report...')
                report = create_default_report(session)
            else:
                generate_feedback_report(session)
                report = session.feedback_report
                messages.success(request, 'Feedback report generated successfully!')
                
        except Exception as e:
            logger.error(f"Failed to generate report for session {session_id}: {str(e)}")
            logger.exception("Full traceback:")
            
            # Create default report as fallback
            try:
                report = create_default_report(session)
                messages.warning(request, 
                    'Generated basic report. Full AI analysis was unavailable.')
            except Exception as e2:
                logger.error(f"Failed to create default report: {str(e2)}")
                messages.error(request, 
                    'Unable to generate feedback report. Please contact support.')
                return redirect('dashboard')
    
    # Double check we have a report
    if report is None:
        messages.error(request, 'Report generation failed. Please try again.')
        return redirect('dashboard')
    
    # Calculate additional stats
    total_words = 0
    avg_speaking_pace = 0
    total_duration = 0
    
    # Get all processed answers
    processed_answers = session.answers.filter(is_processed=True)
    
    if processed_answers.exists():
        # Calculate total words from content analysis
        for answer in processed_answers:
            if hasattr(answer, 'content_analysis'):
                total_words += answer.content_analysis.word_count
            
            # Sum up durations
            if answer.duration:
                total_duration += answer.duration
        
        # Calculate average speaking pace
        pace_list = []
        for answer in processed_answers:
            if hasattr(answer, 'prosody_analysis') and answer.prosody_analysis.speaking_pace_wpm > 0:
                pace_list.append(answer.prosody_analysis.speaking_pace_wpm)
        
        if pace_list:
            avg_speaking_pace = sum(pace_list) / len(pace_list)
    
    # Update session duration if not set
    if session.duration_minutes == 0 and total_duration > 0:
        session.duration_minutes = total_duration / 60  # Convert seconds to minutes
        session.save()

    avg_confidence = 0
    avg_stress = 0
    dominant_emotion_counts = {}

    if processed_answers.exists():
    # Calculate average confidence and stress
        confidence_list = []
        stress_list = []
    
        for answer in processed_answers:
            if hasattr(answer, 'facial_analysis'):
                confidence_list.append(answer.facial_analysis.confidence_score)
                stress_list.append(answer.facial_analysis.stress_score)
            
                # Count emotions
                emotion = answer.facial_analysis.dominant_emotion
                dominant_emotion_counts[emotion] = dominant_emotion_counts.get(emotion, 0) + 1
    
        if confidence_list:
            avg_confidence = sum(confidence_list) / len(confidence_list)
        if stress_list:
            avg_stress = sum(stress_list) / len(stress_list)

    # Get most common emotion
    dominant_emotion = 'neutral'
    if dominant_emotion_counts:
        dominant_emotion = max(dominant_emotion_counts, key=dominant_emotion_counts.get)
    context = {
        'session': session,
        'report': report,
        'total_words': total_words,
        'avg_speaking_pace': round(avg_speaking_pace, 0) if avg_speaking_pace > 0 else 0,
        'interview_duration': session.duration_minutes,
        'avg_confidence': round(avg_confidence, 1),
        'avg_stress': round(avg_stress, 1),
        'dominant_emotion': dominant_emotion,
    }
    return render(request, 'reports/feedback.html', context)

@login_required
def export_report_json(request, session_id):
    """Export report as JSON"""
    session = get_object_or_404(InterviewSession, session_id=session_id, user=request.user)
    
    try:
        report = session.feedback_report
        
        # Build JSON data
        data = {
            'session_id': str(session.session_id),
            'user': session.user.username,
            'job_role': session.job_role.role_name,
            'date': session.created_at.isoformat(),
            'duration_minutes': session.duration_minutes,
            'overall_score': float(report.overall_score),
            'content_score': float(report.content_score),
            'delivery_score': float(report.delivery_score),
            'confidence_score': float(report.confidence_score),
            'summary': report.summary_feedback,
            'strengths': report.strengths,
            'improvements': report.areas_for_improvement,
            'answers': []
        }
        
        # Add answer details
        for answer in session.answers.all():
            answer_data = {
                'question': answer.question.question_text,
                'transcription': answer.transcribed_text,
                'duration': answer.duration,
            }
            
            if hasattr(answer, 'content_analysis'):
                content = answer.content_analysis
                answer_data['content_analysis'] = {
                    'relevance_score': float(content.relevance_score),
                    'clarity_score': float(content.clarity_score),
                    'filler_words': content.filler_word_count,
                    'word_count': content.word_count,
                }
            
            if hasattr(answer, 'prosody_analysis'):
                prosody = answer.prosody_analysis
                answer_data['prosody_analysis'] = {
                    'speaking_pace_wpm': prosody.speaking_pace_wpm,
                    'pitch_hz': prosody.average_pitch_hz,
                }
            
            data['answers'].append(answer_data)
        
        # Return JSON response
        response = JsonResponse(data, json_dumps_params={'indent': 2})
        response['Content-Disposition'] = f'attachment; filename="interview_report_{session_id}.json"'
        return response
        
    except FeedbackReport.DoesNotExist:
        return JsonResponse({'error': 'Report not found'}, status=404)


from django.http import FileResponse

@login_required
def export_report_pdf(request, session_id):
    import os
    from django.conf import settings
    from .ai_services.report_generator import get_pdf_generator
    
    session = get_object_or_404(InterviewSession, session_id=session_id, user=request.user)
    
    try:
        report = session.feedback_report
    except FeedbackReport.DoesNotExist:
        messages.error(request, 'No feedback report available for this interview.')
        return redirect('feedback_report', session_id=session_id)
    
    try:
        pdf_filename = f"interview_report_{session.session_id}.pdf"
        pdf_dir = os.path.join(settings.MEDIA_ROOT, 'reports', 'pdf')
        os.makedirs(pdf_dir, exist_ok=True)
        pdf_path = os.path.join(pdf_dir, pdf_filename)
        
        # Generate PDF
        pdf_generator = get_pdf_generator()
        pdf_generator.generate_report(session, report, pdf_path)
        
        # Use FileResponse (STREAMING)
        return FileResponse(
            open(pdf_path, 'rb'),
            as_attachment=True,
            filename=pdf_filename,
            content_type='application/pdf'
        )
            
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"PDF generation failed: {str(e)}")
        
        messages.error(request, f'Failed to generate PDF report: {str(e)}')
        return redirect('feedback_report', session_id=session_id)
    
@login_required
def user_profile(request):
    """View and edit user profile"""
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        # Update profile
        full_name = request.POST.get('full_name', '')
        experience_level = request.POST.get('experience_level', 'beginner')
        target_role_id = request.POST.get('target_role')
        
        profile.full_name = full_name
        profile.experience_level = experience_level
        
        if target_role_id:
            try:
                target_role = JobRole.objects.get(role_id=target_role_id)
                profile.target_role = target_role
            except JobRole.DoesNotExist:
                pass
        
        profile.save()
        
        # Update user info
        request.user.email = request.POST.get('email', request.user.email)
        request.user.save()
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('user_profile')
    
    # Get all job roles for target role selection
    job_roles = JobRole.objects.all()
    
    context = {
        'profile': profile,
        'job_roles': job_roles,
    }
    return render(request, 'interviews/profile.html', context)

@login_required
def user_settings(request):
    """User settings and preferences"""
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_password':
            # Change password
            current_password = request.POST.get('current_password')
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')
            
            if not request.user.check_password(current_password):
                messages.error(request, 'Current password is incorrect.')
            elif new_password != confirm_password:
                messages.error(request, 'New passwords do not match.')
            elif len(new_password) < 8:
                messages.error(request, 'Password must be at least 8 characters.')
            else:
                request.user.set_password(new_password)
                request.user.save()
                
                # Re-login user
                from django.contrib.auth import update_session_auth_hash
                update_session_auth_hash(request, request.user)
                
                messages.success(request, 'Password changed successfully!')
        
        elif action == 'clear_history':
            # Clear interview history
            if request.POST.get('confirm') == 'yes':
                InterviewSession.objects.filter(user=request.user).delete()
                profile.total_interviews = 0
                profile.average_score = 0
                profile.save()
                messages.success(request, 'Interview history cleared successfully!')
        
        return redirect('user_settings')
    
    context = {
        'profile': profile,
    }
    return render(request, 'interviews/settings.html', context)


@login_required
def delete_interview(request, session_id):
    if request.method == 'POST':

        session = InterviewSession.objects.filter(
            session_id=session_id,
            user=request.user
        ).first()

        if not session:
            messages.error(request, "Interview already deleted or not found.")
            return redirect('interview_history')

        # Delete session
        session.delete()

        # Ensure profile exists
        profile, created = UserProfile.objects.get_or_create(user=request.user)

        completed_sessions = InterviewSession.objects.filter(
            user=request.user,
            status='completed'
        )

        profile.total_interviews = completed_sessions.count()

        from django.db.models import Avg
        avg_score = completed_sessions.filter(
            feedback_report__isnull=False
        ).aggregate(avg=Avg('feedback_report__overall_score'))['avg']

        profile.average_score = avg_score or 0
        profile.save()

        messages.success(request, 'Interview deleted successfully!')

    return redirect('interview_history')

def forgot_password(request):
    """Forgot password - request reset"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        
        if not username or not email:
            messages.error(request, 'Please provide both username and email.')
            return render(request, 'auth/forgot_password.html')
        
        try:
            # Find user by username and email
            user = User.objects.get(username=username, email=email)
            
            # Generate verification code
            token = PasswordResetToken.generate_token()
            
            # Save token to database
            PasswordResetToken.objects.create(
                user=user,
                token=token,
                email=email
            )
            
            # Send email with verification code
            subject = 'Password Reset Verification Code - Vocal View'
            message = f"""
Hello {user.username},

You requested to reset your password for your Vocal View account.

Your verification code is: {token}

This code will expire in 10 minutes.

If you didn't request this password reset, please ignore this email.

Best regards,
The Vocal View Team
            """
            
            try:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False,
                )
                
                # Store username in session for verification page
                request.session['reset_username'] = username
                request.session['reset_email'] = email
                
                messages.success(request, f'Verification code sent to {email}')
                return redirect('verify_reset_code')
                
            except Exception as e:
                messages.error(request, 'Failed to send email. Please try again.')
                import logging
                logging.error(f"Email send error: {str(e)}")
                
        except User.DoesNotExist:
            messages.error(request, 'No account found with this username and email.')
    
    return render(request, 'auth/forgot_password.html')


def verify_reset_code(request):
    """Verify the reset code"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    username = request.session.get('reset_username')
    email = request.session.get('reset_email')
    
    if not username or not email:
        messages.error(request, 'Session expired. Please start over.')
        return redirect('forgot_password')
    
    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        
        if not code:
            messages.error(request, 'Please enter the verification code.')
            return render(request, 'auth/verify_code.html')
        
        try:
            user = User.objects.get(username=username, email=email)
            
            # Find valid token
            token = PasswordResetToken.objects.filter(
                user=user,
                token=code,
                is_used=False
            ).order_by('-created_at').first()
            
            if token and token.is_valid():
                # Mark token as used
                token.is_used = True
                token.save()
                
                # Store verification in session
                request.session['verified_reset_user'] = user.id
                
                messages.success(request, 'Code verified! Please set your new password.')
                return redirect('reset_password')
            else:
                messages.error(request, 'Invalid or expired verification code.')
                
        except User.DoesNotExist:
            messages.error(request, 'Session error. Please start over.')
            return redirect('forgot_password')
    
    return render(request, 'auth/verify_code.html', {
        'email': email
    })


def reset_password(request):
    """Reset password after verification"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    user_id = request.session.get('verified_reset_user')
    
    if not user_id:
        messages.error(request, 'Please verify your code first.')
        return redirect('forgot_password')
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, 'Invalid session. Please start over.')
        return redirect('forgot_password')
    
    if request.method == 'POST':
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        
        if not password1 or not password2:
            messages.error(request, 'Please enter both password fields.')
            return render(request, 'auth/reset_password.html', {'username': user.username})
        
        if password1 != password2:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'auth/reset_password.html', {'username': user.username})
        
        if len(password1) < 8:
            messages.error(request, 'Password must be at least 8 characters.')
            return render(request, 'auth/reset_password.html', {'username': user.username})
        
        if len(password1) < 20:
            messages.error(request, 'Password must be at less than 20 characters.')
            return render(request, 'auth/reset_password.html', {'username': user.username})
        
        # Set new password
        user.set_password(password1)
        user.save()
        
        # Clear session data
        request.session.pop('reset_username', None)
        request.session.pop('reset_email', None)
        request.session.pop('verified_reset_user', None)
        
        messages.success(request, 'Password reset successful! You can now login.')
        return redirect('login')
    
    return render(request, 'auth/reset_password.html', {
        'username': user.username
    })