import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tts_core import split_text, validate_request


class CoreTests(unittest.TestCase):
    def test_text_segmentation_keeps_words(self):
        text = "One short sentence. And another sentence. " + "word " * 90
        parts = split_text(text, 100)
        self.assertTrue(parts)
        self.assertTrue(all(len(x) <= 100 for x in parts))
        self.assertEqual(" ".join(parts).split(), text.split())

    def test_empty(self):
        self.assertEqual(split_text(" \n   "), [])

    def test_long_nonbreaking_token(self):
        word = "x" * 666
        parts = split_text(word, 120)
        self.assertEqual("".join(parts), word)
        self.assertLessEqual(max(map(len, parts)), 120)

    def test_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            wav = Path(directory) / 'voice.wav'
            wav.write_bytes(b'dummy')
            target = Path(directory) / 'spoken.wav'
            validate_request('hello', wav, target, .5, .5)
            with self.assertRaisesRegex(ValueError, 'different'):
                validate_request('hello', wav, wav, .5, .5)
            with self.assertRaisesRegex(ValueError, 'CFG'):
                validate_request('hello', wav, target, 1.5, .5)


if __name__ == '__main__':
    unittest.main()
