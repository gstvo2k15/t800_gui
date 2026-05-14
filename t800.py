import cv2
import numpy as np
import wave
import math
import os
import time
from moviepy import VideoFileClip, AudioFileClip


INPUT = "input.mp4"
TEMP_VIDEO = "t800_video_no_audio.mp4"
TEMP_AUDIO = "t800_sfx.wav"
OUTPUT = "t800_hud_audio.mp4"

MAX_FRAMES = None
# MAX_FRAMES = 600

SAMPLE_RATE = 44100

WHITE = (220, 245, 245)
DIM = (120, 180, 180)
DARK = (50, 40, 40)
RED_BGR = (0, 0, 190)

font = cv2.FONT_HERSHEY_SIMPLEX


def put_text(img, text, x, y, scale=1.0, thickness=2, color=WHITE):
    cv2.putText(img, text, (int(x), int(y)), font, scale, color, thickness, cv2.LINE_AA)


def typewriter(text, frame_id, start_frame, chars_per_frame=0.45):
    n = int((frame_id - start_frame) * chars_per_frame)
    if n <= 0:
        return ""
    return text[:min(n, len(text))]


def is_typing(frame_id, start_frame, text, chars_per_frame=0.45):
    n = int((frame_id - start_frame) * chars_per_frame)
    return 0 <= n < len(text)


def draw_crosshair(img, cx, cy, r=95):
    cv2.circle(img, (cx, cy), r, WHITE, 3, cv2.LINE_AA)
    cv2.circle(img, (cx, cy), int(r * 0.48), DARK, 2, cv2.LINE_AA)

    cv2.line(img, (cx - r, cy), (cx + r, cy), DARK, 2, cv2.LINE_AA)
    cv2.line(img, (cx, cy - r), (cx, cy + r), DARK, 2, cv2.LINE_AA)

    cv2.line(img, (cx - 14, cy), (cx + 14, cy), DARK, 2, cv2.LINE_AA)
    cv2.line(img, (cx, cy - 14), (cx, cy + 14), DARK, 2, cv2.LINE_AA)


def draw_grid(img, x, y, w, h, cell=28, alpha_phase=1.0):
    color = (
        int(120 + 80 * alpha_phase),
        int(190 + 40 * alpha_phase),
        int(190 + 40 * alpha_phase),
    )

    for xx in range(x, x + w + 1, cell):
        cv2.line(img, (xx, y), (xx, y + h), color, 1, cv2.LINE_AA)

    for yy in range(y, y + h + 1, cell):
        cv2.line(img, (x, yy), (x + w, yy), color, 1, cv2.LINE_AA)

    cv2.rectangle(img, (x, y), (x + w, y + h), color, 2, cv2.LINE_AA)


def draw_scan_line(img, frame_id):
    h, w = img.shape[:2]
    y = int((frame_id * 7) % h)
    cv2.line(img, (0, y), (w, y), (255, 255, 255), 1, cv2.LINE_AA)


def draw_cursor_box(img, x, y, frame_id, size=28):
    if (frame_id // 12) % 2 == 0:
        cv2.rectangle(img, (x, y - size), (x + size, y), WHITE, -1)


def draw_check_box(img, x, y, frame_id, start_frame):
    size = 44

    if frame_id < start_frame:
        return

    cv2.rectangle(img, (x, y), (x + size, y + size), WHITE, 3, cv2.LINE_AA)

    progress = min(1.0, (frame_id - start_frame) / 18)

    if progress > 0:
        p1 = (x + 8, y + 24)
        p2 = (x + int(18 * progress), y + int(36 * progress))

        cv2.line(img, p1, p2, WHITE, 5, cv2.LINE_AA)

    if progress > 0.45:
        p2 = (x + 18, y + 36)
        p3 = (
            x + 18 + int(22 * ((progress - 0.45) / 0.55)),
            y + 36 - int(30 * ((progress - 0.45) / 0.55)),
        )
        cv2.line(img, p2, p3, WHITE, 5, cv2.LINE_AA)


def draw_scrolling_numbers(img, x, y, frame_id):
    rows = [
        "234654 453 30",
        "654334 450 16",
        "245261 865 26",
        "453665 766 46",
        "382856 863 09",
        "356878 544 04",
        "664217 985 89",
        "254346 956 32",
    ]

    offset = (frame_id // 4) % len(rows)

    for i in range(6):
        line = rows[(i + offset) % len(rows)]
        put_text(img, line, x, y + i * 36, 1.0, 3)


def draw_route(img, frame_id):
    h, w = img.shape[:2]

    panel_x = int(w * 0.18)
    panel_y = int(h * 0.20)
    panel_w = int(w * 0.46)
    panel_h = int(h * 0.43)

    cv2.rectangle(img, (panel_x, panel_y), (panel_x + panel_w, panel_y + panel_h), (70, 20, 20), -1)
    cv2.rectangle(img, (panel_x, panel_y), (panel_x + panel_w, panel_y + panel_h), DIM, 2)

    # circuito falso
    for i in range(14):
        x1 = panel_x + 30 + i * 45
        y1 = panel_y + 40 + ((i * 37) % (panel_h - 80))
        x2 = min(panel_x + panel_w - 20, x1 + 70)
        y2 = y1 + ((-1) ** i) * 35

        cv2.line(img, (x1, y1), (x2, y1), DARK, 2)
        cv2.line(img, (x2, y1), (x2, y2), DARK, 2)

    pts = [
        (panel_x + 80, panel_y + 180),
        (panel_x + 210, panel_y + 180),
        (panel_x + 250, panel_y + 250),
        (panel_x + 350, panel_y + 250),
        (panel_x + 410, panel_y + 190),
        (panel_x + 480, panel_y + 190),
    ]

    progress = min(1.0, max(0, (frame_id - 80) / 120))
    visible_segments = int(progress * (len(pts) - 1))

    for i in range(visible_segments):
        cv2.line(img, pts[i], pts[i + 1], WHITE, 8, cv2.LINE_AA)
        cv2.line(img, pts[i], pts[i + 1], DIM, 3, cv2.LINE_AA)

    put_text(img, "REROUTE", panel_x + 230, panel_y + panel_h + 70, 1.8, 3)
    draw_cursor_box(img, panel_x + 520, panel_y + panel_h + 62, frame_id, 34)


def draw_hud(frame, frame_id, fps):
    h, w = frame.shape[:2]

    # rojo fuerte
    red = np.zeros_like(frame)
    red[:, :] = RED_BGR
    frame = cv2.addWeighted(frame, 0.38, red, 0.62, 0)

    # contraste agresivo
    frame = cv2.convertScaleAbs(frame, alpha=1.15, beta=-18)

    # blur óptico leve
    if frame_id % 2 == 0:
        frame = cv2.GaussianBlur(frame, (3, 3), 0)

    overlay = frame.copy()

    mode = (frame_id // int(fps * 5)) % 4

    # scanline global
    draw_scan_line(overlay, frame_id)

    # efecto CRT horizontal
    overlay[::5, :] = (overlay[::5, :] * 0.62).astype(np.uint8)

    if mode == 0:
        title = typewriter("SEARCH MODE", frame_id, 15, 0.55)
        put_text(overlay, title, int(w * 0.25), int(h * 0.82), 2.1, 4)
        draw_cursor_box(overlay, int(w * 0.25) + len(title) * 48, int(h * 0.82), frame_id, 40)

        cx = int(w * 0.18 + math.sin(frame_id * 0.04) * 90)
        cy = int(h * 0.48 + math.cos(frame_id * 0.035) * 70)
        draw_crosshair(overlay, cx, cy, 95)

        put_text(overlay, "PARAMETERS:", int(w * 0.74), 110, 1.1, 3)
        draw_scrolling_numbers(overlay, int(w * 0.74), 165, frame_id)

        if frame_id % 90 > 45:
            draw_grid(overlay, int(w * 0.76), int(h * 0.47), 240, 170, 22)

    elif mode == 1:
        draw_route(overlay, frame_id)

        put_text(overlay, "CODE:", 35, 150, 1.1, 3)
        draw_scrolling_numbers(overlay, 35, 205, frame_id)

        put_text(overlay, "SEARCH PARAMETERS", int(w * 0.75), 170, 1.0, 3)
        put_text(overlay, "SPEED", int(w * 0.75), 500, 1.0, 3)
        put_text(overlay, "DIRECTION", int(w * 0.75), 550, 1.0, 3)

    elif mode == 2:
        put_text(overlay, "IMAGE", int(w * 0.27), int(h * 0.85), 2.0, 4)
        put_text(overlay, "ENHANCE", int(w * 0.48), int(h * 0.85), 2.0, 4)
        draw_check_box(overlay, int(w * 0.67), int(h * 0.80), frame_id, int(fps * 11))

        put_text(overlay, "IMAGE", 35, 95, 1.1, 3)
        put_text(overlay, "LEVEL", 35, 135, 1.1, 3)
        draw_scrolling_numbers(overlay, 35, 210, frame_id)

        put_text(overlay, "IMAGE ENHANCE", int(w * 0.73), 95, 1.1, 3)
        put_text(overlay, "MODE 423-6503", int(w * 0.73), 135, 1.1, 3)
        put_text(overlay, "SEQUENCERS 20", int(w * 0.73), 230, 1.1, 3)

        put_text(overlay, "SPEED PARAMETERS", int(w * 0.72), 420, 1.1, 3)
        put_text(overlay, "HUE1  234654 453 30", int(w * 0.72), 480, 1.0, 3)
        put_text(overlay, "SATU  654334 450 16", int(w * 0.72), 520, 1.0, 3)
        put_text(overlay, "BALN  245261 865 26", int(w * 0.72), 560, 1.0, 3)

    else:
        put_text(overlay, "ANALYSIS:   MATCH:", 35, 120, 1.1, 3)
        put_text(overlay, "389 VEHI   55378", 35, 180, 1.0, 3)
        put_text(overlay, "690 SIZE   38022", 35, 220, 1.0, 3)
        put_text(overlay, "600 TSPD   23022", 35, 260, 1.0, 3)
        put_text(overlay, "287 HPWR   12048", 35, 300, 1.0, 3)

        put_text(overlay, "SCAN MODE LEVEL 43545", int(w * 0.32), 120, 1.1, 3)
        put_text(overlay, "ASSESS VEHICLE", int(w * 0.32), 160, 1.1, 3)

        put_text(overlay, "VISUAL:", int(w * 0.72), 260, 1.1, 3)
        put_text(overlay, "MODEL 382", int(w * 0.72), 300, 1.1, 3)
        put_text(overlay, "SLSTS", int(w * 0.72), 340, 1.1, 3)
        put_text(overlay, "91 FATBOY", int(w * 0.72), 380, 1.1, 3)

        draw_grid(overlay, int(w * 0.74), int(h * 0.12), 340, 220, 28)
        draw_check_box(overlay, int(w * 0.66), int(h * 0.80), frame_id, int(fps * 16))

    # ruido barato
    noise = np.random.randint(-5, 6, overlay.shape, dtype=np.int16)
    overlay = np.clip(overlay.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    return overlay


def add_tone(audio, start_s, duration_s, freq=1200, volume=0.25):
    start = int(start_s * SAMPLE_RATE)
    length = int(duration_s * SAMPLE_RATE)

    if start + length >= len(audio):
        return

    for i in range(length):
        t = i / SAMPLE_RATE
        env = 1.0 - (i / length)
        sample = math.sin(2 * math.pi * freq * t) * volume * env
        audio[start + i] += sample


def make_audio(duration_s, fps):
    total_samples = int(duration_s * SAMPLE_RATE)
    audio = np.zeros(total_samples, dtype=np.float32)

    # tecleo rápido
    for t in np.arange(0.3, duration_s, 0.075):
        freq = np.random.choice([900, 1100, 1300, 1600])
        add_tone(audio, t, 0.018, freq=freq, volume=0.18)

    # scrolls
    for t in np.arange(1.2, duration_s, 1.8):
        for k in range(8):
            add_tone(audio, t + k * 0.025, 0.015, freq=500 + k * 90, volume=0.14)

    # checks
    for t in np.arange(3.5, duration_s, 5.0):
        add_tone(audio, t, 0.08, freq=700, volume=0.30)
        add_tone(audio, t + 0.08, 0.10, freq=1400, volume=0.25)

    # pulso bajo
    for t in np.arange(0, duration_s, 0.5):
        add_tone(audio, t, 0.05, freq=90, volume=0.12)

    audio = np.clip(audio, -1.0, 1.0)

    with wave.open(TEMP_AUDIO, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes((audio * 32767).astype(np.int16).tobytes())


def process_video():
    cap = cv2.VideoCapture(INPUT)

    if not cap.isOpened():
        raise RuntimeError(f"No se pudo abrir {INPUT}")

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if fps <= 0:
        fps = 25

    if MAX_FRAMES:
        total_out = min(MAX_FRAMES, total)
    else:
        total_out = total

    duration_s = total_out / fps

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(TEMP_VIDEO, fourcc, fps, (w, h))

    if not out.isOpened():
        raise RuntimeError("No se pudo crear el video temporal")

    start = time.time()
    frame_id = 0

    while True:
        ret, frame = cap.read()

        if not ret:
            break

        if MAX_FRAMES is not None and frame_id >= MAX_FRAMES:
            break

        hud = draw_hud(frame, frame_id, fps)
        out.write(hud)

        frame_id += 1

        if frame_id % 100 == 0:
            elapsed = time.time() - start
            speed = frame_id / elapsed
            pct = frame_id * 100 / total_out
            print(f"{frame_id}/{total_out} frames | {pct:.1f}% | {speed:.2f} fps")

    cap.release()
    out.release()

    make_audio(frame_id / fps, fps)

    video = VideoFileClip(TEMP_VIDEO)
    audio = AudioFileClip(TEMP_AUDIO)

    final = video.with_audio(audio)
    final.write_videofile(
        OUTPUT,
        codec="libx264",
        audio_codec="aac",
        fps=fps,
        preset="medium",
        bitrate="6000k",
    )

    video.close()
    audio.close()
    final.close()

    print(f"Generado: {OUTPUT}")


if __name__ == "__main__":
    process_video()