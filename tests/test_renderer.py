import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import imageio_ffmpeg
import numpy as np

import t800


class RendererTests(unittest.TestCase):
    def setUp(self):
        self.settings = (t800.w, t800.h, t800.fps)

    def tearDown(self):
        t800.w, t800.h, t800.fps = self.settings

    def test_portrait_text_columns_do_not_overlap(self):
        calls = []

        def record(image, value, position, font, scale, color, thickness, line):
            width = cv2.getTextSize(value, font, scale, thickness)[0][0]
            calls.append((position, width))
            return image

        with patch.object(cv2, 'putText', side_effect=record):
            t800.draw_hud(np.zeros((720, 405, 3), np.uint8), 30, (202, 360))
        left, right = [call for call in calls if call[0][1] == 88]
        self.assertLess(left[0][0] + left[1], right[0][0])
        self.assertLessEqual(right[0][0] + right[1], 405)

    def test_tracking_smoothing_is_independent_of_fps(self):
        positions = []
        for rate in (25, 60):
            t800.w, t800.h, t800.fps = 320, 240, rate
            tracker = t800.SceneTracker()
            tracker.destination += (30, 0)
            frame = np.zeros((240, 320, 3), np.uint8)
            for _ in range(rate):
                tracker.update(frame)
            positions.append(tracker.position.copy())
        np.testing.assert_allclose(positions[0], positions[1], atol=0.001)

    def test_export_and_failed_read_preserve_previous_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audio = root / 'sound.wav'
            subprocess.run([
                imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-loglevel', 'error',
                '-f', 'lavfi', '-i', 'sine=frequency=440:duration=0.1', str(audio)
            ], check=True)
            for rate, size in ((25, (320, 240)), (60, (406, 720))):
                source, output = root / 'input.mp4', root / 'output.mp4'
                writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*'mp4v'), rate, size)
                self.assertTrue(writer.isOpened())
                for _ in range(12):
                    writer.write(np.full((size[1], size[0], 3), 100, np.uint8))
                writer.release()
                with patch.multiple(t800, INPUT=str(source), SFX=str(audio), OUTPUT=str(output), MAX_FRAMES=None):
                    t800.render_video()
                reader = cv2.VideoCapture(str(output))
                try:
                    self.assertEqual(int(reader.get(cv2.CAP_PROP_FRAME_COUNT)), 12)
                    self.assertAlmostEqual(reader.get(cv2.CAP_PROP_FPS), rate, places=2)
                    self.assertEqual(int(reader.get(cv2.CAP_PROP_FRAME_WIDTH)), size[0])
                finally:
                    reader.release()
                probe = subprocess.run([
                    imageio_ffmpeg.get_ffmpeg_exe(), '-i', str(output),
                    '-map', '0:a:0', '-f', 'null', '-'
                ], capture_output=True)
                self.assertEqual(probe.returncode, 0, probe.stderr.decode(errors='replace'))

            previous = output.read_bytes()
            real_capture = cv2.VideoCapture

            class FailedCapture:
                def __init__(self, filename):
                    self.capture = real_capture(filename)
                    self.count = 0

                def isOpened(self):
                    return self.capture.isOpened()

                def get(self, field):
                    return self.capture.get(field)

                def read(self):
                    self.count += 1
                    return self.capture.read() if self.count <= 3 else (False, None)

                def release(self):
                    self.capture.release()

            with patch.multiple(t800, INPUT=str(source), SFX=str(audio), OUTPUT=str(output), MAX_FRAMES=None):
                with patch.object(cv2, 'VideoCapture', FailedCapture):
                    with self.assertRaisesRegex(RuntimeError, 'Lectura interrumpida'):
                        t800.render_video()
            self.assertEqual(output.read_bytes(), previous)
            self.assertFalse(list(root.glob('t800-*')))


if __name__ == '__main__':
    unittest.main()
