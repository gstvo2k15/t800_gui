import cv2
import numpy as np
import time
import math
import os
from pathlib import Path
import subprocess
import tempfile
import wave

import imageio_ffmpeg

INPUT = "input.mp4"
SFX = "t800_sfx.mp3"

OUTPUT = "t800_hud.mp4"

MAX_FRAMES = None
# MAX_FRAMES = 300

# Dimensions are configured by render_video; importing the renderer has no side effects.
w, h, fps = 1280, 720, 25.0
WHITE = (218, 235, 235)


def make_audio_loop(samples, sample_rate):
    """Find a steady interior bed and blend its ends into a periodic waveform."""
    if len(samples) < 4 or not np.isfinite(samples).all():
        raise ValueError("El audio no contiene suficientes muestras válidas")
    # Compare short blocks by loudness and spectral shape, preserving both channels.
    block_size = max(1, round(sample_rate * .1))
    count = len(samples) // block_size
    length = min(round(sample_rate * 5), len(samples))
    length_blocks = length // block_size
    start = 0
    if count >= 20:
        blocks = samples[:count * block_size].reshape(count, block_size, -1)
        power = np.mean(blocks ** 2, axis=(1, 2))
        loudness = 10 * np.log10(power + 1e-12)
        spectrum = np.mean(np.abs(np.fft.rfft(blocks, axis=1)) ** 2, axis=2)
        bands = np.array_split(spectrum, 12, axis=1)
        features = np.column_stack([np.sum(band, axis=1) for band in bands])
        features /= np.sum(features, axis=1, keepdims=True) + 1e-12
        # Exclude the attack and tail when there is enough material.
        margin = min(6, max(0, (count - length_blocks) // 2))
        audible = loudness > np.max(loudness) - 24
        best = float("inf")
        for first in range(margin, count - length_blocks - margin + 1):
            last = first + length_blocks
            if not np.all(audible[first:last]):
                continue
            level = loudness[first:last]
            shape = features[first:last]
            score = (np.std(level) + .5 * np.ptp(level)
                     + 20 * np.mean(np.std(shape, axis=0))
                     + 10 * np.linalg.norm(np.mean(shape[:3], axis=0)
                                           - np.mean(shape[-3:], axis=0)))
            if score < best:
                best, start = score, first * block_size
    end = start + length
    fragment = samples[start:end].astype(np.float32, copy=True)
    fade = min(round(sample_rate * .4), len(fragment) // 4)
    fade = max(1, fade)
    head, tail = fragment[:fade], fragment[-fade:]
    mix = np.linspace(0, 1, fade, dtype=np.float32)[:, None]
    # Compensate for the power dip of unrelated signals during the crossfade.
    denominator = np.sqrt(np.mean(head ** 2) * np.mean(tail ** 2))
    correlation = np.clip(np.mean(head * tail) / max(denominator, 1e-12), -.5, 1)
    gain = np.sqrt((1 - mix) ** 2 + mix ** 2 + 2 * correlation * mix * (1 - mix))
    join = ((1 - mix) * tail + mix * head) / gain
    loop = np.concatenate((fragment[fade:-fade], join))
    return loop, start, end


def prepare_audio_loop(source, destination):
    """Decode once; repeat a PCM loop without MP3 encoder padding or restarts."""
    sample_rate = 48000
    decoded = subprocess.run([
        imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-i", str(source),
        "-vn", "-ar", str(sample_rate), "-ac", "2", "-f", "f32le", "pipe:1",
    ], capture_output=True, creationflags=(
        subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    ))
    if decoded.returncode:
        raise RuntimeError("No se pudo decodificar el audio: "
                           + decoded.stderr.decode("utf-8", errors="replace"))
    samples = np.frombuffer(decoded.stdout, dtype="<f4").reshape(-1, 2)
    loop, first, last = make_audio_loop(samples, sample_rate)
    with wave.open(str(destination), "wb") as audio:
        audio.setnchannels(2)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes((np.clip(loop, -1, 1) * 32767).astype("<i2").tobytes())
    print(f"Audio estable: {first / sample_rate:.2f}–{last / sample_rate:.2f}s "
          f"| bucle con fundido: {len(loop) / sample_rate:.2f}s", flush=True)


class SceneTracker:
    """Keep the sight on a patch of the scene instead of animating it."""

    def __init__(self):
        self.position = np.array([w * 0.5, h * 0.5], dtype=np.float32)
        self.destination = self.position.copy()
        self.previous = None
        self.points = None
        self.age = 0
        self.scan_period = None
        self.refresh_period = None

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
        scan_period = int((self.age - 1) / fps)
        if scan_period != self.scan_period:
            self.scan_period = scan_period
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
                    choice = eligible[scan_period % len(eligible)]
                    self.destination = locations[choice].astype(np.float32)
                    self.points = None

        margin = min(w, h) * 0.13
        self.destination = np.clip(self.destination, [margin, margin], [w - margin, h - margin])
        smoothing = 1 - (1 - 0.065) ** (25 / fps)
        self.position += (self.destination - self.position) * smoothing
        refresh_period = int((self.age - 1) / fps / (24 / 25))
        if self.points is None or len(self.points) < 12 or refresh_period != self.refresh_period:
            self.refresh_period = refresh_period
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
    red = np.clip((levels - .015) / .985, 0, 1) ** .9
    highlights = np.clip((levels - .56) / .40, 0, 1) ** 1.5
    lut = np.stack((highlights * 210, highlights * 225, red * 255), axis=1)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    tinted = lut.astype(np.uint8)[gray]

    # A fixed design space keeps the lettering legible at every output resolution.
    canvas_h = 720
    canvas_w = round(width / height * canvas_h)
    overlay = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
    layout_scale = min(1.0, canvas_w / 720)
    margin = round(24 * layout_scale)
    top = 88
    right = canvas_w - round(310 * layout_scale)
    tick = int(seconds * 8)

    def text(value, x, y, scale=.58):
        cv2.putText(overlay, value, (int(x), int(y)), cv2.FONT_HERSHEY_DUPLEX,
                    scale * layout_scale, WHITE, 1, cv2.LINE_AA)

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
        gw, gh = round(160 * layout_scale), 112
        gx, gy = canvas_w - round(190 * layout_scale), top - 20
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
    """Stream BGR frames to FFmpeg and publish only a complete export."""
    global w, h, fps
    cap = cv2.VideoCapture(INPUT)
    start = time.monotonic()
    frame_id = 0
    try:
        if not cap.isOpened():
            raise RuntimeError(f"No se pudo abrir el video: {INPUT}")
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        if w <= 0 or h <= 0 or not math.isfinite(fps) or fps <= 0:
            raise RuntimeError("El video tiene dimensiones o FPS inválidos")
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if MAX_FRAMES is not None and MAX_FRAMES <= 0:
            raise ValueError("MAX_FRAMES debe ser positivo")
        if not Path(SFX).is_file():
            raise RuntimeError(f"No se encontró el audio: {SFX}")
        output = Path(OUTPUT).resolve()
        tracker = SceneTracker()
        # Stage beside the destination so replacement stays on the same filesystem.
        with tempfile.TemporaryDirectory(prefix="t800-", dir=output.parent) as folder:
            staged = Path(folder) / "render.mp4"
            soundtrack = Path(folder) / "loop.wav"
            prepare_audio_loop(Path(SFX).resolve(), soundtrack)
            command = [
                imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
                "-f", "rawvideo", "-pixel_format", "bgr24",
                "-video_size", f"{w}x{h}", "-framerate", str(fps), "-i", "pipe:0",
                "-stream_loop", "-1", "-i", str(soundtrack),
                "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264",
                "-preset", "slow", "-crf", "14",
                "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "256k", "-shortest",
                "-movflags", "+faststart", str(staged),
            ]
            with tempfile.TemporaryFile() as errors:
                process = subprocess.Popen(
                    command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                    stderr=errors,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                try:
                    while MAX_FRAMES is None or frame_id < MAX_FRAMES:
                        ret, frame = cap.read()
                        if not ret:
                            if frame_id == 0:
                                raise RuntimeError("No se pudo leer ningún fotograma")
                            if total > 0 and frame_id < total:
                                raise RuntimeError(
                                    f"Lectura interrumpida: {frame_id}/{total} fotogramas"
                                )
                            break
                        rendered = draw_hud(frame, frame_id, tracker.update(frame))
                        process.stdin.write(rendered.tobytes())
                        frame_id += 1
                        if frame_id % 100 == 0:
                            print(f"{frame_id}/{total} frames", flush=True)
                    process.stdin.close()
                    returncode = process.wait()
                    if returncode:
                        errors.seek(0)
                        raise RuntimeError(
                            "FFmpeg no pudo exportar el video: "
                            + errors.read().decode("utf-8", errors="replace")
                        )
                except BaseException:
                    if process.poll() is None:
                        process.terminate()
                    process.wait()
                    if not process.stdin.closed:
                        try:
                            process.stdin.close()
                        except BrokenPipeError:
                            pass
                    raise
            staged.replace(output)
    finally:
        cap.release()
    print(f"Video generado: {OUTPUT} | {frame_id} frames | {time.monotonic() - start:.1f}s")


if __name__ == "__main__":
    render_video()
