import cv2
import numpy as np
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


class SceneTracker:
    """Keep the sight on a patch of the scene instead of animating it."""

    def __init__(self):
        self.position = np.array([w * 0.5, h * 0.5], dtype=np.float32)
        self.destination = self.position.copy()
        self.previous = None
        self.points = None
        self.age = 0

    def update(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if self.previous is not None and self.points is not None and len(self.points) >= 5:
            moved, status, _ = cv2.calcOpticalFlowPyrLK(
                self.previous, gray, self.points, None,
                winSize=(21, 21), maxLevel=2,
                criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.03),
            )
            if moved is not None:
                valid = status.ravel() == 1
                old = self.points.reshape(-1, 2)[valid]
                new = moved.reshape(-1, 2)[valid]
                if len(new) >= 5:
                    displacement = np.median(new - old, axis=0)
                    residual = np.linalg.norm((new - old) - displacement, axis=1)
                    inliers = residual < max(3.0, min(w, h) * 0.008)
                    if np.count_nonzero(inliers) >= 5:
                        displacement = np.median((new - old)[inliers], axis=0)
                        # Reject cuts and bad optical-flow matches.
                        if np.linalg.norm(displacement) < min(w, h) * 0.08:
                            self.destination += displacement * 0.8
                            self.points = new[inliers].reshape(-1, 1, 2)
                        else:
                            self.points = None
                    else:
                        self.points = None
                else:
                    self.points = None

        self.age += 1
        # Every second, scan toward a new high-contrast detail in the scene.
        # Keep the choices within the useful central field of view.
        scan_interval = max(1, int(fps))
        if self.age == 1 or self.age % scan_interval == 0:
            small = cv2.resize(gray, (max(1, w // 4), max(1, h // 4)))
            sh, sw = small.shape
            area = np.zeros_like(small)
            area[int(sh * .24):int(sh * .76), int(sw * .23):int(sw * .77)] = 255
            candidates = cv2.goodFeaturesToTrack(
                small, maxCorners=80, qualityLevel=0.02,
                minDistance=max(6, min(sw, sh) // 16), mask=area,
            )
            if candidates is not None:
                locations = candidates.reshape(-1, 2) * 4
                distances = np.linalg.norm(locations - self.position, axis=1)
                # Pick a distinct detail without jumping to the screen edge.
                eligible = np.flatnonzero(
                    (distances > min(w, h) * .10) &
                    (distances < min(w, h) * .38)
                )
                if len(eligible):
                    choice = eligible[(self.age // scan_interval) % len(eligible)]
                    self.destination = locations[choice].astype(np.float32)
                    self.points = None

        margin = min(w, h) * 0.13
        self.destination = np.clip(self.destination, [margin, margin], [w - margin, h - margin])
        self.position += (self.destination - self.position) * 0.065
        if self.points is None or len(self.points) < 12 or self.age % 24 == 0:
            mask = np.zeros(gray.shape, dtype=np.uint8)
            cx, cy = np.rint(self.destination).astype(int)
            radius = int(min(w, h) * 0.16)
            cv2.circle(mask, (cx, cy), radius, 255, -1)
            self.points = cv2.goodFeaturesToTrack(
                gray, maxCorners=60, qualityLevel=0.025,
                minDistance=max(5, min(w, h) // 100), mask=mask,
            )
        self.previous = gray
        return tuple(np.rint(self.position).astype(int))


def draw_crosshair(frame, cx, cy):
    radius = max(24, int(min(w, h) * 0.055))
    gap = max(5, radius // 6)
    for start, end in ((0, 65), (115, 155), (205, 245), (295, 350)):
        cv2.ellipse(frame, (cx, cy), (radius, radius), 0, start, end,
                    WHITE, 1, cv2.LINE_AA)
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        cv2.line(frame, (cx + dx * gap, cy + dy * gap),
                 (cx + dx * (radius + 8), cy + dy * (radius + 8)),
                 WHITE, 1, cv2.LINE_AA)
    cv2.circle(frame, (cx, cy), 2, WHITE, -1, cv2.LINE_AA)


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


def draw_hud(frame, frame_id, target):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    # Luminance survives the red filter, as in the film's monochrome POV.
    frame = cv2.merge((gray // 12, gray // 5, np.clip(gray.astype(np.float32) * 0.74 + 32, 0, 255).astype(np.uint8)))

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

        put_text(frame, text, (x, y + 45 + i * 35), 1.0, 3)

    cx, cy = target
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

    frame[::4, :] = (frame[::4, :] * 0.92).astype(np.uint8)
    return frame


start = time.time()
frame_id = 0
tracker = SceneTracker()

while True:
    ret, frame = cap.read()

    if not ret:
        break

    if MAX_FRAMES is not None and frame_id >= MAX_FRAMES:
        break

    hud = draw_hud(frame, frame_id, tracker.update(frame))
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
