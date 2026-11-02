"""Check dependency imports without downloading the model weights."""
import torch
import torchaudio
import perth
from chatterbox.tts import ChatterboxTTS

if "+cpu" not in torch.__version__:
    raise RuntimeError(f"CPU-only PyTorch build expected, found: {torch.__version__}")
if perth.PerthImplicitWatermarker is None:
    raise RuntimeError("Perth audio watermarker could not load. Try Repair Setup.cmd.")
print("Chatterbox dependencies loaded; PyTorch:", torch.__version__)
