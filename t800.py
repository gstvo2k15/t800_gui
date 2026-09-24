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

# Dimensions are configured by render_video; importing the renderer has no side effects.
w, h, fps = 1280, 720, 25.0
WHITE = (218, 235, 235)


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


def draw_hud(frame, frame_id, target):
    """Film-style red vision with compact, time-based diagnostic overlays."""
    height, width = frame.shape[:2]
    seconds = frame_id / fps
    # Deep red midtones, black shadows, and near-white overexposed highlights.
    levels = np.arange(256, dtype=np.float32) / 255
    red = np.clip((levels - .045) * 1.48, 0, 1)
    highlights = np.clip((levels - .56) / .40, 0, 1) ** 1.5
    lut = np.stack((highlights * 210, highlights * 225, red * 255), axis=1)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    tinted = lut.astype(np.uint8)[gray]

    # A fixed design space keeps the lettering legible at every output resolution.
    canvas_h = 720
    canvas_w = round(width / height * canvas_h)
    overlay = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
    margin = 24
    top = 88
    right = canvas_w - 310
    tick = int(seconds * 8)

    def text(value, x, y, scale=.58):
        cv2.putText(overlay, value, (int(x), int(y)), cv2.FONT_HERSHEY_DUPLEX,
                    scale, WHITE, 1, cv2.LINE_AA)

    def block(lines, x, y, reveal=0):
        for i, line in enumerate(lines):
            # Short terminal bursts instead of a long, frame-rate-dependent intro.
            count = max(0, int((seconds - reveal - i * .065) * 85))
            text(line[:count], x, y + i * 19)

    def numbers(count, seed):
        return [f"{(seed + i * 739 + tick * 13) % 100000:05d} "
                f"{(463 + i * 37 + tick * 3) % 1000:03d} "
                f"{(10 + i * 9 + tick) % 100:02d}" for i in range(count)]

    phase = int(seconds / 2.6) % 3
    if phase == 0:
        block(['ANALYSIS:  MATCH:', '******************',
               '300 VEHI   86976', '680 SIZE   33022',
               '900 TSPD   33022', '017 V-PWR  13044',
               '106 GODE   20073', '708 HNGE   20667',
               '090 CAPC   12447', '770 MAX:   14036',
               '000 TORQ   00024', '740 SUSP   33974',
               '110 IDLE   00006', '640 WGHT   70000',
               '800 TANK   34767', '', 'ASSESS: SUITABLE'], margin, top)
        block(['SCAN MODE LEVEL 41', 'TARGET ASSESSMENT'], right, top, .2)
    elif phase == 1:
        block(['SCAN LEVELS:', '***************'] + numbers(7, 23464), margin, top)
        block(['SEARCH CRITERIA', 'MATCH MODE 6408', '', 'ALL LEVELS OPERATIVE'],
              margin, canvas_h - 130)
        block(['SYSTEM STATUS', 'OPTICAL ARRAY: ACTIVE'] + numbers(3, 65432), right, top)
        block(['THREAT ASSESSMENT', 'ANALYSIS IN PROGRESS'], right, canvas_h - 90)
    else:
        block(['MAINTENANCE', 'PORT 4867-F', '', 'ADDRESS', 'CHECKSUM', 'VERIFIED', '']
              + numbers(5, 48764), margin, top)
        block(['INTERNAL CHRONOMETER', f'{seconds:010.3f}'], right, canvas_h - 70)

    # Fine acquisition marks follow scene features, appearing only during a scan.
    cx = int(target[0] / width * canvas_w)
    cy = int(target[1] / height * canvas_h)
    if .45 < seconds % 2.6 < 1.95:
        radius, arm = 31, 11
        for dx in (-1, 1):
            for dy in (-1, 1):
                x, y = cx + dx * radius, cy + dy * radius
                cv2.line(overlay, (x, y), (x - dx * arm, y), WHITE, 1)
                cv2.line(overlay, (x, y), (x, y - dy * arm), WHITE, 1)
        cv2.line(overlay, (cx - 7, cy), (cx + 7, cy), WHITE, 1)
        cv2.line(overlay, (cx, cy - 7), (cx, cy + 7), WHITE, 1)
    if phase == 2:
        gx, gy, gw, gh = canvas_w - 190, top - 20, 160, 112
        for x in range(gx, gx + gw + 1, 10):
            cv2.line(overlay, (x, gy), (x, gy + gh), WHITE, 1)
        for y in range(gy, gy + gh + 1, 8):
            cv2.line(overlay, (gx, y), (gx + gw, y), WHITE, 1)

    # A restrained phosphor halo softens the digital typography.
    glow = cv2.GaussianBlur(overlay, (5, 5), 1.1)
    overlay = cv2.addWeighted(overlay, 1.0, glow, .25, 0)
    overlay = cv2.resize(overlay, (width, height), interpolation=cv2.INTER_LINEAR)
    result = np.maximum(tinted, overlay)
    step = max(2, round(height / 360))
    result[::step] = (result[::step].astype(np.uint16) * 97 // 100).astype(np.uint8)
    return result


def render_video():
    global w, h, fps
    cap = cv2.VideoCapture(INPUT)
    if not cap.isOpened():
        raise RuntimeError(f"No se pudo abrir el video: {INPUT}")
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    out = cv2.VideoWriter(TEMP_VIDEO, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    if not out.isOpened():
        cap.release()
        raise RuntimeError(f"No se pudo crear el video temporal: {TEMP_VIDEO}")
    start = time.time()
    frame_id = 0
    tracker = SceneTracker()
    try:
        while MAX_FRAMES is None or frame_id < MAX_FRAMES:
            ret, frame = cap.read()
            if not ret:
                break
            out.write(draw_hud(frame, frame_id, tracker.update(frame)))
            frame_id += 1
            if frame_id % 100 == 0:
                print(f"{frame_id}/{total} frames", flush=True)
    finally:
        cap.release()
        out.release()

    print("Añadiendo audio...", flush=True)
    with VideoFileClip(TEMP_VIDEO) as video, AudioFileClip(SFX) as source_audio:
        repeats = max(1, int(np.ceil(video.duration / source_audio.duration)))
        audio = concatenate_audioclips([source_audio] * repeats).subclipped(0, video.duration)
        final = video.with_audio(audio)
        try:
            final.write_videofile(OUTPUT, codec="libx264", audio_codec="aac", fps=fps,
                                 logger=None)
        finally:
            final.close()
            audio.close()
    print(f"Video generado: {OUTPUT} | {frame_id} frames | {time.time() - start:.1f}s")


if __name__ == "__main__":
    render_video()
