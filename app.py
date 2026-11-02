"""VoiceClone Studio: user-friendly Windows 11 desktop app for Chatterbox TTS."""
from __future__ import annotations

import json
import os
import queue
import sys
import threading
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from tts_core import ChatterboxEngine, validate_request

APP_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = APP_DIR / "outputs"
SETTINGS_FILE = APP_DIR / "runtime" / "gui-settings.json"
BG = "#f4f6fa"
INK = "#192437"
MUTED = "#546174"
ACCENT = "#265bd6"
WHITE = "#ffffff"


class VoiceCloneApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("VoiceClone Studio — CPU Edition")
        self.geometry("860x740")
        self.minsize(730, 610)
        self.configure(bg=BG)
        self.engine = ChatterboxEngine()
        self.events: queue.Queue[tuple] = queue.Queue()
        self.is_busy = False
        self.last_output: Path | None = None
        self.reference_path = tk.StringVar(value=self._restore_reference())
        self.output_path = tk.StringVar(value=self._new_output_name())
        self.cfg = tk.DoubleVar(value=0.5)
        self.exaggeration = tk.DoubleVar(value=0.5)
        self.status = tk.StringVar(value="Ready. Choose a voice sample, enter text, and generate.")
        self.counter = tk.StringVar(value="0 characters")

        self._create_ui()
        self.after(180, self._drain_events)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    @staticmethod
    def _restore_reference() -> str:
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            location = Path(data.get("last_reference_wav", ""))
            if location.is_file() and location.suffix.lower() == ".wav":
                return str(location)
        except (ValueError, OSError, TypeError):
            pass
        return ""

    @staticmethod
    def _remember_reference(path: str) -> None:
        try:
            SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            temp = SETTINGS_FILE.with_suffix(".tmp")
            temp.write_text(json.dumps({"last_reference_wav": path}), encoding="utf-8")
            os.replace(temp, SETTINGS_FILE)
        except OSError:
            pass  # A read-only folder should not prevent speech generation.

    @staticmethod
    def _new_output_name() -> str:
        return str(OUTPUT_DIR / f"speech_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav")

    def _label(self, parent, text, *, bold=False):
        return tk.Label(parent, text=text, bg=WHITE, fg=INK if bold else MUTED,
                        anchor="w", font=("Segoe UI", 11, "bold" if bold else "normal"))

    def _create_ui(self) -> None:
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Primary.TButton", font=("Segoe UI", 11, "bold"), padding=(22, 11))
        style.configure("Secondary.TButton", font=("Segoe UI", 10), padding=(10, 7))
        style.configure("TEntry", padding=(6, 6))
        style.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor="#dde5f3")

        wrapper = tk.Frame(self, bg=BG, padx=25, pady=20)
        wrapper.pack(fill="both", expand=True)
        tk.Label(wrapper, text="VoiceClone Studio", bg=BG, fg=INK,
                 font=("Segoe UI", 24, "bold"), anchor="w").pack(fill="x")
        tk.Label(wrapper, text="Create English speech using a WAV reference voice  •  CPU only",
                 bg=BG, fg=MUTED, font=("Segoe UI", 10), anchor="w").pack(fill="x", pady=(1, 16))

        panel = tk.Frame(wrapper, bg=WHITE, padx=18, pady=16,
                         highlightthickness=1, highlightbackground="#dae0ea")
        panel.pack(fill="both", expand=True)
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        heading_row = tk.Frame(panel, bg=WHITE)
        heading_row.grid(row=0, column=0, sticky="ew")
        self._label(heading_row, "Text to speak", bold=True).pack(side="left")
        tk.Label(heading_row, textvariable=self.counter, bg=WHITE, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="right")

        self.text_entry = scrolledtext.ScrolledText(
            panel, wrap=tk.WORD, undo=True, height=9, font=("Segoe UI", 11),
            relief="solid", borderwidth=1, padx=10, pady=10,
            bg="#fbfcff", fg=INK, insertbackground=INK,
        )
        self.text_entry.grid(row=1, column=0, sticky="nsew", pady=(6, 13))
        self.text_entry.bind("<KeyRelease>", self._update_counter)
        self.text_entry.bind("<<Paste>>", lambda _event: self.after(30, self._update_counter))
        self.text_entry.insert("1.0", "Hello! This is a voice-cloning demonstration.")
        self._update_counter()

        self._label(panel, "Reference voice WAV", bold=True).grid(row=2, column=0, sticky="w")
        ref_row = tk.Frame(panel, bg=WHITE)
        ref_row.grid(row=3, column=0, sticky="ew", pady=(6, 14))
        ref_row.grid_columnconfigure(0, weight=1)
        ttk.Entry(ref_row, textvariable=self.reference_path, state="readonly").grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.choose_voice_button = ttk.Button(ref_row, text="Choose WAV...", command=self._choose_reference,
                                               style="Secondary.TButton")
        self.choose_voice_button.grid(row=0, column=1)
        tk.Label(panel, text="Your reference WAV is processed once, then cached for faster reuse (including after restarting the app).",
                 bg=WHITE, fg=MUTED, font=("Segoe UI", 9), anchor="w", wraplength=720, justify="left").grid(
                     row=4, column=0, sticky="w", pady=(0, 13))

        self._label(panel, "Output WAV file", bold=True).grid(row=5, column=0, sticky="w")
        out_row = tk.Frame(panel, bg=WHITE)
        out_row.grid(row=6, column=0, sticky="ew", pady=(6, 14))
        out_row.grid_columnconfigure(0, weight=1)
        ttk.Entry(out_row, textvariable=self.output_path).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.choose_output_button = ttk.Button(out_row, text="Save as...", command=self._choose_output,
                                                style="Secondary.TButton")
        self.choose_output_button.grid(row=0, column=1)

        self._label(panel, "Voice controls", bold=True).grid(row=7, column=0, sticky="w")
        scales = tk.Frame(panel, bg=WHITE)
        scales.grid(row=8, column=0, sticky="ew", pady=(5, 12))
        scales.grid_columnconfigure(1, weight=1)
        self._add_slider(scales, 0, "Exaggeration", self.exaggeration, 1.5,
                         "Higher = stronger expression")
        self._add_slider(scales, 1, "CFG weight", self.cfg, 1.0,
                         "Lower values may help a fast reference voice")
        bottom = tk.Frame(panel, bg=WHITE)
        bottom.grid(row=9, column=0, sticky="ew")
        ttk.Button(bottom, text="Reset controls", command=self._reset_controls,
                   style="Secondary.TButton").pack(side="left")
        tk.Label(bottom, text="Default: 0.50 for both", bg=WHITE, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=10)

        actions = tk.Frame(wrapper, bg=BG)
        actions.pack(fill="x", pady=(14, 8))
        self.generate_button = ttk.Button(actions, text="Generate Speech", command=self._generate,
                                          style="Primary.TButton")
        self.generate_button.pack(side="left")
        self.play_button = ttk.Button(actions, text="Play WAV", command=self._play_audio,
                                      style="Secondary.TButton", state="disabled")
        self.play_button.pack(side="left", padx=(9, 0))
        self.folder_button = ttk.Button(actions, text="Open Output Folder", command=self._open_folder,
                                        style="Secondary.TButton")
        self.folder_button.pack(side="left", padx=(9, 0))
        self.progressbar = ttk.Progressbar(wrapper, mode="indeterminate")
        self.progressbar.pack(fill="x", pady=(2, 8))
        tk.Label(wrapper, textvariable=self.status, bg=BG, fg=MUTED,
                 font=("Segoe UI", 10), anchor="w", justify="left", wraplength=790).pack(fill="x")

    def _add_slider(self, parent, row, label, variable, maximum, description) -> None:
        tk.Label(parent, text=label, font=("Segoe UI", 10), bg=WHITE,
                 fg=INK, width=16, anchor="w").grid(row=row, column=0, sticky="w")
        tk.Scale(parent, from_=0, to=maximum, resolution=0.05, orient="horizontal", variable=variable,
                 showvalue=False, bg=WHITE, fg=INK, activebackground=ACCENT,
                 highlightthickness=0, sliderlength=20).grid(row=row, column=1, sticky="ew", padx=(7, 6))
        value_label = tk.Label(parent, bg=WHITE, fg=INK, width=5, font=("Segoe UI", 10))
        value_label.grid(row=row, column=2)
        variable.trace_add("write", lambda *_args, v=variable, w=value_label: w.configure(text=f"{v.get():.2f}"))
        value_label.configure(text=f"{variable.get():.2f}")
        tk.Label(parent, text=description, font=("Segoe UI", 8), bg=WHITE,
                 fg=MUTED).grid(row=row, column=3, sticky="w", padx=(9, 0))

    def _update_counter(self, _event=None) -> None:
        size = len(self.text_entry.get("1.0", "end-1c"))
        self.counter.set(f"{size:,} characters")

    def _choose_reference(self) -> None:
        path = filedialog.askopenfilename(title="Choose a reference voice", filetypes=[("WAV audio", "*.wav"), ("All files", "*.*")])
        if path:
            self.reference_path.set(path)
            self._remember_reference(path)
            self.status.set("Reference selected. A saved voice profile will be reused when available.")

    def _choose_output(self) -> None:
        path = filedialog.asksaveasfilename(title="Save generated speech", defaultextension=".wav",
                                            filetypes=[("WAV audio", "*.wav")], initialfile=Path(self.output_path.get()).name,
                                            initialdir=str(Path(self.output_path.get()).parent))
        if path:
            self.output_path.set(path)

    def _reset_controls(self) -> None:
        self.exaggeration.set(0.5)
        self.cfg.set(0.5)

    def _generate(self) -> None:
        if self.is_busy:
            return
        text = self.text_entry.get("1.0", "end-1c")
        voice = Path(self.reference_path.get()) if self.reference_path.get() else Path(".")
        raw_output = self.output_path.get().strip()
        if not raw_output:
            messagebox.showerror("Missing output", "Select an output WAV filename.")
            return
        output = Path(raw_output).expanduser().absolute()
        try:
            validate_request(text, voice, output, self.cfg.get(), self.exaggeration.get())
        except (ValueError, OSError) as error:
            messagebox.showerror("Check the inputs", str(error))
            return
        if output.exists() and not messagebox.askyesno("Overwrite WAV?", f"Replace the existing file?\n\n{output}"):
            return
        self.is_busy = True
        self.generate_button.configure(state="disabled")
        self.choose_voice_button.configure(state="disabled")
        self.choose_output_button.configure(state="disabled")
        self.play_button.configure(state="disabled")
        self.progressbar.start(12)
        self.status.set("Preparing generation...")
        settings = (text, voice, output, float(self.cfg.get()), float(self.exaggeration.get()))
        threading.Thread(target=self._background_generate, args=settings, daemon=True).start()

    def _background_generate(self, text, voice, output, cfg, exaggeration):
        try:
            path, chunk_count = self.engine.generate(
                text=text, reference=voice, output=output,
                cfg=cfg, exaggeration=exaggeration,
                progress=lambda message: self.events.put(("progress", message)),
            )
            self.events.put(("done", path, chunk_count))
        except Exception as exc:
            import traceback
            log_dir = APP_DIR / "logs"
            try:
                log_dir.mkdir(exist_ok=True)
                with (log_dir / "generation-errors.log").open("a", encoding="utf-8") as f:
                    f.write(f"\n[{datetime.now().isoformat(timespec='seconds')}]\n{traceback.format_exc()}\n")
            except OSError:
                pass
            self.events.put(("error", str(exc)))

    def _drain_events(self):
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            if event[0] == "progress":
                self.status.set(event[1])
            elif event[0] == "done":
                _, path, count = event
                self.last_output = path
                self._finish()
                self.status.set(f"Saved {path.name}  •  {count} segment(s)  •  {self.engine.last_cache_status}")
                self.play_button.configure(state="normal")
                messagebox.showinfo("Audio created", f"Generated WAV saved to:\n{path}")
            elif event[0] == "error":
                self._finish()
                self.status.set("Generation failed. See logs/generation-errors.log for details.")
                messagebox.showerror("Speech generation failed", event[1] + "\n\nSee logs/generation-errors.log for details.")
        self.after(180, self._drain_events)

    def _finish(self):
        self.is_busy = False
        self.progressbar.stop()
        self.generate_button.configure(state="normal")
        self.choose_voice_button.configure(state="normal")
        self.choose_output_button.configure(state="normal")

    def _play_audio(self):
        if not self.last_output or not self.last_output.exists():
            messagebox.showwarning("File missing", "Generate a WAV file first.")
            return
        try:
            if sys.platform == "win32":
                import winsound
                winsound.PlaySound(str(self.last_output), winsound.SND_FILENAME | winsound.SND_ASYNC)
            else:
                messagebox.showinfo("Windows only", "In Windows 11 this button plays the generated WAV.")
        except Exception as error:
            messagebox.showerror("Playback problem", f"Could not play WAV: {error}")

    def _open_folder(self):
        try:
            folder = self.last_output.parent if self.last_output else Path(self.output_path.get()).parent
            folder.mkdir(parents=True, exist_ok=True)
            if sys.platform == "win32":
                os.startfile(str(folder))
            else:
                messagebox.showinfo("Folder", str(folder))
        except Exception as error:
            messagebox.showerror("Cannot open folder", str(error))

    def _on_close(self):
        if self.is_busy and not messagebox.askyesno("Generation in progress", "Closing now will interrupt speech generation. Close anyway?"):
            return
        if sys.platform == "win32":
            try:
                import winsound
                winsound.PlaySound(None, 0)
            except RuntimeError:
                pass
        self.destroy()


if __name__ == "__main__":
    VoiceCloneApp().mainloop()
