import cv2
import numpy as np
import random
import time
from moviepy import VideoFileClip, AudioFileClip, concatenate_audioclips

INPUT = "input.mp4"
SFX = "t800_sfx.mp3"

TEMP_VIDEO = "t800_hud_silent.mp4"
OUTPUT = "t800_hud.mp4"

MAX_FRAMES = None
# MAX_FRAMES = 300

cap = cv2.VideoCapture(INPUT)

if not cap.isOpened():
    raise RuntimeError(f"No se pudo abrir el video: {INPUT}")

w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = cap.get(cv2.CAP_PROP_FPS)
total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

if fps <= 0:
    fps = 25

fourcc = cv2.VideoWriter_fourcc(*"mp4v")
out = cv2.VideoWriter(TEMP_VIDEO, fourcc, fps, (w, h))

if not out.isOpened():
    raise RuntimeError(f"No se pudo crear el video temporal: {TEMP_VIDEO}")

font = cv2.FONT_HERSHEY_SIMPLEX

WHITE = (210, 230, 235)
DARK = (90, 45, 45)


def put_text(img, text, pos, scale=1.0, thickness=3, color=WHITE):
    cv2.putText(img, text, pos, font, scale, color, thickness, cv2.LINE_AA)


def typed(text, frame_id, start_frame, speed=0.75):
    n = int((frame_id - start_frame) * speed)
    if n <= 0:
        return ""
    return text[:min(len(text), n)]


def cursor(img, x, y, frame_id, size=28):
    if (frame_id // 10) % 2 == 0:
        cv2.rectangle(img, (int(x), int(y - size)), (int(x + size), int(y)), WHITE, -1)


def moving_pointer(frame_id):
    cx0 = w // 2
    cy0 = h // 2

    radius_x = int(w * 0.22)
    radius_y = int(h * 0.16)

    cx = int(cx0 + np.sin(frame_id * 0.025) * radius_x)
    cy = int(cy0 + np.cos(frame_id * 0.018) * radius_y)

    return cx, cy


def draw_crosshair(frame, cx, cy):
    radius = 110

    cv2.circle(frame, (cx, cy), radius, WHITE, 3, cv2.LINE_AA)
    cv2.circle(frame, (cx, cy), 55, DARK, 2, cv2.LINE_AA)

    cv2.line(frame, (cx - radius, cy), (cx + radius, cy), DARK, 2, cv2.LINE_AA)
    cv2.line(frame, (cx, cy - radius), (cx, cy + radius), DARK, 2, cv2.LINE_AA)

    cv2.line(frame, (cx - 15, cy), (cx + 15, cy), DARK, 2, cv2.LINE_AA)
    cv2.line(frame, (cx, cy - 15), (cx, cy + 15), DARK, 2, cv2.LINE_AA)


def draw_tracking_grid(frame, cx, cy, frame_id):
    if frame_id % 160 <= 70:
        return

    gw = 220
    gh = 150
    cell = 22

    x1 = min(max(cx + 140, 20), w - gw - 20)
    y1 = min(max(cy - 80, 20), h - gh - 20)

    for xx in range(x1, x1 + gw + 1, cell):
        cv2.line(frame, (xx, y1), (xx, y1 + gh), WHITE, 1, cv2.LINE_AA)

    for yy in range(y1, y1 + gh + 1, cell):
        cv2.line(frame, (x1, yy), (x1 + gw, yy), WHITE, 1, cv2.LINE_AA)

    cv2.rectangle(frame, (x1, y1), (x1 + gw, y1 + gh), WHITE, 2, cv2.LINE_AA)


def draw_hud(frame, frame_id):
    red = np.zeros_like(frame)
    red[:, :] = (0, 0, 180)

    frame = cv2.addWeighted(frame, 0.45, red, 0.55, 0)
    frame = cv2.convertScaleAbs(frame, alpha=0.95, beta=-8)

    x, y = 80, 100

    title_raw = "TRAJECTORY LOGGING:"
    title = typed(title_raw, frame_id, 0, 0.55)
    put_text(frame, title, (x, y), 1.1, 3)

    if len(title) < len(title_raw):
        cursor(frame, x + len(title) * 24, y, frame_id, 26)

    nums = [
        "5439 543 5435 65311",
        "6465 656 7689 10930",
        "54392 5432 875",
    ]

    for i, line in enumerate(nums):
        text = typed(line, frame_id, 35 + i * 20, 0.9)

        if frame_id > 180:
            if i == 0:
                text = f"{5439 + frame_id % 80} 543 {5435 + frame_id % 40} {65311 + frame_id % 90}"
            elif i == 1:
                text = f"{6465 + frame_id % 60} 656 {7689 + frame_id % 70} {10930 + frame_id % 50}"
            else:
                text = f"{54392 + frame_id % 99} {5432 + frame_id % 88} {875 + frame_id % 77}"

        jitter = random.randint(-1, 1)
        put_text(frame, text, (x + jitter, y + 45 + i * 35), 1.0, 3)

    cx, cy = moving_pointer(frame_id)
    draw_crosshair(frame, cx, cy)
    draw_tracking_grid(frame, cx, cy, frame_id)

    px = int(w * 0.78)
    py = 130

    param_title = typed("PARAMETERS:", frame_id, 20, 0.65)
    put_text(frame, param_title, (px, py), 1.1, 3)

    params = [
        "3430  34  3430",
        "7347  73  7347",
        "2392  23  2392",
        "5643   5  5643",
        "3459   3  3459",
        "4535  45  4535",
    ]

    for i, line in enumerate(params):
        if frame_id < 130 + i * 10:
            text = typed(line, frame_id, 80 + i * 12, 0.8)
        else:
            a = 3430 + ((frame_id + i * 17) % 700)
            b = 3 + ((frame_id + i * 11) % 90)
            c = 3430 + ((frame_id + i * 23) % 700)
            text = f"{a:<5} {b:<3} {c:<5}"

        put_text(frame, text, (px, py + 45 + i * 38), 1.0, 3)

    left_1 = typed("PRIORITY OVERRIDE MULTIPLE TARGETS", frame_id, 70, 0.7)
    left_2 = typed("THREAT ASSESSMENT: POTENTIAL DAMAGE", frame_id, 115, 0.7)

    put_text(frame, left_1, (80, h - 120), 1.1, 3)
    put_text(frame, left_2, (80, h - 80), 1.1, 3)

    live_code = (
        f"{534053 + frame_id % 9999} "
        f"{543596 + frame_id % 777} "
        f"876 874798 4745757 44"
    )

    put_text(frame, typed(live_code, frame_id, 160, 1.2), (80, h - 40), 0.95, 3)

    right_x = int(w * 0.68)

    r1 = typed("SELECT ALL TARGETS", frame_id, 90, 0.75)
    r2 = typed("TERMINATION OVERRIDE", frame_id, 125, 0.75)
    r3 = typed("DISABLE TARGETS ONLY", frame_id, 160, 0.75)

    put_text(frame, r1, (right_x, h - 120), 1.1, 3)
    put_text(frame, r2, (right_x, h - 80), 1.1, 3)
    put_text(frame, r3, (right_x, h - 40), 1.1, 3)

    if frame_id % 220 > 150:
        put_text(frame, "SCAN MODE 03958", (right_x, h - 190), 1.15, 3)
        put_text(frame, "ACQUIRE TRANSPORT", (right_x, h - 150), 1.15, 3)

    noise = np.random.randint(-6, 7, frame.shape, dtype=np.int16)
    noisy = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    noisy[::6, :] = (noisy[::6, :] * 0.75).astype(np.uint8)

    return noisy


start = time.time()
frame_id = 0

while True:
    ret, frame = cap.read()

    if not ret:
        break

    if MAX_FRAMES is not None and frame_id >= MAX_FRAMES:
        break

    hud = draw_hud(frame, frame_id)
    out.write(hud)

    frame_id += 1

    if frame_id % 100 == 0:
        elapsed = time.time() - start
        fps_proc = frame_id / elapsed if elapsed > 0 else 0

        if total > 0:
            percent = frame_id * 100 / total
            print(f"{frame_id}/{total} frames | {percent:.1f}% | {fps_proc:.2f} fps")
        else:
            print(f"{frame_id} frames | {fps_proc:.2f} fps")

cap.release()
out.release()

print("Añadiendo audio...")

video = VideoFileClip(TEMP_VIDEO)
audio = AudioFileClip(SFX)

if audio.duration < video.duration:
    loops = int(video.duration // audio.duration) + 1
    audio_clips = [AudioFileClip(SFX) for _ in range(loops)]
    audio = concatenate_audioclips(audio_clips)

audio = audio.subclipped(0, video.duration)

final = video.with_audio(audio)

final.write_videofile(
    OUTPUT,
    codec="libx264",
    audio_codec="aac",
    fps=fps,
)

video.close()
audio.close()
final.close()

elapsed = time.time() - start

print()
print(f"Video generado: {OUTPUT}")
print(f"Frames procesados: {frame_id}")
print(f"Tiempo total: {elapsed:.1f}s")