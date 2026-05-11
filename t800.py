import cv2
import numpy as np
import random
import time

INPUT = "input.mp4"
OUTPUT = "t800_hud.mp4"

MAX_FRAMES = None
# MAX_FRAMES = 300  # descomenta para prueba rápida

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
out = cv2.VideoWriter(OUTPUT, fourcc, fps, (w, h))

if not out.isOpened():
    raise RuntimeError(f"No se pudo crear el video de salida: {OUTPUT}")

font = cv2.FONT_HERSHEY_SIMPLEX


def put_text(img, text, pos, scale=1.0, thickness=3):
    cv2.putText(
        img,
        text,
        pos,
        font,
        scale,
        (210, 230, 235),
        thickness,
        cv2.LINE_AA,
    )


def draw_hud(frame, frame_id):
    # Tinte rojo
    red = np.zeros_like(frame)
    red[:, :] = (0, 0, 180)
    frame = cv2.addWeighted(frame, 0.45, red, 0.55, 0)

    # Oscurecimiento leve
    frame = cv2.convertScaleAbs(frame, alpha=0.95, beta=-8)

    # Texto superior izquierdo
    x, y = 80, 100
    put_text(frame, "TRAJECTORY LOGGING:", (x, y), 1.1, 3)

    nums = [
        "5439 543 5435 65311",
        "6465 656 7689 10930",
        "54392 5432 875",
    ]

    for i, line in enumerate(nums):
        jitter = random.randint(-1, 1)
        put_text(frame, line, (x + jitter, y + 45 + i * 35), 1.0, 3)

    # Crosshair móvil
    cx = int(w * 0.55 + np.sin(frame_id * 0.03) * 120)
    cy = int(h * 0.50 + np.cos(frame_id * 0.025) * 70)

    radius = 110

    cv2.circle(frame, (cx, cy), radius, (210, 230, 235), 3, cv2.LINE_AA)
    cv2.circle(frame, (cx, cy), 55, (90, 45, 45), 2, cv2.LINE_AA)

    cv2.line(frame, (cx - radius, cy), (cx + radius, cy), (90, 45, 45), 2, cv2.LINE_AA)
    cv2.line(frame, (cx, cy - radius), (cx, cy + radius), (90, 45, 45), 2, cv2.LINE_AA)

    cv2.line(frame, (cx - 15, cy), (cx + 15, cy), (90, 45, 45), 2, cv2.LINE_AA)
    cv2.line(frame, (cx, cy - 15), (cx, cy + 15), (90, 45, 45), 2, cv2.LINE_AA)

    # Parámetros derecha
    px = int(w * 0.78)
    py = 130

    put_text(frame, "PARAMETERS:", (px, py), 1.1, 3)

    params = [
        "3430  34  3430",
        "7347  73  7347",
        "2392  23  2392",
        "5643   5  5643",
        "3459   3  3459",
        "4535  45  4535",
    ]

    for i, line in enumerate(params):
        put_text(frame, line, (px, py + 45 + i * 38), 1.0, 3)

    # Texto inferior izquierdo
    put_text(
        frame,
        "PRIORITY OVERRIDE MULTIPLE TARGETS",
        (80, h - 120),
        1.1,
        3,
    )

    put_text(
        frame,
        "THREAT ASSESSMENT: POTENTIAL DAMAGE",
        (80, h - 80),
        1.1,
        3,
    )

    put_text(
        frame,
        f"{534053 + frame_id % 9999} {543596 + frame_id % 777} 876 874798 4745757 44",
        (80, h - 40),
        0.95,
        3,
    )

    # Texto inferior derecho
    right_x = int(w * 0.68)

    put_text(frame, "SELECT ALL TARGETS", (right_x, h - 120), 1.1, 3)
    put_text(frame, "TERMINATION OVERRIDE", (right_x, h - 80), 1.1, 3)
    put_text(frame, "DISABLE TARGETS ONLY", (right_x, h - 40), 1.1, 3)

    # Ruido rápido
    noise = np.random.randint(-6, 7, frame.shape, dtype=np.int16)
    noisy = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    # Barrido horizontal rápido
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

elapsed = time.time() - start

print()
print(f"Video generado: {OUTPUT}")
print(f"Frames procesados: {frame_id}")
print(f"Tiempo total: {elapsed:.1f}s")