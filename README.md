# SRT to Audio (ElevenLabs)

Convert `.srt` subtitle files into high-quality speech audio using [ElevenLabs API](https://elevenlabs.io/).

<img width="927" height="790" alt="w4exgFQHEt" src="https://github.com/user-attachments/assets/5e99a53e-629b-4dd6-9707-4b9783336c0d" />




## Features
- 🎯 Supports `.srt` subtitle input
- 🗣️ Uses ElevenLabs TTS for natural-sounding voices
- 💾 Resume progress if the process is interrupted

---

## Requirements
- Python 3.12
- ElevenLabs API key ([Get it here](https://elevenlabs.io/app/settings/api-keys)) 10k credits/month
- **ffmpeg** installed on your system


---

## Installation

# Clone the repository
git clone https://github.com/lulueve3/srt-to-audio-elevenlabs.git

cd srt-to-audio-elevenlabs

# Install dependencies
pip install -r requirements.txt


## Usage

1. **Prepare** an `.srt` subtitle file.
2. **Run** the program:
   python srt_to_audio.py
3. In the **GUI**:
   * Select your `.srt` file.
   * Enter your **ElevenLabs API Key**.
   * Enter your **Voice ID** (from ElevenLabs voice settings).
   * Enter **Model ID** (default: `eleven_flash_v2_5`).
   * Adjust **Max Speed** if needed.
   * Click **Start Conversion**.
4. Output audio file will be saved as:
   output_audio.mp3 in the same folder as the `.srt`.

note:

<img width="720" height="695" alt="hCgu92sWwH" src="https://github.com/user-attachments/assets/de216ee9-1489-4fae-aba0-45718e7aa2a3" />

**Max Speed*
This controls the maximum playback speed for the generated speech.
The program automatically adjusts speed based on subtitle duration ( default 1.0 ~ 1.5)
- 1.0 = normal speed.
- '>1.0 = speed up speech to fit shorter subtitles.
- Recommended: 1.5 for most cases.


## Resume Feature

If the process stops unexpectedly:

* Click start again to continue from the last process..

---

