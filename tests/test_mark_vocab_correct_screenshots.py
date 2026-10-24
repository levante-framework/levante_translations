#!/usr/bin/env python3
"""Offline check that the acorn card border turns green and the original stays put."""

import os
import sys
import tempfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utilities.mark_vocab_correct_screenshots import (
    cache_vocab_assets,
    find_card_frames,
    mark_screenshot,
    quadrant_name,
    save_original_once,
)

LEVANTE_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = LEVANTE_ROOT / "crowdin-projects" / "debug_vocab_004_full.png"
ASSET_WORDS = ("acorn", "coconut", "key", "clothesline")
GREEN = (0, 255, 0)


def _green_count(image: Image.Image, box: tuple[int, int, int, int], pad: int = 4) -> int:
    x0, y0, x1, y1 = box
    pixels = image.load()
    width, height = image.size
    count = 0
    for y in range(max(0, y0 - pad), min(height, y1 + 1 + pad)):
        for x in range(max(0, x0 - pad), min(width, x1 + 1 + pad)):
            if pixels[x, y] == GREEN:
                count += 1
    return count


def test_acorn_border_turns_green_and_original_is_kept() -> None:
    assert FIXTURE.exists(), f"missing fixture {FIXTURE}"
    original_bytes = FIXTURE.read_bytes()
    with tempfile.TemporaryDirectory() as tmp:
        images = Path(tmp) / "images"
        missing = cache_vocab_assets(ASSET_WORDS, images)
        assert not missing, f"missing bucket images: {missing}"
        original = Path(tmp) / "originals" / "2756_vocab-004.png"
        save_original_once(original, original_bytes)
        save_original_once(original, b"do-not-overwrite")
        assert original.read_bytes() == original_bytes

        with Image.open(original) as image:
            source = image.convert("RGB").copy()
        marked, info = mark_screenshot(source, "acorn", ["coconut", "key", "clothesline"], images)
        assert original.read_bytes() == original_bytes
        assert info["quadrant"] == "bottom-right"
        assert float(info["match_margin"]) > 15
        assert marked.size == source.size

        frames = find_card_frames(source)
        assert len(frames) == 4
        counts = {
            quadrant_name(card, frames): _green_count(marked, (card.x0, card.y0, card.x1, card.y1))
            for card in frames
        }
        assert counts["bottom-right"] > 1000
        for name in ("top-left", "top-right", "bottom-left"):
            assert counts[name] == 0, f"{name} gained green pixels: {counts[name]}"


def main() -> int:
    try:
        test_acorn_border_turns_green_and_original_is_kept()
    except AssertionError as exc:
        print(f"FAIL: {exc}")
        return 1
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1
    print("PASS: vocab screenshot border")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
