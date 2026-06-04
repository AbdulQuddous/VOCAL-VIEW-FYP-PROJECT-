from interviews.utils.dataset_loader import get_dataset_loader
import logging
from typing import List, Dict
logger = logging.getLogger(__name__)


class QuestionGenerator:
    
    def __init__(self):
        self.loader = get_dataset_loader()
        logger.info("QuestionGenerator initialized (dataset mode)")
    
    def generate_questions(
        self,
        role_name: str,
        difficulty: str,
        count: int = 5
    ) -> List[Dict]:
        try:
            logger.info(f"Generating {count} {difficulty} questions for {role_name}")
            
            # Get questions from dataset
            questions = self.loader.get_questions(
                role_name=role_name,
                difficulty=difficulty,
                count=count
            )
            
            if not questions:
                logger.error(f"No questions found for {role_name} ({difficulty})")
                return []
            
            # Validate and format
            validated_questions = self._validate_questions(questions)
            
            logger.info(f"Generated {len(validated_questions)} questions")
            
            return validated_questions
            
        except Exception as e:
            logger.error(f"Question generation failed: {e}")
            return []
    
    def _validate_questions(self, questions: List[Dict]) -> List[Dict]:
        """Validate question structure"""
        validated = []
        
        for q in questions:
            # Ensure required fields
            if not all(k in q for k in ['question_text', 'keywords']):
                logger.warning(f"Invalid question format: {q}")
                continue
            
            # Add defaults
            if 'expected_answer' not in q:
                q['expected_answer'] = ""
            
            if 'difficulty' not in q:
                q['difficulty'] = 'medium'
            
            validated.append(q)
        
        return validated
    
    def get_available_roles(self) -> List[str]:
        """Get list of available roles in dataset"""
        dataset = self.loader.load_dataset()
        return list(dataset.keys())
    
    def get_question_count(self, role_name: str, difficulty: str = None) -> int:
        """Get count of available questions"""
        questions = self.loader.get_questions(
            role_name=role_name,
            difficulty=difficulty,
            count=9999  # Get all
        )
        return len(questions)


# Singleton
_generator = None

def get_question_generator() -> QuestionGenerator:
    """Get singleton question generator"""
    global _generator
    if _generator is None:
        _generator = QuestionGenerator()
    return _generator