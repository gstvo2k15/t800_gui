import cv2
import numpy as np
import wave
import math
import time
from moviepy import VideoFileClip, AudioFileClip

INPUT = "input.mp4"
TEMP_VIDEO = "t800_video_no_audio.mp4"
TEMP_AUDIO = "t800_sfx.wav"
OUTPUT = "t800_hud_audio.mp4"

MAX_FRAMES = None
# MAX_FRAMES = 900

SAMPLE_RATE = 44100

WHITE = (225, 250, 250)
CYAN = (180, 245, 255)
DIM = (110, 170, 175)
DARK = (55, 30, 30)
RED_BGR = (0, 0, 210)

font = cv2.FONT_HERSHEY_SIMPLEX


def put(img, text, x, y, s=1.4, t=3, c=WHITE):
    cv2.putText(img, text, (int(x), int(y)), font, s, c, t, cv2.LINE_AA)


def typewriter(text, f, start, speed=0.8):
    n = int((f - start) * speed)
    return text[:max(0, min(len(text), n))]


def cursor(img, x, y, f, size=42):
    if (f // 10) % 2 == 0:
        cv2.rectangle(img, (int(x), int(y - size)), (int(x + size), int(y)), WHITE, -1)


def panel(img, x, y, w, h, border=2):
    cv2.rectangle(img, (x, y), (x + w, y + h), (55, 12, 12), -1)
    cv2.rectangle(img, (x, y), (x + w, y + h), DIM, border, cv2.LINE_AA)


def scanlines(img):
    img[::4, :] = (img[::4, :] * 0.55).astype(np.uint8)
    img[1::4, :] = (img[1::4, :] * 0.8).astype(np.uint8)


def scan_beam(img, f):
    h, w = img.shape[:2]
    y = int((f * 8) % h)
    cv2.line(img, (0, y), (w, y), WHITE, 1)
    cv2.line(img, (0, max(0, y - 2)), (w, max(0, y - 2)), DIM, 1)


def grid(img, x, y, w, h, cell=28):
    for xx in range(x, x + w + 1, cell):
        cv2.line(img, (xx, y), (xx, y + h), DIM, 1)
    for yy in range(y, y + h + 1, cell):
        cv2.line(img, (x, yy), (x + w, yy), DIM, 1)
    cv2.rectangle(img, (x, y), (x + w, y + h), CYAN, 2)


def crosshair(img, cx, cy, r=90):
    cv2.circle(img, (cx, cy), r, WHITE, 3, cv2.LINE_AA)
    cv2.circle(img, (cx, cy), int(r * 0.45), DARK, 2, cv2.LINE_AA)
    cv2.line(img, (cx - r, cy), (cx + r, cy), DARK, 2)
    cv2.line(img, (cx, cy - r), (cx, cy + r), DARK, 2)
    cv2.line(img, (cx - 16, cy), (cx + 16, cy), DARK, 2)
    cv2.line(img, (cx, cy - 16), (cx, cy + 16), DARK, 2)


def edge_pointer(w, h, f):
    cx, cy = w // 2, h // 2
    phase = (f // 80) % 8
    p = (f % 80) / 80.0
    p = 0.5 - 0.5 * math.cos(p * math.pi)

    targets = [
        (80, h // 2),
        (w - 80, h // 2),
        (w // 2, 80),
        (w // 2, h - 80),
        (120, 120),
        (w - 120, 120),
        (120, h - 120),
        (w - 120, h - 120),
    ]

    tx, ty = targets[phase]
    x = int(cx + (tx - cx) * p)
    y = int(cy + (ty - cy) * p)
    return x, y


def numbers(img, x, y, f, rows=7, s=1.25):
    base = [
        "234654 453 30",
        "654334 450 16",
        "245261 865 26",
        "453665 766 46",
        "382856 863 09",
        "356878 544 04",
        "664217 985 89",
        "254346 956 32",
        "389 VEHI 55378",
        "690 SIZE 38022",
        "600 TSPD 23022",
        "287 HPWR 12048",
    ]
    off = (f // 5) % len(base)
    for i in range(rows):
        put(img, base[(off + i) % len(base)], x, y + i * int(38 * s), s, 3)


def checkbox(img, x, y, f, start):
    size = 54
    cv2.rectangle(img, (x, y), (x + size, y + size), WHITE, 3)
    p = min(1.0, max(0, (f - start) / 22))
    if p > 0:
        cv2.rectangle(img, (x + 8, y + 8), (x + int(8 + 38 * p), y + 46), WHITE, -1)


def compass(img, x, y):
    r = 95
    dirs = [
        ("N", 0, -1), ("NE", 0.7, -0.7), ("E", 1, 0), ("SE", 0.7, 0.7),
        ("S", 0, 1), ("SW", -0.7, 0.7), ("W", -1, 0), ("NW", -0.7, -0.7)
    ]
    for label, dx, dy in dirs:
        cv2.line(img, (x, y), (int(x + dx * r), int(y + dy * r)), WHITE, 5)
        put(img, label, x + dx * (r + 35) - 20, y + dy * (r + 35) + 10, 1.0, 3)


def route_mode(img, f):
    h, w = img.shape[:2]

    px, py = int(w * 0.13), int(h * 0.17)
    pw, ph = int(w * 0.58), int(h * 0.48)
    panel(img, px, py, pw, ph)

    for i in range(26):
        x1 = px + 35 + (i * 67) % (pw - 80)
        y1 = py + 40 + (i * 43) % (ph - 70)
        x2 = min(px + pw - 25, x1 + 80)
        y2 = y1 + ((-1) ** i) * 36
        cv2.line(img, (x1, y1), (x2, y1), DARK, 2)
        cv2.line(img, (x2, y1), (x2, y2), DARK, 2)

    pts = [
        (px + 90, py + 180),
        (px + 250, py + 180),
        (px + 320, py + 280),
        (px + 470, py + 280),
        (px + 560, py + 195),
        (px + 680, py + 195),
    ]

    progress = min(1.0, max(0, (f % 180) / 120))
    segs = int(progress * (len(pts) - 1))

    for i in range(segs):
        cv2.line(img, pts[i], pts[i + 1], WHITE, 10, cv2.LINE_AA)
        cv2.line(img, pts[i], pts[i + 1], CYAN, 4, cv2.LINE_AA)

    put(img, "REROUTE", px + 260, py + ph + 80, 2.4, 5)
    cursor(img, px + 620, py + ph + 72, f, 50)

    if f % 180 > 110:
        put(img, "ALTERNATE  POWER", px + 190, py + ph + 160, 2.4, 5)
        checkbox(img, px + 770, py + ph + 112, f, 110)

    put(img, "CODE:", 40, 135, 1.5, 4)
    numbers(img, 40, 200, f, 7, 1.25)

    put(img, "SEARCH PARAMETERS", int(w * 0.76), 140, 1.3, 4)
    put(img, "GUIDE 654334", int(w * 0.76), 210, 1.15, 3)
    put(img, "SPEED 245261", int(w * 0.76), 260, 1.15, 3)
    put(img, "DIRECTION", int(w * 0.76), 540, 1.25, 4)


def enhance_mode(img, f):
    h, w = img.shape[:2]

    put(img, "IMAGE", int(w * 0.27), int(h * 0.86), 2.8, 5)
    put(img, "ENHANCE", int(w * 0.49), int(h * 0.86), 2.8, 5)
    checkbox(img, int(w * 0.70), int(h * 0.80), f, 20)

    put(img, "IMAGE", 38, 95, 1.45, 4)
    put(img, "LEVEL", 38, 145, 1.45, 4)
    numbers(img, 38, 230, f, 7, 1.25)

    put(img, "IMAGE ENHANCE", int(w * 0.73), 95, 1.45, 4)
    put(img, "MODE 423-6503", int(w * 0.73), 145, 1.45, 4)
    put(img, "SEQUENCERS 20", int(w * 0.73), 250, 1.45, 4)

    put(img, "SPEED PARAMETERS", int(w * 0.70), 430, 1.45, 4)
    numbers(img, int(w * 0.70), 500, f, 6, 1.1)

    compass(img, int(w * 0.84), int(h * 0.25))

    put(img, "SCAN LEVELS:", 40, 420, 1.35, 4)
    put(img, "****************", 40, 460, 1.15, 3)
    put(img, "234654 453 30", 40, 515, 1.35, 4)

    put(img, "LATERAL SPEED   573 3589", int(w * 0.63), int(h * 0.60), 1.35, 4)


def scan_vehicle_mode(img, f):
    h, w = img.shape[:2]

    put(img, "CRITERIA:", 35, 130, 1.5, 4)
    put(img, "**************", 35, 175, 1.2, 3)
    numbers(img, 35, 240, f, 8, 1.22)

    gx = int(w * 0.73)
    gy = int(h * 0.16)
    grid(img, gx, gy, 420, 260, 30)

    put(img, "SCAN MODE 03958", int(w * 0.70), int(h * 0.63), 1.55, 4)
    put(img, "ACQUIRE TRANSPORT", int(w * 0.70), int(h * 0.70), 1.55, 4)
    put(img, "PRIORITY 1238905D", int(w * 0.70), int(h * 0.76), 1.55, 4)

    put(img, "VEHI 35793 43457 33", int(w * 0.70), int(h * 0.84), 1.25, 4)
    put(img, "MTRC 23491 46000 40", int(w * 0.70), int(h * 0.89), 1.25, 4)
    put(img, "TRCT 24812 04343 00", int(w * 0.70), int(h * 0.94), 1.25, 4)


def search_mode(img, f):
    h, w = img.shape[:2]

    cx, cy = edge_pointer(w, h, f)
    crosshair(img, cx, cy, 95)

    put(img, typewriter("SEARCH MODE", f % 160, 5, 0.9), int(w * 0.25), int(h * 0.82), 2.0, 4)
    cursor(img, int(w * 0.25) + 520, int(h * 0.82), f, 46)

    put(img, "PARAMETERS:", int(w * 0.73), 105, 1.35, 4)
    numbers(img, int(w * 0.73), 170, f, 6, 1.1)

    if (f // 50) % 2 == 0:
        grid(img, int(w * 0.74), int(h * 0.51), 310, 190, 24)


def ident_mode(img, f):
    h, w = img.shape[:2]

    panel(img, int(w * 0.20), int(h * 0.10), int(w * 0.45), int(h * 0.55))

    put(img, "CODE:", 30, 140, 1.5, 4)
    numbers(img, 30, 210, f, 6, 1.2)

    put(img, "MATCH CRITERIA", int(w * 0.70), 110, 1.5, 4)
    put(img, "NETFILE 342-589", int(w * 0.70), 190, 1.3, 4)
    put(img, "MISSION PROFILE", int(w * 0.70), 240, 1.3, 4)
    put(img, "CONNOR, JOHN", int(w * 0.70), 340, 1.55, 4)
    put(img, "****************", int(w * 0.70), 385, 1.1, 3)
    numbers(img, int(w * 0.70), 450, f, 8, 1.05)

    put(img, "TARGET", int(w * 0.32), int(h * 0.46), 2.1, 5)
    put(img, "ACQUIRED", int(w * 0.30), int(h * 0.54), 2.1, 5)

    put(img, "IDENT  POSITIVE", int(w * 0.31), int(h * 0.88), 2.7, 5)
    checkbox(img, int(w * 0.66), int(h * 0.81), f, 40)

    put(img, "PERCENTAGE MATCH:", int(w * 0.70), int(h * 0.82), 1.25, 4)
    put(img, "99.45036 PROBABLE", int(w * 0.70), int(h * 0.90), 1.25, 4)


def draw_hud(frame, frame_id, fps):
    h, w = frame.shape[:2]

    red = np.zeros_like(frame)
    red[:] = RED_BGR
    frame = cv2.addWeighted(frame, 0.30, red, 0.70, 0)
    frame = cv2.convertScaleAbs(frame, alpha=1.32, beta=-30)

    if frame_id % 2 == 0:
        frame = cv2.GaussianBlur(frame, (3, 3), 0)

    img = frame.copy()

    scanlines(img)
    scan_beam(img, frame_id)

    mode = (frame_id // int(fps * 4)) % 5

    if mode == 0:
        search_mode(img, frame_id)
    elif mode == 1:
        route_mode(img, frame_id)
    elif mode == 2:
        enhance_mode(img, frame_id)
    elif mode == 3:
        scan_vehicle_mode(img, frame_id)
    else:
        ident_mode(img, frame_id)

    noise = np.random.randint(-6, 7, img.shape, dtype=np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    return img


def tone(audio, start, dur, freq, vol):
    a = int(start * SAMPLE_RATE)
    n = int(dur * SAMPLE_RATE)
    if a + n >= len(audio):
        return
    for i in range(n):
        t = i / SAMPLE_RATE
        env = 1.0 - i / n
        audio[a + i] += math.sin(2 * math.pi * freq * t) * vol * env


def make_audio(duration):
    audio = np.zeros(int(duration * SAMPLE_RATE), dtype=np.float32)

    for t in np.arange(0.2, duration, 0.06):
        tone(audio, t, 0.014, np.random.choice([900, 1100, 1350, 1700]), 0.16)

    for t in np.arange(1.0, duration, 1.3):
        for k in range(10):
            tone(audio, t + k * 0.022, 0.012, 400 + k * 120, 0.13)

    for t in np.arange(3.2, duration, 4.0):
        tone(audio, t, 0.06, 600, 0.28)
        tone(audio, t + 0.07, 0.09, 1500, 0.24)

    for t in np.arange(0, duration, 0.45):
        tone(audio, t, 0.05, 85, 0.11)

    audio = np.clip(audio, -1, 1)

    with wave.open(TEMP_AUDIO, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes((audio * 32767).astype(np.int16).tobytes())


def main():
    cap = cv2.VideoCapture(INPUT)
    if not cap.isOpened():
        raise RuntimeError(f"No se pudo abrir {INPUT}")

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    total_out = min(MAX_FRAMES, total) if MAX_FRAMES else total

    out = cv2.VideoWriter(
        TEMP_VIDEO,
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (w, h),
    )

    start = time.time()
    frame_id = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if MAX_FRAMES and frame_id >= MAX_FRAMES:
            break

        out.write(draw_hud(frame, frame_id, fps))
        frame_id += 1

        if frame_id % 100 == 0:
            elapsed = time.time() - start
            print(f"{frame_id}/{total_out} | {frame_id * 100 / total_out:.1f}% | {frame_id / elapsed:.2f} fps")

    cap.release()
    out.release()

    make_audio(frame_id / fps)

    video = VideoFileClip(TEMP_VIDEO)
    audio = AudioFileClip(TEMP_AUDIO)

    final = video.with_audio(audio)
    final.write_videofile(
        OUTPUT,
        codec="libx264",
        audio_codec="aac",
        fps=fps,
        bitrate="7000k",
        preset="medium",
    )

    video.close()
    audio.close()
    final.close()

    print(f"Generado: {OUTPUT}")


if __name__ == "__main__":
    main()