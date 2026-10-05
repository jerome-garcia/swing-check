"""FrameReader: frames from several videos at once, with videos closed under it."""

import shutil
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest

from swingcheck.app.frames import FrameReader
from swingcheck.output.video import VideoWriter

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")


@pytest.fixture
def videos(tmp_path):
    paths = []
    for n in range(3):
        path = tmp_path / f"v{n}.mp4"
        with VideoWriter(path, 64, 48, 30.0) as w:
            for _ in range(20):
                w.write(np.full((48, 64, 3), n * 80, np.uint8))
        paths.append(path)
    return paths


def brightness(jpeg: bytes) -> float:
    import cv2
    return float(cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_GRAYSCALE).mean())


def test_reads_the_right_video_from_many_threads(videos):
    # Fewer open slots than videos, so videos are closed and reopened while others read.
    reader = FrameReader(max_open=2)
    jobs = [(n, i) for i in range(20) for n in range(3)] * 3
    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(lambda job: (job[0], brightness(reader.jpeg(videos[job[0]], job[1]))), jobs))
    for n, b in results:
        assert abs(b - n * 80) < 6, (n, b)


def test_forget_and_missing_frames(videos):
    reader = FrameReader()
    assert reader.jpeg(videos[0], 3)[:2] == b"\xff\xd8"
    reader.forget(videos[0])
    assert reader.jpeg(videos[0], 4)[:2] == b"\xff\xd8"  # reopens
    with pytest.raises(IndexError):
        reader.jpeg(videos[0], 999)
