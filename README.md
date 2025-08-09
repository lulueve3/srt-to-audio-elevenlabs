# SRT to Audio (ElevenLabs)

Convert `.srt` subtitle files into high-quality speech audio using [ElevenLabs API](https://elevenlabs.io/).

## Features
- 🎯 Supports `.srt` subtitle input
- 🗣️ Uses ElevenLabs TTS for natural-sounding voices
- 💾 Resume progress if the process is interrupted

---

## Requirements
- Python 3.12
- ElevenLabs API key ([Get it here](https://elevenlabs.io/app/settings/api-keys))

---

## Installation

# Clone the repository
git clone https://github.com/<your-username>/srt-to-audio-elevenlabs.git
cd srt-to-audio-elevenlabs

# Install dependencies
pip install -r requirements.txt


---

## Usage

1. **Prepare** an `.srt` subtitle file.
2. **Run** the program:
   python srt_to_audio.py
   
4. In the **GUI**:

   * Select your `.srt` file.
   * Enter your **ElevenLabs API Key**.
   * Enter your **Voice ID** (from ElevenLabs voice settings).
   * Enter **Model ID** (default: `eleven_flash_v2_5`).
   * Adjust **Max Speed** if needed.
   * Click **Start Conversion**.
5. Output audio file will be saved as:
   output_audio.mp3 in the same folder as the `.srt`.

---

## Resume Feature

If the process stops unexpectedly:

* Click start again to continue from the last process..

---

