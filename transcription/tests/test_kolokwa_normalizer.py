from django.test import SimpleTestCase

from transcription.services.kolokwa_normalizer import normalize


class KolokwaNormalizerTests(SimpleTestCase):
    def test_basic_phrases(self):
        self.assertEqual(normalize("I na know"), "I do not know")
        self.assertEqual(normalize("I now know"), "I don't know")
        self.assertEqual(normalize("I na there"), "I am not there")
        self.assertEqual(normalize("I alright"), "I am okay")

    def test_short_tokens(self):
        self.assertEqual(normalize("da one"), "That one")
        self.assertEqual(normalize("dis one"), "This one")
        self.assertEqual(normalize("wat time"), "What time")
        self.assertEqual(normalize("wetin happen"), "What happen")

    def test_boundaries(self):
        # Ensure short tokens don't match inside other words
        self.assertEqual(normalize("koala"), "Koala")
        self.assertEqual(normalize("people"), "People")
