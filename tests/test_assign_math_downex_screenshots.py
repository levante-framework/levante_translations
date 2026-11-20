#!/usr/bin/env python3

import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utilities.assign_math_downex_screenshots import compose, image_keys, picture_items


def test_image_keys_put_the_correct_picture_first() -> None:
    assert image_keys("Counting", "3cars", "Correct", ["Correct", "Incorrect"]) == ["3cars"]
    assert image_keys(
        "Non-symbolic Number Identification",
        "",
        "6cans",
        ["7cans", "4cans"],
    ) == ["6cans", "7cans", "4cans"]


def test_picture_items_keep_downex_math_pictures_once() -> None:
    rows = [
        {
            "item_id": "counting-3",
            "audio_file": "counting-1",
            "item": "3cars",
            "answer": "Correct",
            "response_alternatives": "Correct,Incorrect",
            "trial_type": "Counting",
            "downex": "TRUE",
            "task": "math",
        },
        {
            "item_id": "counting-3",
            "audio_file": "counting-1",
            "item": "3cars",
            "answer": "Correct",
            "response_alternatives": "Correct,Incorrect",
            "trial_type": "Counting",
            "downex": True,
            "task": "math",
        },
        {
            "item_id": "num-comp-6",
            "audio_file": "number-comparison-prompt2",
            "trial_type": "Number Comparison",
            "downex": True,
            "task": "math",
        },
        {
            "item_id": "counting-vocab",
            "audio_file": "counting-1",
            "trial_type": "Counting",
            "downex": True,
            "task": "vocab",
        },
        {
            "item_id": "counting-main",
            "audio_file": "counting-1",
            "item": "3cars",
            "trial_type": "Counting",
            "downex": "",
            "task": "math",
        },
    ]
    items = picture_items(rows)
    assert [item["item_id"] for item in items] == ["counting-3"]
    assert items[0]["audio"] == "counting-1"


def test_compose_places_cards_in_a_row() -> None:
    left = Image.new("RGBA", (20, 40), (255, 0, 0, 255))
    right = Image.new("RGBA", (20, 40), (0, 0, 255, 255))
    canvas = compose([left, right])
    assert canvas.size == (16 * 2 + 180 + 180 + 16, 360 + 32)
    assert canvas.getpixel((16, 16)) == (255, 0, 0)
    assert canvas.getpixel((16 + 180 + 16, 16)) == (0, 0, 255)
