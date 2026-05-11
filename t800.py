import cv2
import numpy as np
import random

INPUT = "input.mp4"
OUTPUT = "t800_hud.mp4"

cap = cv2.VideoCapture(INPUT)

w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = cap.get(cv2.CAP_PROP_FPS)

fourcc = cv2.VideoWriter_fourcc(*"mp4v")
out = cv2.VideoWriter(OUTPUT, fourcc, fps, (w, h))

font = cv2.FONT_HERSHEY_SIMPLEX

def draw_hud(frame, t):
    overlay = frame.copy()

    # Tinte rojo general
    red = np.zeros_like(frame)
    red[:, :] = (0, 0, 180)
    frame = cv2.addWeighted(frame, 0.45, red, 0.55, 0)

    # Texto superior izquierdo
    x, y = 80, 100
    cv2.putText(frame, "TRAJECTORY LOGGING:", (x, y),
                font, 1.1, (210, 230, 235), 3, cv2.LINE_AA)

    nums = [
        "5439 543 5435 65311",
        "6465 656 7689 10930",
        "54392 5432 875"
    ]

    for i, line in enumerate(nums):
        jitter = random.randint(-1, 1)
        cv2.putText(frame, line, (x + jitter, y + 45 + i * 35),
                    font, 1.0, (210, 230, 235), 3, cv2.LINE_AA)

    # Crosshair central móvil
    cx = int(w * 0.55 + np.sin(t * 0.03) * 120)
    cy = int(h * 0.50 + np.cos(t * 0.025) * 70)

    radius = 110
    cv2.circle(frame, (cx, cy), radius, (210, 230, 235), 3, cv2.LINE_AA)
    cv2.circle(frame, (cx, cy), 55, (80, 40, 40), 2, cv2.LINE_AA)

    cv2.line(frame, (cx - radius, cy), (cx + radius, cy),
             (80, 40, 40), 2, cv2.LINE_AA)
    cv2.line(frame, (cx, cy - radius), (cx, cy + radius),
             (80, 40, 40), 2, cv2.LINE_AA)

    cv2.line(frame, (cx - 15, cy), (cx + 15, cy),
             (80, 40, 40), 2, cv2.LINE_AA)
    cv2.line(frame, (cx, cy - 15), (cx, cy + 15),
             (80, 40, 40), 2, cv2.LINE_AA)

    # Parámetros derecha
    px = int(w * 0.78)
    py = 130

    cv2.putText(frame, "PARAMETERS:", (px, py),
                font, 1.1, (210, 230, 235), 3, cv2.LINE_AA)

    params = [
        "3430  34  3430",
        "7347  73  7347",
        "2392  23  2392",
        "5643   5  5643",
        "3459   3  3459",
        "4535  45  4535",
    ]

    for i, line in enumerate(params):
        cv2.putText(frame, line, (px, py + 45 + i * 38),
                    font, 1.0, (210, 230, 235), 3, cv2.LINE_AA)

    # Texto inferior
    cv2.putText(frame, "PRIORITY OVERRIDE MULTIPLE TARGETS",
                (80, h - 120), font, 1.1, (210, 230, 235), 3, cv2.LINE_AA)

    cv2.putText(frame, "THREAT ASSESSMENT: POTENTIAL DAMAGE",
                (80, h - 80), font, 1.1, (210, 230, 235), 3, cv2.LINE_AA)

    cv2.putText(frame, "SELECT ALL TARGETS",
                (int(w * 0.68), h - 120), font, 1.1, (210, 230, 235), 3, cv2.LINE_AA)

    cv2.putText(frame, "TERMINATION OVERRIDE",
                (int(w * 0.68), h - 80), font, 1.1, (210, 230, 235), 3, cv2.LINE_AA)

    # Ruido leve
    noise = np.random.normal(0, 8, frame.shape).astype(np.int16)
    noisy = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    # Barrido horizontal tenue
    for yy in range(0, h, 6):
        noisy[yy:yy+1, :] = np.clip(noisy[yy:yy+1, :] * 0.75, 0, 255)

    return noisy

frame_id = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break

    hud = draw_hud(frame, frame_id)
    out.write(hud)
    frame_id += 1

cap.release()
out.release()