"""Shared test fixtures."""

from swingcheck.ingest import VideoInfo


def make_info(**overrides) -> VideoInfo:
    fields = dict(
        source="x.mov", source_size=1, source_mtime=0.0, trim_start=None, trim_end=None,
        fps=240.0, width=1080, height=1920, rotation=90, frame_count=480, duration=2.0,
        source_codec="hevc", hdr=False, warnings=[],
    )
    fields.update(overrides)
    return VideoInfo(**fields)
