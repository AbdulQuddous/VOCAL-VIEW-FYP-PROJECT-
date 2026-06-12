"""
IMPROVED Populate Expected Keywords Script
==========================================
Filters out generic words and uses expanded technical terms database

Usage:
    python populate_keywords_improved.py --dry-run    # Test first
    python populate_keywords_improved.py              # Run for real
"""

import os
import sys
import django

# Django setup
if __name__ == "__main__":
    project_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, project_path)
    
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vocalview.settings')
    django.setup()

from interviews.models import Question, JobRole
import spacy
import json
from pathlib import Path


# =====================================================
# STOP WORDS - Generic words to EXCLUDE from keywords
# =====================================================

GENERIC_STOP_WORDS = {
    # Generic question words
    'what', 'how', 'why', 'when', 'where', 'who', 'which',
    'describe', 'explain', 'tell', 'give', 'provide',
    
    # Generic nouns
    'you', 'your', 'experience', 'time', 'example', 'way',
    'process', 'approach', 'method', 'thing', 'part', 'aspect',
    'concept', 'definition', 'understanding', 'knowledge',
    'question', 'answer', 'situation', 'challenge', 'problem',
    
    # Generic verbs
    'do', 'make', 'use', 'get', 'know', 'think', 'work',
    'handle', 'manage', 'deal', 'ensure', 'implement',
    
    # Articles and prepositions
    'a', 'an', 'the', 'this', 'that', 'these', 'those',
    'in', 'on', 'at', 'to', 'for', 'with', 'from', 'of', 'about',
    
    # Role-agnostic terms
    'position', 'job', 'role', 'company', 'team', 'project'
}


# =====================================================
# LOAD EXPANDED TECHNICAL TERMS
# =====================================================

def load_expanded_tech_terms():
    """Load expanded technical terms from JSON file"""
    # Try to load from interviews/data/ first
    tech_terms_path = Path('interviews/data/tech_terms.json')
    
    if not tech_terms_path.exists():
        # Fallback to current directory
        tech_terms_path = Path('tech_terms_EXPANDED.json')
    
    if tech_terms_path.exists():
        with open(tech_terms_path, 'r') as f:
            return json.load(f)
    else:
        print("⚠️  Warning: tech_terms.json not found, using built-in terms")
        return {}


# Load tech terms
TECH_TERMS_DB = load_expanded_tech_terms()


# =====================================================
# ROLE-SPECIFIC KEYWORD EXTRACTION
# =====================================================

def get_role_category(role_name):
    """
    Map job role to category
    
    Args:
        role_name: Job role name (e.g., "Python Developer")
        
    Returns:
        str: Category key (e.g., "developer")
    """
    role_lower = role_name.lower()
    
    # Developer roles
    if any(word in role_lower for word in ['developer', 'engineer', 'programmer', 'coder']):
        if 'data' not in role_lower:
            return 'developer'
    
    # Data roles
    if any(word in role_lower for word in ['data', 'analyst', 'scientist', 'ml', 'ai']):
        return 'data'
    
    # Management roles
    if any(word in role_lower for word in ['manager', 'lead', 'director', 'pm', 'scrum master']):
        return 'management'
    
    # Design roles
    if any(word in role_lower for word in ['designer', 'ux', 'ui', 'design']):
        return 'design'
    
    # Marketing roles
    if any(word in role_lower for word in ['marketing', 'seo', 'growth', 'content']):
        return 'marketing'
    
    # DevOps roles
    if any(word in role_lower for word in ['devops', 'sre', 'infrastructure', 'cloud']):
        return 'devops'
    
    # Generic fallback
    return 'generic'


def get_tech_terms_for_role(role_name, max_terms=50):
    """
    Get all technical terms for a role
    
    Args:
        role_name: Job role name
        max_terms: Maximum terms to return
        
    Returns:
        list: Technical terms
    """
    category = get_role_category(role_name)
    
    if category not in TECH_TERMS_DB:
        return []
    
    # Combine all term types for the category
    all_terms = []
    for subcategory, terms in TECH_TERMS_DB[category].items():
        all_terms.extend(terms)
    
    return all_terms[:max_terms]


# =====================================================
# IMPROVED KEYWORD EXTRACTOR
# =====================================================

class ImprovedKeywordExtractor:
    """Extract keywords with generic word filtering"""
    
    def __init__(self):
        """Initialize SpaCy model"""
        self.nlp = spacy.load('en_core_web_sm')
        print("✅ SpaCy model loaded")
    
    def is_valid_keyword(self, keyword):
        """
        Check if keyword is valid (not generic)
        
        Args:
            keyword: Keyword to check
            
        Returns:
            bool: True if valid
        """
        keyword_lower = keyword.lower().strip()
        
        # Filter out stop words
        if keyword_lower in GENERIC_STOP_WORDS:
            return False
        
        # Filter out very short words (except common tech terms like 'r', 'c')
        if len(keyword_lower) < 2:
            return False
        
        # Filter out single letters that aren't known programming languages
        if len(keyword_lower) == 1 and keyword_lower not in ['r', 'c']:
            return False
        
        # Filter out multi-word phrases containing stop words
        words = keyword_lower.split()
        if len(words) > 1:
            # Check if phrase is mostly stop words
            stop_word_count = sum(1 for w in words if w in GENERIC_STOP_WORDS)
            if stop_word_count >= len(words) / 2:
                return False
        
        return True
    
    def extract_from_text(self, text, role_tech_terms=None):
        """
        Extract technical keywords from question text
        
        Args:
            text: Question text
            role_tech_terms: List of role-specific technical terms
            
        Returns:
            list: Valid technical keywords
        """
        if role_tech_terms is None:
            role_tech_terms = []
        
        doc = self.nlp(text.lower())
        keywords = set()
        
        # 1. Match against role-specific technical terms (HIGHEST PRIORITY)
        text_lower = text.lower()
        for term in role_tech_terms:
            if term.lower() in text_lower:
                keywords.add(term.lower())
        
        # 2. Extract technical nouns and proper nouns
        for token in doc:
            if token.pos_ in ['PROPN', 'NOUN']:
                if self.is_valid_keyword(token.text):
                    # Only add if it looks technical
                    if len(token.text) > 3 or token.text in ['api', 'sql', 'css', 'html', 'ui', 'ux']:
                        keywords.add(token.text)
        
        # 3. Extract noun chunks (technical phrases)
        for chunk in doc.noun_chunks:
            chunk_text = chunk.text.strip()
            # Only 2-3 word technical phrases
            if 2 <= len(chunk.text.split()) <= 3:
                if self.is_valid_keyword(chunk_text):
                    keywords.add(chunk_text)
        
        return sorted(list(keywords), key=len, reverse=True)
    
    def combine_keywords(self, text_keywords, role_tech_terms, max_total=10):
        """
        Combine text and role keywords intelligently
        
        Args:
            text_keywords: Keywords from question text
            role_tech_terms: Role-specific technical terms
            max_total: Maximum total keywords
            
        Returns:
            list: Combined keywords
        """
        combined = []
        
        # Priority 1: Text keywords that match role tech terms (MOST RELEVANT)
        for kw in text_keywords:
            if kw.lower() in [t.lower() for t in role_tech_terms]:
                if kw not in combined:
                    combined.append(kw)
        
        # Priority 2: Remaining text keywords (CONTEXT-SPECIFIC)
        for kw in text_keywords:
            if kw not in combined:
                combined.append(kw)
                if len(combined) >= max_total:
                    return combined
        
        # Priority 3: Top role tech terms (ROLE-SPECIFIC)
        for term in role_tech_terms[:20]:  # Top 20 most common
            if term not in combined:
                combined.append(term)
                if len(combined) >= max_total:
                    return combined
        
        return combined[:max_total]


# =====================================================
# MAIN POPULATION FUNCTION
# =====================================================

def populate_keywords_improved(dry_run=False, verbose=True):
    """
    Populate expected_keywords with improved filtering
    
    Args:
        dry_run: If True, show preview without saving
        verbose: If True, print detailed output
    """
    extractor = ImprovedKeywordExtractor()
    
    print("\n" + "="*80)
    print("IMPROVED KEYWORD POPULATION SCRIPT")
    print("="*80)
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be saved")
    else:
        print("✍️  LIVE MODE - Changes will be saved to database")
    
    print()
    
    # Get all questions
    all_questions = Question.objects.all()
    total_questions = all_questions.count()
    
    print(f"📊 Found {total_questions} questions to process\n")
    
    updated_count = 0
    
    for i, question in enumerate(all_questions, 1):
        # Get job role
        job_role = question.session.job_role if question.session else None
        job_role_name = job_role.role_name if job_role else "Generic"
        
        # Get role-specific technical terms
        role_tech_terms = get_tech_terms_for_role(job_role_name)
        
        # Extract keywords from question text
        text_keywords = extractor.extract_from_text(
            question.question_text,
            role_tech_terms=role_tech_terms
        )
        
        # Combine intelligently
        final_keywords = extractor.combine_keywords(
            text_keywords,
            role_tech_terms,
            max_total=10
        )
        
        if verbose:
            print(f"[{i}/{total_questions}] Q{question.question_id}")
            print(f"  Role: {job_role_name}")
            print(f"  Question: {question.question_text[:60]}...")
            print(f"  ❌ Old Keywords: {question.expected_keywords[:5] if question.expected_keywords else []}")
            print(f"  ✅ New Keywords: {final_keywords}")
            print()
        
        # Update question
        if not dry_run:
            question.expected_keywords = final_keywords
            question.save()
            updated_count += 1
        else:
            updated_count += 1
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    if dry_run:
        print(f"✅ Would update: {updated_count} questions")
    else:
        print(f"✅ Updated: {updated_count} questions")
    
    print("\n✨ Done!\n")


def test_improved_extraction():
    """Test improved keyword extraction"""
    extractor = ImprovedKeywordExtractor()
    
    test_cases = [
        ("How do you optimize database queries in Django?", "Python Developer"),
        ("Explain your experience with React hooks", "Frontend Developer"),
        ("Tell me about a time you debugged a production issue", "DevOps Engineer"),
        ("What is your approach to user research?", "UI/UX Designer"),
    ]
    
    print("\n" + "="*80)
    print("TESTING IMPROVED KEYWORD EXTRACTION")
    print("="*80 + "\n")
    
    for question_text, role in test_cases:
        print(f"Question: {question_text}")
        print(f"Role: {role}")
        
        role_terms = get_tech_terms_for_role(role)
        text_keywords = extractor.extract_from_text(question_text, role_terms)
        final_keywords = extractor.combine_keywords(text_keywords, role_terms)
        
        print(f"Extracted: {text_keywords}")
        print(f"✅ Final Keywords: {final_keywords}")
        print("-" * 80)
        print()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Improved keyword population with filtering')
    parser.add_argument('--dry-run', action='store_true', help='Preview without saving')
    parser.add_argument('--test', action='store_true', help='Test extraction')
    parser.add_argument('--quiet', action='store_true', help='Suppress output')
    
    args = parser.parse_args()
    
    if args.test:
        test_improved_extraction()
    else:
        populate_keywords_improved(dry_run=args.dry_run, verbose=not args.quiet)