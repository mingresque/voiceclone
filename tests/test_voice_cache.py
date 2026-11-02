"""Deterministic cache regression tests; no model download or torch install needed."""
from __future__ import annotations

import contextlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tts_core import ChatterboxEngine, voice_fingerprint


class FakeAudio:
    ndim = 2

    def __init__(self, samples=10):
        self.shape = (1, samples)

    def detach(self):
        return self

    def cpu(self):
        return self

    def to(self, _dtype):
        return self


class FakeConditionals:
    loads = 0
    saves = 0

    def __init__(self, identifier):
        self.identifier = identifier

    def save(self, path):
        type(self).saves += 1
        Path(path).write_text(json.dumps({"identifier": self.identifier}), encoding="utf-8")

    @classmethod
    def load(cls, path, map_location="cpu"):
        assert map_location == "cpu"
        cls.loads += 1
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(data["identifier"])

    def to(self, device):
        assert device == "cpu"
        return self


class FakeModel:
    sr = 24000
    all_models = []

    def __init__(self):
        self.conds = None
        self.prepares = []
        self.calls = []
        self.__class__.all_models.append(self)

    @classmethod
    def from_pretrained(cls, device):
        assert device == "cpu"
        return cls()

    def prepare_conditionals(self, wav_fpath, exaggeration=0.5):
        self.prepares.append((wav_fpath, exaggeration))
        self.conds = FakeConditionals(Path(wav_fpath).read_bytes().hex())

    def generate(self, text, audio_prompt_path, cfg_weight, exaggeration):
        assert self.conds is not None
        self.calls.append((text, audio_prompt_path, cfg_weight, exaggeration, self.conds.identifier))
        return FakeAudio()


class VoiceCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.wav = root / "reference.wav"
        self.wav.write_bytes(b"reference voice 1")
        self.out = root / "speech.wav"
        self.cache = root / "voice-cache"
        FakeConditionals.saves = 0
        FakeConditionals.loads = 0
        FakeModel.all_models = []
        torch = types.ModuleType("torch")
        torch.float32 = "float32"
        torch.inference_mode = contextlib.nullcontext
        torch.zeros = lambda shape, dtype: FakeAudio(shape[1])
        torch.cat = lambda pieces, dim: FakeAudio(sum(x.shape[1] for x in pieces))
        audio = types.ModuleType("torchaudio")
        audio.save = lambda path, wav, sr, **kw: Path(path).write_bytes(b"generated")
        chatterbox = types.ModuleType("chatterbox")
        tts = types.ModuleType("chatterbox.tts")
        tts.ChatterboxTTS = FakeModel
        tts.Conditionals = FakeConditionals
        self.modules = mock.patch.dict(sys.modules, {
            "torch": torch, "torchaudio": audio,
            "chatterbox": chatterbox, "chatterbox.tts": tts,
        })
        self.modules.start()
        self.addCleanup(self.modules.stop)

    def test_first_generation_and_multi_chunk_prepare_once(self):
        engine = ChatterboxEngine(self.cache)
        output, n = engine.generate("First line. Second line.", self.wav, self.out)
        model = FakeModel.all_models[0]
        self.assertEqual(n, 2)
        self.assertEqual(output.read_bytes(), b"generated")
        self.assertEqual(len(model.prepares), 1)
        self.assertEqual(len(model.calls), 2)
        self.assertTrue(all(call[1] is None for call in model.calls))
        self.assertEqual(FakeConditionals.saves, 1)
        self.assertEqual(len(list(self.cache.glob("*.pt"))), 1)

    def test_same_reference_again_with_different_settings(self):
        engine = ChatterboxEngine(self.cache)
        engine.generate("Hello", self.wav, self.out)
        engine.generate("Again", self.wav, self.out, cfg=0.8, exaggeration=1.2)
        model = FakeModel.all_models[0]
        self.assertEqual(len(model.prepares), 1)
        self.assertEqual(FakeConditionals.loads, 0)
        self.assertEqual(model.calls[-1][2:4], (0.8, 1.2))
        self.assertIn("memory", engine.last_cache_status)

    def test_restart_restores_cached_voice_without_preparing(self):
        ChatterboxEngine(self.cache).generate("Hello", self.wav, self.out)
        another = ChatterboxEngine(self.cache)
        another.generate("Hello again", self.wav, self.out)
        self.assertEqual(len(FakeModel.all_models), 2)
        self.assertEqual(len(FakeModel.all_models[1].prepares), 0)
        self.assertEqual(FakeConditionals.loads, 1)
        self.assertEqual(FakeConditionals.saves, 1)
        self.assertIn("disk cache", another.last_cache_status)

    def test_modified_wav_invalidates_cache_even_if_same_path(self):
        engine = ChatterboxEngine(self.cache)
        engine.generate("One", self.wav, self.out)
        initial_hash = voice_fingerprint(self.wav)
        self.wav.write_bytes(b"reference voice 2")
        self.assertNotEqual(voice_fingerprint(self.wav), initial_hash)
        engine.generate("Two", self.wav, self.out)
        self.assertEqual(len(FakeModel.all_models[0].prepares), 2)
        self.assertEqual(len(list(self.cache.glob("*.pt"))), 2)

    def test_identical_audio_at_different_path_reuses(self):
        engine = ChatterboxEngine(self.cache)
        engine.generate("One", self.wav, self.out)
        copy = Path(self.tmp.name) / "another-filename.wav"
        copy.write_bytes(self.wav.read_bytes())
        engine.generate("Two", copy, self.out)
        self.assertEqual(len(FakeModel.all_models[0].prepares), 1)

    def test_corrupt_cache_is_rebuilt(self):
        engine = ChatterboxEngine(self.cache)
        engine.generate("One", self.wav, self.out)
        cache_file = next(self.cache.glob("*.pt"))
        cache_file.write_bytes(b"invalid")
        new_engine = ChatterboxEngine(self.cache)
        progress = []
        new_engine.generate("Two", self.wav, self.out, progress=progress.append)
        self.assertEqual(len(FakeModel.all_models[-1].prepares), 1)
        self.assertIn("rebuilding", " ".join(progress))
        self.assertEqual(json.loads(cache_file.read_text())["identifier"], self.wav.read_bytes().hex())

    def test_reference_file_changed_during_processing_is_not_cached(self):
        class MutatingModel(FakeModel):
            def prepare_conditionals(self, wav_fpath, exaggeration=0.5):
                super().prepare_conditionals(wav_fpath, exaggeration)
                Path(wav_fpath).write_bytes(b"changed during extraction")
        engine = ChatterboxEngine(self.cache)
        engine._model = MutatingModel()
        with self.assertRaisesRegex(RuntimeError, "changed"):
            engine.generate("Hello", self.wav, self.out)
        self.assertEqual(list(self.cache.glob("*.pt")), [])


if __name__ == "__main__":
    unittest.main()


class GuiPreferenceTests(unittest.TestCase):
    def test_last_reference_restored_only_while_file_exists(self):
        import app
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wav = root / "friend.wav"
            wav.write_bytes(b"wave")
            settings = root / "runtime" / "gui-settings.json"
            with mock.patch.object(app, "SETTINGS_FILE", settings):
                app.VoiceCloneApp._remember_reference(str(wav))
                self.assertEqual(app.VoiceCloneApp._restore_reference(), str(wav))
                wav.unlink()
                self.assertEqual(app.VoiceCloneApp._restore_reference(), "")
