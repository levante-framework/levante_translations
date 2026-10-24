#!/usr/bin/env python3
"""Mark the correct vocab picture on Crowdin screenshots.

Downloads vocab-NNN.png screenshots, keeps a local original, recolors the
border of the correct card bright green, and optionally replaces the same
Crowdin screenshot in place.

The screenshot filename is not the item id. Tags point at string identifiers
such as vocab-item-001. The corpus `answer` for that audio file is the English
image name, and the 2x2 grid is shuffled, so the correct card is chosen by
comparing each card to the source photos.

Usage:
  python utilities/mark_vocab_correct_screenshots.py
  python utilities/mark_vocab_correct_screenshots.py --items vocab-item-001 --limit 1
  python utilities/mark_vocab_correct_screenshots.py --upload
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROJECT_ID = os.environ.get("CROWDIN_PROJECT_ID", "756721")
DEFAULT_CORPUS = (
    REPO_ROOT.parent
    / "levante-qa"
    / "tools"
    / "vlm-panel"
    / "corpora"
    / "vocab"
    / "vocab-item-bank-en-US.csv"
)
DEFAULT_OUTPUT = REPO_ROOT / "translation_grading" / "output" / "vocab_correct_screenshots"
DEFAULT_IMAGES = DEFAULT_OUTPUT / "source_images"
ASSET_BUCKET = "levante-assets-dev"
ASSET_PREFIX = "visual/vocab/"
VOCAB_SCREENSHOT_RE = re.compile(r"^vocab-\d+\.png$", re.IGNORECASE)
GREEN = (0, 255, 0)
THUMB = 24


@dataclass
class CardFrame:
    x0: int
    y0: int
    x1: int
    y1: int
    pixels: list[tuple[int, int]]

    @property
    def width(self) -> int:
        return self.x1 - self.x0 + 1

    @property
    def height(self) -> int:
        return self.y1 - self.y0 + 1

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def area(self) -> int:
        return len(self.pixels)


def get_token() -> str:
    token = os.environ.get("CROWDIN_API_TOKEN", "").strip() or os.environ.get("CROWDIN_TOKEN", "").strip()
    if token:
        return token
    token_path = Path.home() / ".crowdin_api_token"
    if token_path.exists():
        return token_path.read_text(encoding="utf-8").strip()
    raise RuntimeError("Crowdin token not found. Set CROWDIN_API_TOKEN or create ~/.crowdin_api_token.")


def crowdin_client(project_id: str):
    from crowdin_api import CrowdinClient

    return CrowdinClient(token=get_token(), project_id=int(project_id))


def load_corpus(path: Path) -> dict[str, dict[str, object]]:
    """Map audio_file (vocab-item-NNN) to answer and distractor words."""
    items: dict[str, dict[str, object]] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            audio = str(row.get("audio_file") or "").strip()
            answer = str(row.get("answer") or "").strip()
            if not audio or not answer:
                continue
            distractors = [
                part.strip()
                for part in str(row.get("response_alternatives") or "").split(",")
                if part.strip()
            ]
            items[audio] = {"answer": answer, "distractors": distractors}
    return items


def save_original_once(path: Path, data: bytes) -> None:
    if path.exists() and path.stat().st_size > 0:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def replace_original_if_changed(path: Path, data: bytes) -> str:
    """Save a Crowdin screenshot, keeping the first local copy if a later download differs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.stat().st_size == 0:
        path.write_bytes(data)
        return "downloaded"
    if path.read_bytes() == data:
        return "unchanged"
    previous = path.parent / "previous" / path.name
    if not previous.exists() or previous.stat().st_size == 0:
        previous.parent.mkdir(parents=True, exist_ok=True)
        previous.write_bytes(path.read_bytes())
    path.write_bytes(data)
    return "updated"


def _is_border_pixel(r: int, g: int, b: int) -> bool:
    return b > 140 and b > r + 60 and b > g + 40 and r < 140


def _is_blue_tint(r: int, g: int, b: int) -> bool:
    return b > r + 20 and b > 90 and r < 180


def find_card_frames(image: Image.Image) -> list[CardFrame]:
    """Return the four large blue card borders, ignoring the speaker button."""
    rgb = image.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()
    mask = bytearray(width * height)
    for y in range(height):
        row = y * width
        for x in range(width):
            if _is_border_pixel(*pixels[x, y]):
                mask[row + x] = 1

    raw_components = _connected_frames(mask, mask, width, height, eight=False)
    frames = _similar_frames(raw_components)
    if len(frames) >= 4:
        return frames
    grown = _dilate_mask(mask, width, height)
    frames = _similar_frames(_connected_frames(mask, grown, width, height, eight=True))
    if len(frames) >= 4:
        return frames
    frames = _frames_from_grid(mask, width, height)
    if len(frames) >= 4:
        return frames
    return _infer_fourth_card(raw_components, mask, width, height)


def _dilate_mask(mask: bytearray, width: int, height: int) -> bytearray:
    grown = bytearray(mask)
    for y in range(height):
        row = y * width
        for x in range(width):
            if not mask[row + x]:
                continue
            for dy in (-1, 0, 1):
                ny = y + dy
                if ny < 0 or ny >= height:
                    continue
                for dx in (-1, 0, 1):
                    nx = x + dx
                    if 0 <= nx < width:
                        grown[ny * width + nx] = 1
    return grown


def _connected_frames(
    mask: bytearray,
    walk: bytearray,
    width: int,
    height: int,
    *,
    eight: bool,
) -> list[CardFrame]:
    steps = ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1))
    if not eight:
        steps = steps[:4]
    seen = bytearray(width * height)
    components: list[CardFrame] = []
    for y in range(height):
        row = y * width
        for x in range(width):
            start = row + x
            if not walk[start] or seen[start]:
                continue
            stack = [start]
            seen[start] = 1
            coords: list[tuple[int, int]] = []
            min_x = max_x = x
            min_y = max_y = y
            while stack:
                index = stack.pop()
                cx, cy = index % width, index // width
                if mask[index]:
                    coords.append((cx, cy))
                    if cx < min_x:
                        min_x = cx
                    if cx > max_x:
                        max_x = cx
                    if cy < min_y:
                        min_y = cy
                    if cy > max_y:
                        max_y = cy
                for dx, dy in steps:
                    nx = cx + dx
                    ny = cy + dy
                    if nx < 0 or ny < 0 or nx >= width or ny >= height:
                        continue
                    neighbor = ny * width + nx
                    if seen[neighbor] or not walk[neighbor]:
                        continue
                    seen[neighbor] = 1
                    stack.append(neighbor)
            if coords:
                components.append(CardFrame(min_x, min_y, max_x, max_y, coords))
    return components


def _infer_fourth_card(
    components: Sequence[CardFrame],
    mask: bytearray,
    width: int,
    height: int,
) -> list[CardFrame]:
    """Rebuild a card whose border was swallowed by a blue object inside the photo."""
    rings = []
    for card in components:
        if min(card.width, card.height) < 80:
            continue
        if card.area > 0.35 * card.width * card.height:
            continue
        rings.append(card)
    rings.sort(key=lambda card: card.area, reverse=True)
    if not rings:
        return []
    ref = rings[0]
    rings = [
        card
        for card in rings
        if abs(card.width - ref.width) <= ref.width * 0.25 and abs(card.height - ref.height) <= ref.height * 0.25
    ][:3]
    if len(rings) < 3:
        return []
    tolerance = max(ref.width, ref.height) * 0.2

    def centers(values: list[float]) -> list[float]:
        groups: list[list[float]] = []
        for value in sorted(values):
            if not groups or abs(value - groups[-1][0]) > tolerance:
                groups.append([value])
            else:
                groups[-1].append(value)
        return [sum(group) / len(group) for group in groups]

    xs = centers([card.cx for card in rings])
    ys = centers([card.cy for card in rings])
    if len(xs) != 2 or len(ys) != 2:
        return []

    def nearest(value: float, options: list[float]) -> float:
        return min(options, key=lambda option: abs(option - value))

    occupied = {(nearest(card.cx, xs), nearest(card.cy, ys)) for card in rings}
    missing = [(x, y) for x in xs for y in ys if (x, y) not in occupied]
    if len(missing) != 1:
        return []
    center_x, center_y = missing[0]
    card_w = int(round(sum(card.width for card in rings) / len(rings)))
    card_h = int(round(sum(card.height for card in rings) / len(rings)))
    x0 = int(round(center_x - card_w / 2))
    y0 = int(round(center_y - card_h / 2))
    x1 = x0 + card_w - 1
    y1 = y0 + card_h - 1
    edge = 12
    coords = []
    for y in range(max(0, y0), min(height, y1 + 1)):
        row = y * width
        for x in range(max(0, x0), min(width, x1 + 1)):
            if not mask[row + x]:
                continue
            if x <= x0 + edge or x >= x1 - edge or y <= y0 + edge or y >= y1 - edge:
                coords.append((x, y))
    if len(coords) < 80:
        return []
    return [*rings, CardFrame(x0, y0, x1, y1, coords)]


def _similar_frames(components: Sequence[CardFrame]) -> list[CardFrame]:
    large = [card for card in components if min(card.width, card.height) >= 80]
    large.sort(key=lambda card: card.area, reverse=True)
    if not large:
        return []
    ref_w = large[0].width
    ref_h = large[0].height
    similar = [
        card
        for card in large
        if abs(card.width - ref_w) <= ref_w * 0.25 and abs(card.height - ref_h) <= ref_h * 0.25
    ]
    return similar[:4] if len(similar) >= 4 else []


def _low_band_split(counts: Sequence[int]) -> int | None:
    """Index of the gap between two peaks, looking at the middle of the image."""
    total = len(counts)
    if total < 40:
        return None
    start = total // 5
    end = total * 4 // 5
    window = 8
    best_at = None
    best_value = None
    for index in range(start, end - window):
        value = sum(counts[index : index + window])
        if best_value is None or value < best_value:
            best_value = value
            best_at = index + window // 2
    return best_at


def _frames_from_grid(mask: bytearray, width: int, height: int) -> list[CardFrame]:
    """Four card borders from the gaps in a 2x2 grid.

    Used when a thin or photo-colored border does not stay one connected ring.
    Only pixels near each card's edge are kept, so a blue photo is not recolored.
    """
    columns = [0] * width
    rows = [0] * height
    for y in range(height):
        row = y * width
        for x in range(width):
            if mask[row + x]:
                columns[x] += 1
                rows[y] += 1
    split_x = _low_band_split(columns)
    split_y = _low_band_split(rows)
    if split_x is None or split_y is None:
        return []
    regions = (
        (0, 0, split_x, split_y),
        (split_x, 0, width, split_y),
        (0, split_y, split_x, height),
        (split_x, split_y, width, height),
    )
    frames: list[CardFrame] = []
    for x0, y0, x1, y1 in regions:
        coords = [
            (x, y)
            for y in range(y0, y1)
            for x in range(x0, x1)
            if mask[y * width + x]
        ]
        if len(coords) < 80:
            return []
        min_x = min(x for x, _y in coords)
        max_x = max(x for x, _y in coords)
        min_y = min(y for _x, y in coords)
        max_y = max(y for _x, y in coords)
        if min(max_x - min_x, max_y - min_y) < 80:
            return []
        edge = 10
        ring = [
            (x, y)
            for x, y in coords
            if x <= min_x + edge or x >= max_x - edge or y <= min_y + edge or y >= max_y - edge
        ]
        if len(ring) < 80:
            return []
        frames.append(CardFrame(min_x, min_y, max_x, max_y, ring))
    return frames


def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2


def quadrant_name(card: CardFrame, cards: Sequence[CardFrame]) -> str:
    mid_x = _median([item.cx for item in cards])
    mid_y = _median([item.cy for item in cards])
    vertical = "top" if card.cy < mid_y else "bottom"
    horizontal = "left" if card.cx < mid_x else "right"
    return f"{vertical}-{horizontal}"


def camelize(text: str) -> str:
    """Match core-tasks camelize: 'rubber band' -> 'rubberBand'."""

    def replace(match: re.Match) -> str:
        if match.group(2):
            return match.group(2).upper()
        return match.group(1).lower()

    return re.sub(r"^([A-Z])|[\s\-_](\w)", replace, text)


def image_dirs(images_dir: Path | Sequence[Path]) -> list[Path]:
    if isinstance(images_dir, Path):
        return [images_dir]
    return [path for path in images_dir if path]


def source_image_path(images_dir: Path | Sequence[Path], word: str) -> Path | None:
    stems = []
    for stem in (word, camelize(word), re.sub(r"[\s\-_]+", "", word)):
        if stem and stem not in stems:
            stems.append(stem)
    for directory in image_dirs(images_dir):
        for stem in stems:
            for ext in (".webp", ".jpg", ".jpeg", ".png"):
                candidate = directory / f"{stem}{ext}"
                if candidate.exists():
                    return candidate
        wanted = set(_name_keys(word))
        ranked = []
        if directory.exists():
            for candidate in directory.iterdir():
                if candidate.suffix.lower() not in {".webp", ".jpg", ".jpeg", ".png"}:
                    continue
                if wanted.intersection(_name_keys(candidate.stem)):
                    ranked.append(candidate)
        if ranked:
            ranked.sort(key=lambda path: {".webp": 0, ".png": 1, ".jpg": 2, ".jpeg": 3}[path.suffix.lower()])
            return ranked[0]
    return None


def _name_keys(stem: str) -> list[str]:
    keys = []
    for value in (stem, camelize(stem), re.sub(r"[\s\-_]+", "", stem)):
        key = value.lower()
        if key and key not in keys:
            keys.append(key)
    return keys


def list_vocab_asset_names() -> dict[str, str]:
    """Map a normalized word to its filename in levante-assets-dev. Webp wins."""
    names: dict[str, str] = {}
    rank = {".webp": 0, ".png": 1, ".jpg": 2, ".jpeg": 3}
    page_token = None
    while True:
        query = f"prefix={urllib.parse.quote(ASSET_PREFIX)}&maxResults=1000&fields=items(name),nextPageToken"
        if page_token:
            query += "&pageToken=" + urllib.parse.quote(page_token)
        url = f"https://storage.googleapis.com/storage/v1/b/{ASSET_BUCKET}/o?{query}"
        with urllib.request.urlopen(url, timeout=60) as response:
            payload = json.load(response)
        for item in payload.get("items") or []:
            filename = str(item.get("name") or "").rsplit("/", 1)[-1]
            suffix = Path(filename).suffix.lower()
            if not filename or suffix not in rank:
                continue
            for key in _name_keys(Path(filename).stem):
                current = names.get(key)
                if current is None or rank[suffix] < rank[Path(current).suffix.lower()]:
                    names[key] = filename
        page_token = payload.get("nextPageToken")
        if not page_token:
            break
    return names


def cache_vocab_assets(words: Iterable[str], cache_dir: Path) -> list[str]:
    """Save the latest levante-assets-dev vocab photo for each word into cache_dir."""
    index = list_vocab_asset_names()
    cache_dir.mkdir(parents=True, exist_ok=True)
    missing = []
    updated = 0
    for word in sorted({part.strip() for part in words if part and part.strip()}):
        filename = next((index[key] for key in _name_keys(word) if key in index), None)
        if filename is None:
            missing.append(word)
            continue
        destination = cache_dir / filename
        url = f"https://storage.googleapis.com/{ASSET_BUCKET}/{ASSET_PREFIX}{urllib.parse.quote(filename)}"
        data = download_bytes(url)
        if not destination.exists() or destination.read_bytes() != data:
            destination.write_bytes(data)
            updated += 1
    print(f"Vocab assets from {ASSET_BUCKET}: {updated} updated, {len(missing)} missing.")
    if missing:
        print("Missing asset words: " + ", ".join(missing))
    return missing


def _thumb_from_image(image: Image.Image) -> list[tuple[int, int, int]]:
    resized = image.convert("RGB").resize((THUMB, THUMB), Image.Resampling.BILINEAR)
    return list(resized.getdata())


def _card_thumb(image: Image.Image, card: CardFrame) -> list[tuple[int, int, int]]:
    inset = max(4, min(16, card.width // 16))
    crop = image.crop((card.x0 + inset, card.y0 + inset, card.x1 + 1 - inset, card.y1 + 1 - inset))
    return _thumb_from_image(crop)


def _mean_abs(left: Sequence[tuple[int, int, int]], right: Sequence[tuple[int, int, int]]) -> float:
    total = 0
    for a, b in zip(left, right):
        total += abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])
    return total / (len(left) * 3)


def mark_screenshot(
    image: Image.Image,
    answer: str,
    distractors: Sequence[str],
    images_dir: Path | Sequence[Path],
) -> tuple[Image.Image, dict[str, object]]:
    """Recolor the correct card border. Does not modify `image`."""
    cards = find_card_frames(image)
    if len(cards) != 4:
        raise ValueError(f"expected 4 card borders, found {len(cards)}")

    words = [answer, *distractors]
    thumbs: dict[str, list[tuple[int, int, int]]] = {}
    missing = []
    for word in words:
        path = source_image_path(images_dir, word)
        if path is None:
            missing.append(word)
            continue
        with Image.open(path) as source:
            thumbs[word] = _thumb_from_image(source)
    if missing:
        raise ValueError(f"missing source images: {', '.join(missing)}")
    if answer not in thumbs:
        raise ValueError(f"missing source image for {answer}")

    winners = []
    for card in cards:
        card_thumb = _card_thumb(image, card)
        scores = sorted((_mean_abs(card_thumb, thumbs[word]), word) for word in thumbs)
        best_score, best_word = scores[0]
        second_score = scores[1][0] if len(scores) > 1 else best_score
        if best_word == answer:
            winners.append((card, best_score, second_score - best_score, quadrant_name(card, cards)))

    if len(winners) > 1:
        winners.sort(key=lambda item: item[1])
        best_score = winners[0][1]
        runner_score = winners[1][1]
        if runner_score - best_score < 20:
            raise ValueError(f"answer {answer} matched {len(winners)} cards")
        winners = winners[:1]
    if len(winners) != 1:
        raise ValueError(f"answer {answer} matched {len(winners)} cards")

    card, _score, margin, quadrant = winners[0]
    marked = recolor_border(image, card.pixels)
    return marked, {
        "answer": answer,
        "quadrant": quadrant,
        "match_margin": round(margin, 2),
    }


def _in_rounded_rect(x: int, y: int, x0: int, y0: int, x1: int, y1: int, radius: int) -> bool:
    if x < x0 or y < y0 or x > x1 or y > y1:
        return False
    radius = max(0, min(radius, (x1 - x0) // 2, (y1 - y0) // 2))
    if radius <= 0:
        return True
    cx = x0 + radius if x < x0 + radius else x1 - radius if x > x1 - radius else x
    cy = y0 + radius if y < y0 + radius else y1 - radius if y > y1 - radius else y
    dx, dy = x - cx, y - cy
    return dx * dx + dy * dy <= radius * radius


def _corner_radius(target, x0: int, y0: int, x1: int, y1: int) -> int:
    """How far the straight border starts in from each corner of the card box."""
    insets = []
    probes = (
        ((x, y0) for x in range(x0, x1 + 1)),
        ((x, y0) for x in range(x1, x0 - 1, -1)),
        ((x, y1) for x in range(x0, x1 + 1)),
        ((x, y1) for x in range(x1, x0 - 1, -1)),
        ((x0, y) for y in range(y0, y1 + 1)),
        ((x0, y) for y in range(y1, y0 - 1, -1)),
        ((x1, y) for y in range(y0, y1 + 1)),
        ((x1, y) for y in range(y1, y0 - 1, -1)),
    )
    for points in probes:
        for step, (x, y) in enumerate(points):
            if _is_border_pixel(*target[x, y]):
                insets.append(step)
                break
    if not insets:
        return 16
    insets.sort()
    return insets[len(insets) // 2]


def recolor_border(image: Image.Image, pixels: Iterable[tuple[int, int]], radius: int = 2) -> Image.Image:
    """Paint a rounded green stroke on the card border, leaving the photo alone."""
    marked = image.convert("RGB").copy()
    target = marked.load()
    width, height = marked.size
    core = list(pixels)
    if not core:
        return marked
    x0 = min(x for x, _y in core)
    x1 = max(x for x, _y in core)
    y0 = min(y for _x, y in core)
    y1 = max(y for _x, y in core)
    corner = _corner_radius(target, x0, y0, x1, y1)
    stroke = 5
    fringe = 4
    for y in range(max(0, y0 - fringe), min(height, y1 + fringe + 1)):
        for x in range(max(0, x0 - fringe), min(width, x1 + fringe + 1)):
            outer = _in_rounded_rect(x, y, x0, y0, x1, y1, corner)
            inner = _in_rounded_rect(x, y, x0 + stroke, y0 + stroke, x1 - stroke, y1 - stroke, corner - stroke)
            if outer and not inner:
                target[x, y] = GREEN
                continue
            if outer or inner:
                continue
            if _in_rounded_rect(x, y, x0 - fringe, y0 - fringe, x1 + fringe, y1 + fringe, corner + fringe) and _is_blue_tint(*target[x, y]):
                target[x, y] = GREEN
    return marked


def _unwrap_rows(payload: dict) -> list[dict]:
    rows = []
    for row in payload.get("data") or []:
        if isinstance(row, dict) and isinstance(row.get("data"), dict):
            rows.append(row["data"])
        elif isinstance(row, dict):
            rows.append(row)
    return rows


def _iter_pages(fetch, limit: int = 500):
    offset = 0
    while True:
        payload = fetch(limit=limit, offset=offset)
        rows = _unwrap_rows(payload)
        yield from rows
        page = payload.get("data") or []
        if len(page) < limit:
            break
        offset += limit


def _screenshot_tags(client, screenshot: dict) -> list[dict]:
    raw_tags = screenshot.get("tags")
    tags_count = int(screenshot.get("tagsCount") or 0)
    if isinstance(raw_tags, list) and (raw_tags or tags_count == 0):
        tags = []
        for tag in raw_tags:
            if isinstance(tag, dict) and isinstance(tag.get("data"), dict):
                tags.append(tag["data"])
            elif isinstance(tag, dict):
                tags.append(tag)
        return tags
    payload = client.screenshots.list_tags(screenshotId=int(screenshot["id"]), limit=100, offset=0)
    return _unwrap_rows(payload)


def _tag_requests(tags: Sequence[dict]) -> list[dict]:
    requests = []
    seen = set()
    for tag in tags:
        string_id = tag.get("stringId")
        if string_id is None or string_id in seen:
            continue
        seen.add(string_id)
        request: dict[str, object] = {"stringId": int(string_id)}
        position = tag.get("position")
        if isinstance(position, dict):
            request["position"] = {
                "x": int(position["x"]),
                "y": int(position["y"]),
                "width": int(position["width"]),
                "height": int(position["height"]),
            }
        requests.append(request)
    return requests


def vocab_string_identifiers(client) -> dict[int, str]:
    from crowdin_api.api_resources.source_strings.enums import ScopeFilter

    mapping: dict[int, str] = {}
    for row in _iter_pages(
        lambda limit, offset: client.source_strings.list_strings(
            limit=limit,
            offset=offset,
            filter="vocab-item",
            scope=ScopeFilter.IDENTIFIER,
        )
    ):
        identifier = str(row.get("identifier") or "")
        if identifier.startswith("vocab-item-") and row.get("id") is not None:
            mapping[int(row["id"])] = identifier
    return mapping


def _screenshot_record(client, shot: dict, identifiers: dict[int, str], seen_ids: set[int]) -> dict | None:
    name = str(shot.get("name") or "")
    screenshot_id = int(shot.get("id") or 0)
    if not screenshot_id or screenshot_id in seen_ids:
        return None
    tags = _screenshot_tags(client, shot)
    item_ids = []
    for tag in tags:
        string_id = tag.get("stringId")
        if string_id is None:
            continue
        identifier = identifiers.get(int(string_id))
        if identifier is None:
            identifier = _fetch_identifier(client, int(string_id), identifiers)
        if identifier and identifier.startswith("vocab-item-") and identifier not in item_ids:
            item_ids.append(identifier)
    url = str(shot.get("url") or "")
    skip_reason = None
    if len(item_ids) != 1:
        skip_reason = "no single vocab-item tag"
    elif not url:
        skip_reason = "missing screenshot url"
    return {
        "screenshot_id": screenshot_id,
        "name": name,
        "url": url,
        "item_id": item_ids[0] if len(item_ids) == 1 else None,
        "tags": tags,
        "skip_reason": skip_reason,
    }


def list_vocab_screenshots(client) -> list[dict]:
    """Vocab screenshots tagged to one vocab-item identifier.

    Names are usually vocab-NNN.png. A replaced screenshot can have another
    filename, so any vocab item still missing after that pass is looked up by tag.
    """
    identifiers = vocab_string_identifiers(client)
    screenshots = []
    seen_ids: set[int] = set()
    for shot in _iter_pages(lambda limit, offset: client.screenshots.list_screenshots(limit=limit, offset=offset)):
        if not VOCAB_SCREENSHOT_RE.match(str(shot.get("name") or "")):
            continue
        record = _screenshot_record(client, shot, identifiers, seen_ids)
        if record:
            seen_ids.add(record["screenshot_id"])
            screenshots.append(record)
    covered = {shot["item_id"] for shot in screenshots if shot.get("item_id")}
    for string_id, item_id in list(identifiers.items()):
        if item_id in covered:
            continue
        for shot in _iter_pages(
            lambda limit, offset, string_id=string_id: client.screenshots.list_screenshots(
                limit=limit,
                offset=offset,
                stringIds=[string_id],
            )
        ):
            record = _screenshot_record(client, shot, identifiers, seen_ids)
            if not record or record.get("item_id") != item_id:
                continue
            seen_ids.add(record["screenshot_id"])
            screenshots.append(record)
            covered.add(item_id)
            break
    screenshots.sort(key=lambda shot: shot["screenshot_id"])
    return screenshots


def _fetch_identifier(client, string_id: int, cache: dict[int, str]) -> str | None:
    if string_id in cache:
        return cache[string_id]
    payload = client.source_strings.get_string(stringId=string_id)
    data = payload.get("data") or {}
    identifier = str(data.get("identifier") or "")
    if identifier:
        cache[string_id] = identifier
    return identifier or None


def download_bytes(url: str) -> bytes:
    request = urllib.request.Request(url)
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read()


def output_filename(screenshot_id: int, name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).name).strip("_") or "screenshot.png"
    return f"{screenshot_id}_{safe}"


def restore_tags_if_needed(client, screenshot_id: int, previous_tags: Sequence[dict]) -> str | None:
    payload = client.screenshots.list_tags(screenshotId=screenshot_id, limit=100, offset=0)
    current = _unwrap_rows(payload)
    current_ids = {int(tag["stringId"]) for tag in current if tag.get("stringId") is not None}
    missing = [tag for tag in previous_tags if tag.get("stringId") is not None and int(tag["stringId"]) not in current_ids]
    if not missing:
        return None
    client.screenshots.add_tag(screenshotId=screenshot_id, data=_tag_requests(missing))
    return f"restored {len(missing)} tag(s)"


def upload_marked(client, screenshot_id: int, name: str, marked_path: Path, previous_tags: Sequence[dict]) -> str | None:
    with marked_path.open("rb") as handle:
        stored = client.storages.add_storage(handle)
    storage_id = int(stored["data"]["id"])
    client.screenshots.update_screenshot(screenshotId=screenshot_id, storageId=storage_id, name=name)
    return restore_tags_if_needed(client, screenshot_id, previous_tags)


def process_screenshots(
    shots: Sequence[dict],
    corpus: dict[str, dict[str, object]],
    images_dir: Path | Sequence[Path],
    output_dir: Path,
    *,
    upload: bool,
    client=None,
) -> list[dict]:
    originals = output_dir / "originals"
    marked_dir = output_dir / "marked"
    results = []
    for shot in shots:
        record = {
            "screenshot_id": shot["screenshot_id"],
            "name": shot["name"],
            "item_id": shot.get("item_id"),
            "answer": None,
            "quadrant": None,
            "match_margin": None,
            "status": "skipped",
            "reason": shot.get("skip_reason"),
            "uploaded": False,
            "original": None,
            "marked": None,
            "original_refresh": None,
        }
        if record["reason"]:
            results.append(record)
            print(f"skip {shot['screenshot_id']} {shot['name']}: {record['reason']}")
            continue
        item = corpus.get(str(shot["item_id"]))
        if not item:
            record["reason"] = f"no corpus row for {shot['item_id']}"
            results.append(record)
            print(f"skip {shot['screenshot_id']} {shot['name']}: {record['reason']}")
            continue
        filename = output_filename(shot["screenshot_id"], shot["name"])
        original_path = originals / filename
        marked_path = marked_dir / filename
        try:
            refresh = replace_original_if_changed(original_path, download_bytes(shot["url"]))
            record["original_refresh"] = refresh
            if refresh == "updated":
                print(f"updated original {shot.get('item_id')} {shot['name']}")
            record["original"] = str(original_path)
            record["answer"] = item["answer"]
            with Image.open(original_path) as image:
                marked, info = mark_screenshot(
                    image,
                    str(item["answer"]),
                    list(item["distractors"]),
                    images_dir,
                )
            marked_path.parent.mkdir(parents=True, exist_ok=True)
            marked.save(marked_path, format="PNG")
            record.update(
                {
                    "status": "marked",
                    "reason": None,
                    "quadrant": info["quadrant"],
                    "match_margin": info["match_margin"],
                    "marked": str(marked_path),
                }
            )
            print(
                f"marked {shot['item_id']} {shot['name']} answer={item['answer']} "
                f"quadrant={info['quadrant']} margin={info['match_margin']}"
            )
            if upload:
                note = upload_marked(client, shot["screenshot_id"], shot["name"], marked_path, shot.get("tags") or [])
                record["uploaded"] = True
                if note:
                    record["reason"] = note
                print(f"uploaded {shot['screenshot_id']} {shot['name']}")
        except ValueError as exc:
            record["reason"] = str(exc)
            print(f"skip {shot['screenshot_id']} {shot['name']}: {exc}")
        except Exception as exc:
            record["status"] = "error"
            record["reason"] = str(exc)
            print(f"error {shot['screenshot_id']} {shot['name']}: {exc}", file=sys.stderr)
        results.append(record)
    return results


def screenshots_from_artifact(path: Path) -> list[dict]:
    """Vocab screenshots from a crowdin-screenshot-artifact.json cache."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    shots = []
    seen = set()
    for entry in payload.get("entries") or []:
        item_id = str(entry.get("itemId") or "")
        if not item_id.startswith("vocab-item-"):
            continue
        for shot in entry.get("screenshots") or []:
            name = str(shot.get("name") or "")
            if not VOCAB_SCREENSHOT_RE.match(name):
                continue
            screenshot_id = int(shot.get("screenshotId") or 0)
            if not screenshot_id or screenshot_id in seen:
                continue
            seen.add(screenshot_id)
            url = str(shot.get("url") or shot.get("sourceUrl") or "")
            shots.append(
                {
                    "screenshot_id": screenshot_id,
                    "name": name,
                    "url": url,
                    "item_id": item_id,
                    "tags": [],
                    "skip_reason": None if url else "missing screenshot url",
                }
            )
    shots.sort(key=lambda shot: int(str(shot["item_id"]).rsplit("-", 1)[-1]))
    return shots


def write_review_page(output_dir: Path, results: Sequence[dict], asset_base: str = "") -> Path:
    """Local HTML page for checking marked screenshots.

    asset_base, when set, points image tags at that public prefix instead of
    local relative files. Marked images use {base}/marked/ and unmarked images
    use {base}/originals/.
    """
    import html as html_lib

    def card_html(row: dict) -> str:
        item_id = str(row.get("item_id") or "")
        answer = str(row.get("answer") or "")
        status = str(row.get("status") or "")
        quadrant = str(row.get("quadrant") or "")
        margin = row.get("match_margin")
        reason = str(row.get("reason") or "")
        image_path = row.get("marked") or row.get("original")
        src = ""
        if image_path:
            filename = Path(image_path).name
            if asset_base:
                folder = "marked" if row.get("marked") else "originals"
                src = f"{asset_base.rstrip('/')}/{folder}/{filename}?v=20261023f"
            else:
                src = Path(image_path).relative_to(output_dir).as_posix()
        bits = [item_id, answer or "—", status]
        if quadrant:
            bits.append(quadrant)
        if margin is not None:
            bits.append(f"margin {margin}")
        if reason:
            bits.append(reason)
        caption = html_lib.escape(" · ".join(bits))
        css = "missing" if status != "marked" else ("low" if margin is not None and float(margin) < 20 else "")
        if src:
            return (
                f'<figure class="{css}"><img src="{html_lib.escape(src)}" '
                f'alt="{html_lib.escape(item_id)}"><figcaption>{caption}</figcaption></figure>'
            )
        return f'<figure class="missing"><figcaption>{caption}</figcaption></figure>'

    def item_number(row: dict) -> int:
        item_id = str(row.get("item_id") or "")
        tail = item_id.rsplit("-", 1)[-1]
        return int(tail) if tail.isdigit() else 10**9

    ordered = sorted(results, key=item_number)
    body = "\n".join(card_html(row) for row in ordered)
    page = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Vocab screenshot check</title>
<style>
  body { font-family: sans-serif; margin: 16px; background: #f4f4f4; }
  figure { display: inline-block; width: 320px; margin: 8px; background: white; vertical-align: top; }
  img { width: 100%; height: auto; }
  figcaption { font-size: 13px; padding: 6px; }
  .missing { outline: 2px solid #c45; }
  .low { outline: 2px solid #e6a817; }
</style>
</head>
<body>
<h1>Vocab screenshot check</h1>
<p>__COUNT__ items, in numerical item order. Green border should sit on the picture named in the caption.</p>
__BODY__
</body>
</html>
"""
    page = page.replace("__COUNT__", str(len(results))).replace("__BODY__", body)
    path = output_dir / ("review-public.html" if asset_base else "review.html")
    path.write_text(page, encoding="utf-8")
    return path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mark correct vocab answers on Crowdin screenshots")
    parser.add_argument("--project", default=DEFAULT_PROJECT_ID, help="Crowdin project id (default 756721)")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS, help="Vocab corpus CSV")
    parser.add_argument(
        "--images",
        type=Path,
        default=DEFAULT_IMAGES,
        help="Local cache of vocab photos. Refreshed from levante-assets-dev before matching",
    )
    parser.add_argument(
        "--extra-images",
        type=Path,
        action="append",
        default=[],
        help="Extra local directory of source images, searched after the cache",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Local originals, marked images, and manifest")
    parser.add_argument("--items", default="", help="Comma-separated vocab-item ids to process")
    parser.add_argument("--limit", type=int, default=0, help="Max screenshots to process (0 means all)")
    parser.add_argument("--upload", action="store_true", help="Replace the Crowdin screenshot with the marked image")
    parser.add_argument(
        "--artifact",
        type=Path,
        help="Use a crowdin-screenshot-artifact.json cache instead of listing screenshots live",
    )
    parser.add_argument(
        "--review-only",
        action="store_true",
        help="Rewrite the review page from the existing manifest without marking again",
    )
    parser.add_argument(
        "--asset-base",
        default="",
        help="Public URL prefix for review images, such as a GCS folder",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.review_only:
        manifest_path = args.output / "manifest.json"
        if not manifest_path.exists():
            print(f"ERROR: manifest not found: {manifest_path}", file=sys.stderr)
            return 2
        results = json.loads(manifest_path.read_text(encoding="utf-8"))
        review_path = write_review_page(args.output, results, asset_base=args.asset_base)
        print(f"Review: {review_path}")
        return 0
    if not args.corpus.exists():
        print(f"ERROR: corpus not found: {args.corpus}", file=sys.stderr)
        return 2
    extra_missing = [path for path in args.extra_images if not path.exists()]
    if extra_missing:
        print("ERROR: image directory not found: " + ", ".join(str(path) for path in extra_missing), file=sys.stderr)
        return 2
    corpus = load_corpus(args.corpus)
    asset_words = []
    for item in corpus.values():
        asset_words.append(str(item["answer"]))
        asset_words.extend(str(word) for word in item["distractors"])
    cache_vocab_assets(asset_words, args.images)
    image_paths = [args.images, *args.extra_images]
    client = None
    if args.artifact:
        if not args.artifact.exists():
            print(f"ERROR: artifact not found: {args.artifact}", file=sys.stderr)
            return 2
        shots = screenshots_from_artifact(args.artifact)
        if args.upload:
            client = crowdin_client(args.project)
    else:
        client = crowdin_client(args.project)
        shots = list_vocab_screenshots(client)
    wanted = {item.strip() for item in args.items.split(",") if item.strip()}
    if wanted:
        shots = [shot for shot in shots if shot.get("item_id") in wanted]
    if args.limit > 0:
        shots = shots[: args.limit]
    results = process_screenshots(
        shots,
        corpus,
        image_paths,
        args.output,
        upload=args.upload,
        client=client,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output / "manifest.json"
    manifest_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    review_path = write_review_page(args.output, results)
    marked = sum(1 for row in results if row["status"] == "marked")
    skipped = sum(1 for row in results if row["status"] == "skipped")
    errors = sum(1 for row in results if row["status"] == "error")
    print(f"{marked} marked, {skipped} skipped, {errors} errors.")
    print(f"Manifest: {manifest_path}")
    print(f"Review: {review_path}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
