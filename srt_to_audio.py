import os
import re
import io
import json
import threading
import requests
import srt
from pydub import AudioSegment
from gtts import gTTS

import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from tkinter.scrolledtext import ScrolledText

SETTINGS_FILE = "tts_settings.json"
PARTIAL_NAME = "output_partial.mp3"
PROGRESS_NAME = "progress.txt"
OUTPUT_NAME = "output_audio.mp3"

# ---------------- Settings persistence ----------------
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_settings(data):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log_message(f"⚠️ Failed to save settings: {e}")

settings_cache = load_settings()

# ---------------- Logging helpers ----------------
def log_message(msg):
    log_box.configure(state="normal")
    log_box.insert(tk.END, msg + "\n")
    log_box.see(tk.END)
    log_box.configure(state="disabled")
    root.update_idletasks()
    print(msg)

def set_ui_running(running: bool):
    widgets = [
        start_btn, browse_btn, engine_menu,
        api_entry, voice_entry, model_entry, show_btn,
        gtts_lang_entry, gtts_accent_entry,
        max_entry
    ]
    for w in widgets:
        try:
            w.configure(state=("disabled" if running else "normal"))
        except Exception:
            pass

# ---------------- TTS backends ----------------
def synthesize_elevenlabs(api_key, voice_id, model_id, text, speed=1.0):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
    payload = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True
        }
    }
    if speed != 1.0:
        payload["text"] = f"<speak><prosody rate='{speed*100:.0f}%'>{text}</prosody></speak>"
        payload["ssml"] = True

    headers = {
        "Accept": "audio/mpeg",
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=120)
    if resp.status_code != 200:
        raise Exception(f"ElevenLabs API Error: {resp.status_code} {resp.text}")
    return resp.content  # mp3 bytes

def synthesize_gtts(text, lang="en", accent_tld=""):
    if accent_tld.strip():
        tts = gTTS(text=text, lang=lang, tld=accent_tld.strip())
    else:
        tts = gTTS(text=text, lang=lang)
    temp_path = "_gtts_tmp.mp3"
    tts.save(temp_path)
    with open(temp_path, "rb") as f:
        data = f.read()
    try:
        os.remove(temp_path)
    except Exception:
        pass
    return data  # mp3 bytes

# ---------------- Core processing with resume ----------------
def process_srt(engine, srt_file, max_speed,
                # ElevenLabs
                api_key="", voice_id="", model_id="eleven_flash_v2_5",
                # gTTS
                gtts_lang="en", gtts_accent=""):
    with open(srt_file, "r", encoding="utf-8") as f:
        subs = list(srt.parse(f.read()))

    out_dir = os.path.dirname(srt_file)
    output_file = os.path.join(out_dir, OUTPUT_NAME)
    partial_file = os.path.join(out_dir, PARTIAL_NAME)
    progress_file = os.path.join(out_dir, PROGRESS_NAME)

    if os.path.exists(progress_file):
        with open(progress_file, "r", encoding="utf-8") as pf:
            last_index = int(pf.read().strip() or 0)
    else:
        last_index = 0

    if os.path.exists(partial_file):
        final_audio = AudioSegment.from_file(partial_file, format="mp3")
    else:
        final_audio = AudioSegment.silent(duration=0)

    total = len(subs)
    for idx, sub in enumerate(subs):
        if idx < last_index:
            continue

        start_ms = int(sub.start.total_seconds() * 1000)
        end_ms = int(sub.end.total_seconds() * 1000)
        duration_ms = end_ms - start_ms

        text = sub.content.replace("\n", " ")
        word_count = len(re.findall(r'\w+', text))
        est_read_time = int((word_count / 2.5) * 1000)
        speed = min(max_speed, est_read_time / duration_ms) if est_read_time > duration_ms else 1.0

        log_message(f"▶ [{idx+1}/{total}] {sub.start} → {sub.end} | speed={speed:.2f}")

        if engine == "gtts":
            audio_bytes = synthesize_gtts(text, lang=gtts_lang, accent_tld=gtts_accent)
        elif engine == "elevenlabs":
            audio_bytes = synthesize_elevenlabs(api_key, voice_id, model_id, text, speed)
        else:
            raise Exception(f"Unsupported engine: {engine}")

        seg = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")

        if len(seg) > duration_ms and duration_ms > 0:
            playback_speed = len(seg) / duration_ms
            seg = seg.speedup(playback_speed=playback_speed)

        if start_ms > len(final_audio):
            final_audio += AudioSegment.silent(duration=start_ms - len(final_audio))

        final_audio += seg

        final_audio.export(partial_file, format="mp3")
        with open(progress_file, "w", encoding="utf-8") as pf:
            pf.write(str(idx + 1))

    final_audio.export(output_file, format="mp3")
    log_message(f"🎯 Finished! Saved at: {output_file}")

    if os.path.exists(partial_file): os.remove(partial_file)
    if os.path.exists(progress_file): os.remove(progress_file)

# ---------------- Worker ----------------
def run_worker():
    try:
        srt_file = srt_path.get().strip()
        engine = engine_var.get()  # "gtts" or "elevenlabs"
        try:
            max_speed = float(max_speed_var.get().strip())
        except Exception:
            messagebox.showerror("Error", "Max Speed must be a number.")
            return

        if not os.path.isfile(srt_file):
            messagebox.showerror("Error", "Please select a valid .srt file.")
            return

        if engine == "elevenlabs":
            api_key = api_key_var.get().strip()
            voice_id = voice_var.get().strip()
            model_id = model_var.get().strip()
            if not api_key:
                messagebox.showerror("Error", "Please enter your ElevenLabs API Key.")
                return
            if not voice_id:
                messagebox.showerror("Error", "Please enter a Voice ID.")
                return
            if not model_id:
                messagebox.showerror("Error", "Please enter a Model ID.")
                return
        else:
            api_key = voice_id = model_id = ""  # not used

        gtts_lang = gtts_lang_var.get().strip() or "en"
        gtts_accent = gtts_accent_var.get().strip()

        settings = {
            "last_srt": srt_file,
            "max_speed": max_speed,
            "engine": engine,
            "gtts": {
                "lang": gtts_lang,
                "accent": gtts_accent
            },
            "elevenlabs": {
                "api_key": api_key,
                "voice_id": voice_id,
                "model_id": model_id if engine == "elevenlabs" else model_var.get().strip() or "eleven_flash_v2_5"
            }
        }
        save_settings(settings)

        set_ui_running(True)
        process_srt(
            engine=engine,
            srt_file=srt_file,
            max_speed=max_speed,
            api_key=api_key,
            voice_id=voice_id,
            model_id=model_id if engine == "elevenlabs" else "eleven_flash_v2_5",
            gtts_lang=gtts_lang,
            gtts_accent=gtts_accent
        )

    except Exception as e:
        log_message(f"❌ Error: {e}")
        messagebox.showerror("Error", f"{e}\nProgress was saved (if any). Run again to resume.")
    finally:
        set_ui_running(False)

def start_processing():
    threading.Thread(target=run_worker, daemon=True).start()

def choose_srt():
    file_path = filedialog.askopenfilename(
        title="Select SRT file",
        filetypes=[("SRT Files", "*.srt")]
    )
    if file_path:
        srt_path.set(file_path)

# ---------------- UI ----------------
def toggle_show_api():
    global api_shown
    api_shown = not api_shown
    if api_shown:
        api_entry.configure(show="")
        show_btn.configure(text="Hide")
    else:
        api_entry.configure(show="•")
        show_btn.configure(text="Show")

def on_engine_change(*_):
    if engine_var.get() == "elevenlabs":
        gtts_frame.pack_forget()
        eleven_frame.pack(fill="x", pady=(10,0), after=card_input)
    else:
        eleven_frame.pack_forget()
        gtts_frame.pack(fill="x", pady=(10,0), after=card_input)

root = tk.Tk()
root.title("SRT → Audio (Google TTS / ElevenLabs)")
root.geometry("780x650")
root.minsize(740, 580)

style = ttk.Style()
try:
    style.theme_use("clam")
except Exception:
    pass

container = ttk.Frame(root, padding=16)
container.pack(fill="both", expand=True)

card_input = ttk.LabelFrame(container, text="Source & Settings", padding=12)
card_input.pack(fill="x")

srt_path = tk.StringVar()
engine_var = tk.StringVar(value="gtts")  # default Google TTS (free)

api_key_var = tk.StringVar()
voice_var = tk.StringVar()
model_var = tk.StringVar(value="eleven_flash_v2_5")

gtts_lang_var = tk.StringVar(value="en")
gtts_accent_var = tk.StringVar(value="")

max_speed_var = tk.StringVar(value="1.5")
api_shown = False

# load settings
if settings_cache:
    srt_path.set(settings_cache.get("last_srt", ""))
    max_speed_var.set(str(settings_cache.get("max_speed", 1.5)))
    engine_var.set(settings_cache.get("engine", "gtts"))

    el = settings_cache.get("elevenlabs", {})
    api_key_var.set(el.get("api_key", ""))
    voice_var.set(el.get("voice_id", ""))
    model_var.set(el.get("model_id", "eleven_flash_v2_5"))

    gt = settings_cache.get("gtts", {})
    gtts_lang_var.set(gt.get("lang", "en"))
    gtts_accent_var.set(gt.get("accent", ""))

# row 0: SRT
row = 0
ttk.Label(card_input, text="SRT file:").grid(row=row, column=0, sticky="e", padx=(0,8), pady=4)
srt_entry = ttk.Entry(card_input, textvariable=srt_path, width=58)
srt_entry.grid(row=row, column=1, sticky="we", pady=4)
browse_btn = ttk.Button(card_input, text="Browse...", command=choose_srt)
browse_btn.grid(row=row, column=2, padx=(8,0), pady=4)

# row 1: Engine
row += 1
ttk.Label(card_input, text="Engine:").grid(row=row, column=0, sticky="e", padx=(0,8), pady=4)
engine_menu = ttk.OptionMenu(card_input, engine_var, engine_var.get(), "gtts", "elevenlabs", command=lambda _: on_engine_change())
engine_menu.grid(row=row, column=1, sticky="w", pady=4)

# Configure column weights for proper resizing
card_input.columnconfigure(1, weight=1)

# Frames for engines
gtts_frame = ttk.LabelFrame(container, text="Google Text-to-Speech (Free)", padding=12)

erow = 0
ttk.Label(gtts_frame, text="Language (lang):").grid(row=erow, column=0, sticky="e", padx=(0,8), pady=4)
gtts_lang_entry = ttk.Entry(gtts_frame, textvariable=gtts_lang_var, width=20)
gtts_lang_entry.grid(row=erow, column=1, sticky="w", pady=4)

erow += 1
ttk.Label(gtts_frame, text="Accent (tld, optional):").grid(row=erow, column=0, sticky="e", padx=(0,8), pady=4)
gtts_accent_entry = ttk.Entry(gtts_frame, textvariable=gtts_accent_var, width=20)
gtts_accent_entry.grid(row=erow, column=1, sticky="w", pady=4)

# Create link label for documentation
link_frame = ttk.Frame(gtts_frame)
link_frame.grid(row=erow, column=2, sticky="w", padx=(8,0))
ttk.Label(link_frame, text="Examples: com, com.au, co.uk").pack(side="left")
link_label = ttk.Label(link_frame, text="(docs)", foreground="blue", cursor="hand2")
link_label.pack(side="left", padx=(5,0))

def open_gtts_docs(event):
    import webbrowser
    webbrowser.open("https://gtts.readthedocs.io/en/latest/module.html#localized-accents")

link_label.bind("<Button-1>", open_gtts_docs)

# Configure column weights for gtts_frame
gtts_frame.columnconfigure(1, weight=1)

# ElevenLabs frame
eleven_frame = ttk.LabelFrame(container, text="ElevenLabs (API required)", padding=12)

erow = 0
ttk.Label(eleven_frame, text="API Key:").grid(row=erow, column=0, sticky="e", padx=(0,8), pady=4)
api_entry = ttk.Entry(eleven_frame, textvariable=api_key_var, width=40, show="•")
api_entry.grid(row=erow, column=1, sticky="we", pady=4)
show_btn = ttk.Button(eleven_frame, text="Show", width=8, command=lambda: toggle_show_api())
show_btn.grid(row=erow, column=2, sticky="w", padx=(8,0), pady=4)

erow += 1
ttk.Label(eleven_frame, text="Voice ID:").grid(row=erow, column=0, sticky="e", padx=(0,8), pady=4)
voice_entry = ttk.Entry(eleven_frame, textvariable=voice_var, width=30)
voice_entry.grid(row=erow, column=1, sticky="we", pady=4)

erow += 1
ttk.Label(eleven_frame, text="Model ID:").grid(row=erow, column=0, sticky="e", padx=(0,8), pady=4)
model_entry = ttk.Entry(eleven_frame, textvariable=model_var, width=30)
model_entry.grid(row=erow, column=1, sticky="we", pady=4)

# Configure column weights for eleven_frame
eleven_frame.columnconfigure(1, weight=1)

# Global Max Speed
card_speed = ttk.LabelFrame(container, text="Timing", padding=12)
card_speed.pack(fill="x", pady=(10,0))
ttk.Label(card_speed, text="Max Speed:").grid(row=0, column=0, sticky="e", padx=(0,8), pady=4)
max_entry = ttk.Entry(card_speed, textvariable=max_speed_var, width=10)
max_entry.grid(row=0, column=1, sticky="w", pady=4)

# Actions
actions = ttk.Frame(container)
actions.pack(fill="x", pady=(10,0))
start_btn = ttk.Button(actions, text="Start Conversion", command=start_processing)
start_btn.pack(side="left")

# Log
card_log = ttk.LabelFrame(container, text="Progress", padding=12)
card_log.pack(fill="both", expand=True, pady=(12,0))
log_box = ScrolledText(card_log, height=16, state="disabled", wrap="word")
log_box.pack(fill="both", expand=True)

# Show default frame based on engine
if engine_var.get() == "elevenlabs":
    eleven_frame.pack(fill="x", pady=(10,0), after=card_input)
else:
    gtts_frame.pack(fill="x", pady=(10,0), after=card_input)

# Set up trace for engine change
engine_var.trace_add("write", on_engine_change)

root.mainloop()
