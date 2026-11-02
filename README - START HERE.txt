VOICECLONE STUDIO — WINDOWS 11 PORTABLE, CPU + VOICE CACHE EDITION
===================================================

WHAT IT DOES
------------
Converts typed English text into WAV speech that resembles a reference WAV
recording. The app uses the same ChatterboxTTS.from_pretrained(device="cpu")
model and the same cfg_weight and exaggeration defaults as the supplied script.

QUICK START FOR YOUR FRIEND
---------------------------
1. Use a Windows 11 x64 laptop or desktop. Make sure you have internet access,
   generous free storage (at least 10 GB recommended), and ideally 16 GB RAM.
2. Extract the ENTIRE ZIP into a normal folder, such as Downloads or Desktop.
   Do NOT double-click the CMD file while it is still inside the ZIP preview.
3. Double-click "Start VoiceClone.cmd".
4. On the first launch, a setup window will download a private Python 3.11
   runtime, CPU-only PyTorch, and the Chatterbox libraries. This does NOT
   require installing Python yourself or administrator permissions. The window
   may be busy for a while depending on internet speed and hardware.
5. When the VoiceClone Studio GUI appears:
   - Type or paste the words to be spoken.
   - Click "Choose WAV..." and select YOUR OWN reference audio file.
     The app remembers the last selected WAV for future launches.
   - Choose the output WAV filename (or leave the suggested filename).
   - Optionally adjust Exaggeration and CFG weight (both default to 0.50).
   - Click "Generate Speech". The first generation downloads the AI MODEL.
     The reference WAV is also processed into a reusable voice profile ONCE.
   - Use "Play WAV" or "Open Output Folder" once generation finishes.
6. For later use, double-click "Start VoiceClone.cmd" again. The model and
   dependencies remain cached INSIDE the app folder and normally need no new
   downloads. The selected voice is restored when its WAV file still exists,
   and the previously processed voice profile is loaded from disk.

AUTOMATIC VOICE CACHING (NEW)
-----------------------------
- The first time a reference WAV is used, Chatterbox extracts its voice
  conditioning data and saves it in runtime\voice-cache\*.pt.
- Subsequent segments in the same generation, and later generations with the
  same WAV, reuse this data without analyzing the WAV again.
- Even after closing the program, the voice profile loads automatically from
  the cache when the same WAV is selected; the GUI remembers the last selected
  sample while its path remains valid.
- If the WAV contents change (even without changing its filename), the app
  detects the difference and builds a NEW voice profile automatically.
- If two WAV files have identical contents, they share the same voice profile.
- Moving/deleting the original WAV: the saved profile remains on disk, but
  the GUI still requires you to select an existing WAV before generating.
- CFG weight and exaggeration remain adjustable without reprocessing the WAV.
- If a cache entry is damaged or incompatible, it is rebuilt automatically.
- The cache is tied to the pinned English chatterbox-tts 0.1.7 format. If you
  update Chatterbox yourself, old cache entries may require clearing.
- To remove cached voice profiles, close the app and delete the contents of
  runtime\voice-cache. No original WAV files are copied into the cache.
- Caching avoids repeated voice analysis, NOT the CPU-intensive speech
  synthesis stage. Do not expect all generation time to disappear.

UPGRADING AN EARLIER VOICECLONE STUDIO FOLDER
--------------------------------------------
If you already have an installed/extracted original version, you can merge
this updated ZIP's VoiceClone-Windows11-Portable folder into it and approve
replacement of the files. Do NOT delete the existing runtime folder; it holds
previously downloaded Python packages and model weights. The first run after
this update will build a voice profile for the WAV you select. If you are
starting fresh, simply extract everything and follow the Quick Start above.

IMPORTANT
---------
- This is a portable FIRST-RUN BOOTSTRAP package, not a fully prebuilt EXE.
  The first launch REQUIRES internet and downloads several GB of dependencies
  and model weights into this folder. There is no dependency on a separately
  installed Python. After all files are downloaded, generation can work offline.
- CPU synthesis is much slower than using an NVIDIA GPU, especially with long
  text. The GUI stays responsive and displays the segment currently processing.
- Use a clean WAV sample of a voice you are authorized to clone. The app does
  not include, copy, or distribute anybody else's voice sample.
- Original reference WAV is read-only; the generated output is saved separately.
- Enter only English text for this model. It is NOT the multilingual variant.
- For long paragraphs the app generates several shorter segments and joins
  them with small pauses, giving more predictable speech than one huge prompt.
- The speech model may add an imperceptible audio watermark, as supplied by
  the upstream Chatterbox implementation.
- Avoid extracting this app inside Program Files, a synced folder, or a path
  that Windows blocks from writing. Keep the whole folder together.
- This build targets Windows 11 x64. Windows on ARM is not supported.
- It has not been tested on a live Windows 11 machine here; setup compatibility
  depends on external packages and model downloads being available.

TROUBLESHOOTING
---------------
- Initial download failed: confirm internet access and available disk space.
  Double-click "Repair Setup.cmd" to re-create the local Python environment.
- Generation failed: see logs\generation-errors.log. Setup errors are logged
  under logs\setup.log. The UI shows the immediate error message as well.
- Double-clicking the launcher opens and immediately closes a window:
  launch it from a regular Windows Command Prompt so you can see messages, or
  inspect setup.log. Windows security software may block downloaded scripts.
- No audio plays: open the saved WAV directly in Windows Media Player.
- Model download errors: check that huggingface.co is reachable. The model
  cache is stored under runtime\huggingface.
- Moving the app folder after setup triggers a rebuild of the private Python
  environment on the next launch. The bundled models/cache are retained.
- To completely uninstall, delete the extracted folder and its runtime folder.

WHAT IS IN THIS ZIP
-------------------
Start VoiceClone.cmd    Double-click entry point
Repair Setup.cmd       Reinstall/repair dependencies
setup_and_launch.ps1   Automates downloads and portable runtime setup
app.py                 Tkinter interface
tts_core.py            Chatterbox CPU generation + persistent WAV profile cache
requirements.txt       App dependencies
overrides.txt         Use PyPI Perth wheel in place of Git source
outputs\                Default location for generated WAV files
runtime\voice-cache\   Created automatically for processed voice profiles

UPSTREAM SOFTWARE
-----------------
Chatterbox TTS by Resemble AI: https://github.com/resemble-ai/chatterbox
  License: MIT (see upstream repository for terms)
PyTorch: https://pytorch.org/
uv: https://github.com/astral-sh/uv
Python 3.11: https://www.python.org/
Chatterbox pretrained model: https://huggingface.co/ResembleAI/chatterbox

These are third-party projects. Their binaries/dependencies are downloaded by
this package on the recipient machine and retain their respective licenses.
