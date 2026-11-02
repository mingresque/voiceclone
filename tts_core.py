"""CPU-only Chatterbox speech synthesis, separated from the Tkinter interface.

No AI packages are imported until a generation request is actually made.
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Callable

MAX_CHUNK = 280


def split_text(text: str, limit: int = MAX_CHUNK) -> list[str]:
    """Break long input into manageable pieces without dropping words.

    Prefer sentence endings; long sentences wrap at word boundaries. The text
    is normalized to single spaces because the TTS model does not preserve
    layout whitespace in spoken output.
    """
    if limit < 20:
        raise ValueError("Chunk size must be at least 20 characters.")
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    parts: list[str] = []
    current = ""
    for sentence in sentences:
        words = sentence.split(" ")
        for word in words:
            if len(word) > limit:
                if current:
                    parts.append(current)
                    current = ""
                # Rare cases: a huge unbroken token (e.g., a very long URL).
                parts.extend(word[i : i + limit] for i in range(0, len(word), limit))
                continue
            if not current:
                current = word
            elif len(current) + 1 + len(word) <= limit:
                current += " " + word
            else:
                parts.append(current)
                current = word
        # Splitting between sentences improves the model's prosody.
        if current and current.endswith((".", "!", "?")):
            parts.append(current)
            current = ""
    if current:
        parts.append(current)
    return parts


def validate_request(text: str, reference: Path, output: Path, cfg: float, exaggeration: float) -> None:
    if not text.strip():
        raise ValueError("Enter text to be spoken.")
    if not reference.is_file() or reference.suffix.lower() != ".wav":
        raise ValueError("Choose an existing reference audio file in WAV format.")
    if output.suffix.lower() != ".wav":
        raise ValueError("The output filename must end in .wav.")
    if reference.resolve() == output.resolve():
        raise ValueError("The output must be different from the reference WAV file.")
    if not 0.0 <= cfg <= 1.0:
        raise ValueError("CFG weight must be between 0 and 1.")
    if not 0.0 <= exaggeration <= 1.5:
        raise ValueError("Exaggeration must be between 0 and 1.5.")


# Increment this if the model/conditioning serialization changes. The app is
# currently pinned to the English chatterbox-tts==0.1.7 in requirements.txt.
VOICE_CACHE_FORMAT = "english-chatterbox-tts-0.1.7-v1"
DEFAULT_CACHE_DIR = Path(__file__).resolve().parent / "runtime" / "voice-cache"


def voice_fingerprint(wav_path: Path) -> str:
    """Hash WAV contents, not filenames or timestamps, to detect replacement."""
    digest = hashlib.sha256()
    with wav_path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class ChatterboxEngine:
    """Reuse a CPU model and per-voice conditioning, including across launches.

    Voice conditioning is extracted once per unique WAV contents and stored in
    runtime/voice-cache. Generation always omits audio_prompt_path so Chatterbox
    does not repeat the reference audio analysis for each text chunk.
    """

    def __init__(self, cache_dir: Path | None = None) -> None:
        self._model = None
        self._active_voice_digest: str | None = None
        self.cache_dir = Path(cache_dir) if cache_dir is not None else DEFAULT_CACHE_DIR
        self.last_cache_status = ""

    def _ensure_voice(self, reference: Path, model, conditionals_type, report) -> None:
        digest = voice_fingerprint(reference)
        if self._active_voice_digest == digest and model.conds is not None:
            self.last_cache_status = "voice reused from memory"
            report("Using previously prepared voice (no WAV reprocessing).")
            return

        cache_path = self.cache_dir / f"{VOICE_CACHE_FORMAT}-{digest}.pt"
        if cache_path.is_file():
            report("Loading saved voice profile (skipping WAV processing)...")
            try:
                # Upstream Conditionals.load uses torch.load(weights_only=True).
                model.conds = conditionals_type.load(cache_path, map_location="cpu").to("cpu")
            except Exception as error:
                # A corrupt or incompatible cache should not prevent synthesis.
                report(f"Saved voice profile unusable ({type(error).__name__}); rebuilding it...")
                try:
                    cache_path.unlink()
                except OSError:
                    pass
            else:
                self._active_voice_digest = digest
                self.last_cache_status = "voice loaded from disk cache"
                return

        report("Processing reference WAV (once for this voice)...")
        # The original model's emotion setting can be adjusted during generate()
        # without extracting the voice again; keep the persisted cache neutral.
        model.conds = None
        model.prepare_conditionals(str(reference), exaggeration=0.5)
        if voice_fingerprint(reference) != digest:
            # Do not save a profile for a WAV that changed during preparation.
            model.conds = None
            self._active_voice_digest = None
            raise RuntimeError("The reference WAV changed while being processed. Please retry.")

        self._active_voice_digest = digest
        self.last_cache_status = "voice prepared for this session"
        temp_path = cache_path.with_name(f"{cache_path.name}.{os.getpid()}.tmp")
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            # Save atomically, so crashes cannot leave half-written cache files.
            model.conds.save(temp_path)
            os.replace(temp_path, cache_path)
        except Exception as error:
            # Cache write failures are non-fatal: keep reusing it in memory.
            report(f"Voice ready; could not save disk cache ({error}).")
        else:
            self.last_cache_status = "new voice profile saved to cache"
            report("Reference voice prepared and cached for future launches.")
        finally:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass

    def generate(
        self,
        text: str,
        reference: Path,
        output: Path,
        cfg: float = 0.5,
        exaggeration: float = 0.5,
        progress: Callable[[str], None] | None = None,
    ) -> tuple[Path, int]:
        validate_request(text, reference, output, cfg, exaggeration)
        report = progress or (lambda _message: None)
        chunks = split_text(text)
        if not chunks:
            raise ValueError("Enter text to be spoken.")

        report("Loading Chatterbox on CPU. First use downloads the AI model...")
        import torch
        import torchaudio as ta
        from chatterbox.tts import ChatterboxTTS, Conditionals

        if self._model is None:
            self._model = ChatterboxTTS.from_pretrained(device="cpu")
        model = self._model
        pieces = []
        silence = torch.zeros((1, int(model.sr * 0.24)), dtype=torch.float32)
        with torch.inference_mode():
            self._ensure_voice(reference, model, Conditionals, report)
            for index, chunk in enumerate(chunks, 1):
                report(f"Generating speech segment {index} of {len(chunks)} (CPU)...")
                wav = model.generate(
                    chunk,
                    audio_prompt_path=None,  # critical: reuse preprocessed conditionals
                    cfg_weight=cfg,
                    exaggeration=exaggeration,
                )
                if wav.ndim == 1:
                    wav = wav.unsqueeze(0)
                wav = wav.detach().cpu().to(torch.float32)
                if wav.shape[0] != 1 or wav.shape[1] == 0:
                    raise RuntimeError("Unexpected audio shape returned by the TTS model.")
                if pieces:
                    pieces.append(silence)
                pieces.append(wav)
        result = torch.cat(pieces, dim=1)
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_name(output.stem + ".partial.wav")
        try:
            report("Saving WAV file...")
            ta.save(str(temp), result, model.sr, encoding="PCM_S", bits_per_sample=16, backend="soundfile")
            os.replace(temp, output)
        finally:
            if temp.exists():
                temp.unlink()
        return output, len(chunks)
