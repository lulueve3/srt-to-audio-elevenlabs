import os
import re
import io
import json
import threading
import requests
import srt
from pydub import AudioSegment

import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from tkinter.scrolledtext import ScrolledText

SETTINGS_FILE = "tts_settings.json"
PARTIAL_NAME = "output_partial.mp3"
PROGRESS_NAME = "progress.txt"
OUTPUT_NAME = "output_audio.mp3"

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

def log_message(msg):
    log_box.configure(state="normal")
    log_box.insert(tk.END, msg + "\n")
    log_box.see(tk.END)
    log_box.configure(state="disabled")
    root.update_idletasks()
    print(msg)

def set_ui_running(running: bool):
    for w in (start_btn, browse_btn, api_entry, voice_entry, model_entry, max_entry, show_btn):
        w.configure(state=("disabled" if running else "normal"))

def toggle_show_api():
    global api_shown
    api_shown = not api_shown
    if api_shown:
        api_entry.configure(show="")
        show_btn.configure(text="Hide")
    else:
        api_entry.configure(show="•")
        show_btn.configure(text="Show")

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
    return resp.content

def process_srt(srt_file, api_key, voice_id, model_id, max_speed):
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
        audio_bytes = synthesize_elevenlabs(api_key, voice_id, model_id, text, speed)

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

def run_worker():
    try:
        srt_file = srt_path.get().strip()
        api_key = api_key_var.get().strip()
        voice_id = voice_var.get().strip()
        model_id = model_var.get().strip()
        try:
            max_speed = float(max_speed_var.get().strip())
        except Exception:
            messagebox.showerror("Error", "Max Speed must be a number.")
            return

        if not os.path.isfile(srt_file):
            messagebox.showerror("Error", "Please select a valid .srt file.")
            return
        if not api_key:
            messagebox.showerror("Error", "Please enter your ElevenLabs API Key.")
            return
        if not voice_id:
            messagebox.showerror("Error", "Please enter a Voice ID.")
            return
        if not model_id:
            messagebox.showerror("Error", "Please enter a Model ID.")
            return

        settings = {
            "last_srt": srt_file,
            "max_speed": max_speed,
            "elevenlabs": {
                "api_key": api_key,
                "voice_id": voice_id,
                "model_id": model_id
            }
        }
        save_settings(settings)

        set_ui_running(True)
        process_srt(srt_file, api_key, voice_id, model_id, max_speed)

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

root = tk.Tk()
root.title("SRT → Audio (ElevenLabs)")
root.geometry("740x600")
root.minsize(700, 520)

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
api_key_var = tk.StringVar()
voice_var = tk.StringVar()
model_var = tk.StringVar(value="eleven_flash_v2_5")
max_speed_var = tk.StringVar(value="1.5")
api_shown = False

if settings_cache:
    srt_path.set(settings_cache.get("last_srt", ""))
    max_speed_var.set(str(settings_cache.get("max_speed", 1.5)))
    el = settings_cache.get("elevenlabs", {})
    api_key_var.set(el.get("api_key", ""))
    voice_var.set(el.get("voice_id", ""))
    model_var.set(el.get("model_id", "eleven_flash_v2_5"))

row = 0
ttk.Label(card_input, text="SRT file:").grid(row=row, column=0, sticky="e", padx=(0,8), pady=4)
srt_entry = ttk.Entry(card_input, textvariable=srt_path, width=54)
srt_entry.grid(row=row, column=1, sticky="we", pady=4)
browse_btn = ttk.Button(card_input, text="Browse...", command=choose_srt)
browse_btn.grid(row=row, column=2, padx=(8,0), pady=4)

row += 1
ttk.Label(card_input, text="API Key:").grid(row=row, column=0, sticky="e", padx=(0,8), pady=4)
api_entry = ttk.Entry(card_input, textvariable=api_key_var, width=40, show="•")
api_entry.grid(row=row, column=1, sticky="w", pady=4)
show_btn = ttk.Button(card_input, text="Show", width=8, command=toggle_show_api)
show_btn.grid(row=row, column=2, sticky="w", pady=4)

row += 1
ttk.Label(card_input, text="Voice ID:").grid(row=row, column=0, sticky="e", padx=(0,8), pady=4)
voice_entry = ttk.Entry(card_input, textvariable=voice_var, width=30)
voice_entry.grid(row=row, column=1, sticky="w", pady=4)

row += 1
ttk.Label(card_input, text="Model ID:").grid(row=row, column=0, sticky="e", padx=(0,8), pady=4)
model_entry = ttk.Entry(card_input, textvariable=model_var, width=30)
model_entry.grid(row=row, column=1, sticky="w", pady=4)

row += 1
ttk.Label(card_input, text="Max Speed:").grid(row=row, column=0, sticky="e", padx=(0,8), pady=4)
max_entry = ttk.Entry(card_input, textvariable=max_speed_var, width=10)
max_entry.grid(row=row, column=1, sticky="w", pady=4)

for c in range(3):
    card_input.grid_columnconfigure(c, weight=1 if c == 1 else 0)

actions = ttk.Frame(container)
actions.pack(fill="x", pady=(10,0))
start_btn = ttk.Button(actions, text="Start Conversion", command=start_processing)
start_btn.pack(side="left")

card_log = ttk.LabelFrame(container, text="Progress", padding=12)
card_log.pack(fill="both", expand=True, pady=(12,0))

log_box = ScrolledText(card_log, height=16, state="disabled", wrap="word")
log_box.pack(fill="both", expand=True)

root.mainloop()
