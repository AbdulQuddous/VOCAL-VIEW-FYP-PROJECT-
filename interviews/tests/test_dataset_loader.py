# interviews/tests/test_dataset_loader.py

from django.test import SimpleTestCase
from interviews.utils.dataset_loader import get_dataset_loader


class DatasetLoaderTest(SimpleTestCase):

    def setUp(self):
        self.loader = get_dataset_loader()

    def test_load_dataset(self):
        """Test dataset loading"""
        dataset = self.loader.load_dataset()

        self.assertIsInstance(dataset, dict)
        self.assertIn('software_engineer', dataset)
        self.assertGreater(len(dataset['software_engineer']), 0)

    def test_get_questions(self):
        """Test question filtering"""
        questions = self.loader.get_questions(
            role_name='software engineer',
            difficulty='medium',
            count=5
        )

        # dataset-based system = flexible length
        self.assertIsInstance(questions, list)
        self.assertGreater(len(questions), 0)
        self.assertLessEqual(len(questions), 5)

        for q in questions:
            self.assertIn('question_text', q)
            self.assertIn('keywords', q)
            self.assertIsInstance(q['keywords'], list)

    def test_difficulty_filtering(self):
        """Test difficulty filtering works correctly"""
        questions = self.loader.get_questions(
            role_name='software engineer',
            difficulty='easy',
            count=10
        )

        for q in questions:
            self.assertEqual(q['difficulty'].lower(), 'easy')