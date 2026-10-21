# T800 gui generator for videos
Basic repo for generate T800 gui in your videos

## Usage

Put your wished video as "input.mp4" and execute with `python t800.py` to generate "t800_hud.mp4" video.
---

## 🚀 Installation & Usage
### **1️⃣ Install Dependencies**
Make sure you have Python 3.10 or newer installed, then install required packages:

```bash
sudo apt install -yqq python3-tk python3.10-venv

python3.10 -m venv test
source test/bin/activate
pip install -r requirements.txt
```
**Note**: Only tested in Ubuntu/Debian distros.


### **2️⃣ Run the Program**
`python t800.py`

### **3️⃣ Deactivate Virtual Environment when finished**
`
deactivate
`

### Wintel usage
```powershell
python.exe -m venv wintel

Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process

.\wintel\Scripts\Activate.ps1

pip install -r requirements.txt

python t800.py
```
## Rendering

The renderer encodes H.264 video (CRF 14, slow preset) and 256 kb/s AAC audio directly with FFmpeg, provided by `imageio-ffmpeg`. It preserves the source resolution and frame rate. The red filter retains detail in bright areas instead of clipping them to solid red. Portrait videos use narrower HUD columns; odd dimensions are padded by one pixel for playback compatibility.

For the soundtrack, it selects a steady fragment of up to five seconds from `t800_sfx.mp3`, comparing loudness and spectral variation and avoiding the attack and tail where possible. A crossfade of up to 0.4 seconds joins the ends, with power compensation to reduce volume dips. This PCM loop repeats to cover the video without repeatedly decoding the full MP3. The selected interval is printed during export. Automatic selection reduces audible restarts; prominent rhythmic or melodic motifs can still sound repetitive.

Run from the directory containing `input.mp4` and `t800_sfx.mp3`. The output is replaced only after a successful export. Known premature read failures abort the export; when the source provides no frame count, end-of-file and decoding failure cannot be distinguished reliably.
