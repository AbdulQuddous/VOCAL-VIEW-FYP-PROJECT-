from django.core.management.base import BaseCommand
from interviews.models import Question
from interviews.utils.dataset_loader import get_dataset_loader


class Command(BaseCommand):
    help = 'Import questions from JSON to Question table'

    def handle(self, *args, **options):
        loader = get_dataset_loader()
        dataset = loader.load_dataset()

        imported = 0

        for role, questions in dataset.items():
            for q in questions:
                Question.objects.get_or_create(
                    question_text=q['question_text'],
                    defaults={
                        'question_type': q.get('question_type', 'Technical'),
                        'difficulty': q.get('difficulty', 'medium'),
                        'expected_keywords': q.get('keywords', []),
                        'session': None   # optional if null allowed
                    }
                )
                imported += 1

        self.stdout.write(self.style.SUCCESS(f'✅ Imported {imported} questions'))