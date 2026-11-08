"""Parse timestamped microdrama screenplays without treating overlapping events as sequential."""
from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path, PurePosixPath
import math
import re
import zipfile

MAX_TEXT_BYTES = 2 * 1024 * 1024
MAX_ZIP_BYTES = 50 * 1024 * 1024
MAX_EXPANDED_BYTES = 100 * 1024 * 1024
MAX_EPISODES = 500


@dataclass
class Event:
    id: str
    kind: str
    speaker: str
    start: float
    end: float
    text: str


@dataclass
class Episode:
    number: int
    source: str
    logline: str
    continuity: str
    duration: float
    events: list[Event]
    warnings: list[str] = field(default_factory=list)


def parse_timestamp(value: str) -> float:
    """Accept MM:SS[.fraction] or HH:MM:SS[.fraction], never negative times."""
    value = value.strip().strip("()")
    if not re.fullmatch(r"\d+:\d{2}(?::\d{2})?(?:\.\d+)?", value):
        raise ValueError(f"Invalid timestamp: {value!r}")
    parts = value.split(":")
    seconds = float(parts[-1])
    minutes = int(parts[-2])
    if seconds >= 60 or (len(parts) == 3 and minutes >= 60):
        raise ValueError(f"Invalid timestamp: {value!r}")
    return round((int(parts[0]) * 3600 if len(parts) == 3 else 0) + minutes * 60 + seconds, 6)


def format_timestamp(seconds: float) -> str:
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError("Timestamp must be finite and nonnegative")
    ticks = round(seconds * 100)
    minutes, remainder = divmod(ticks, 6000)
    secs, cents = divmod(remainder, 100)
    return f"{minutes:02d}:{secs:02d}.{cents:02d}"


_HEADER = re.compile(r"^\*\*(.+?)\*\*\s*$", re.MULTILINE)
_TIMING = re.compile(r"^Start:\s*\(([^)]+)\)\s*\|\s*End:\s*\(([^)]+)\)\s*$", re.IGNORECASE | re.MULTILINE)
_SCENE_TIME = re.compile(r"^Scene\s+(start|end):\s*(.*?)\s*$", re.IGNORECASE | re.MULTILINE)


def _metadata(text: str, name: str) -> str:
    match = re.search(rf"^{re.escape(name)}:\s*(.*)$", text, re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def parse_episode(text: str, source: str = "") -> Episode:
    """Reject incomplete event blocks; preserve source order and all overlaps.

    Declared scene bounds determine duration. Events outside them are retained
    with a warning so the validation layer can reject affected clips. If scene
    times are absent, maximum event end is used and explicitly warned about.
    """
    if len(text.encode("utf-8")) > MAX_TEXT_BYTES:
        raise ValueError("Script exceeds the 2 MiB per-file limit")
    text = text.lstrip("\ufeff").replace("\r\n", "\n")
    number_text = _metadata(text, "EPISODE NUMBER")
    number_match = re.fullmatch(r"(?:Episode\s+)?(\d+)", number_text, re.IGNORECASE)
    if not number_match or int(number_match.group(1)) < 1:
        raise ValueError(f"{source}: missing or invalid EPISODE NUMBER")
    headers = list(_HEADER.finditer(text))
    if not headers:
        raise ValueError(f"{source}: no timestamped event blocks found")
    events = []
    consumed_timing = 0
    for index, header in enumerate(headers):
        block_end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        raw = text[header.end():block_end]
        # A new scene or script terminator belongs to the screenplay structure.
        raw = re.split(r"^\s*(?:SCENE\s+\d+\b|---\s*SCRIPT END\s*---)", raw, maxsplit=1, flags=re.MULTILINE | re.IGNORECASE)[0]
        timing = list(_TIMING.finditer(raw))
        if len(timing) != 1 or raw[:timing[0].start()].strip():
            raise ValueError(f"{source}: event {index + 1} has missing or malformed timing")
        consumed_timing += 1
        start, end = map(parse_timestamp, timing[0].groups())
        if end <= start:
            raise ValueError(f"{source}: event {index + 1} must end after it starts")
        content = raw[timing[0].end():].strip()
        if not content or re.search(r"^(?:Start|End):", content, re.MULTILINE | re.IGNORECASE):
            raise ValueError(f"{source}: event {index + 1} has empty content or unparsed timing")
        label = header.group(1).strip().rstrip(":").strip()
        label_upper = label.upper()
        kind = {"CAMERA": "camera", "ACTION": "action", "SOUND FX": "sound", "SOUND": "sound", "SFX": "sound"}.get(label_upper, "dialogue")
        speaker = re.sub(r"\s*\([^)]*\)", "", label).strip() if kind == "dialogue" else ""
        events.append(Event(f"e{index + 1:03d}", kind, speaker, start, end, content))
    all_start_lines = re.findall(r"^Start\s*:", text, re.MULTILINE | re.IGNORECASE)
    if len(all_start_lines) != consumed_timing:
        raise ValueError(f"{source}: unparsed timestamp blocks detected")
    warnings = []
    scene_values = list(_SCENE_TIME.finditer(text))
    bounds = []
    for index in range(0, len(scene_values), 2):
        if index + 1 >= len(scene_values) or scene_values[index].group(1).lower() != "start" or scene_values[index + 1].group(1).lower() != "end":
            raise ValueError(f"{source}: incomplete scene bounds")
        start = parse_timestamp(scene_values[index].group(2))
        end = parse_timestamp(scene_values[index + 1].group(2))
        if end <= start:
            raise ValueError(f"{source}: invalid scene duration")
        bounds.append((start, end))
    if bounds:
        duration = max(end for _, end in bounds)
        if any(e.start < min(start for start, _ in bounds) or e.end > duration + 0.001 for e in events):
            warnings.append("One or more events extend outside declared episode scene bounds.")
        if any(bounds[i][0] < bounds[i - 1][1] - 0.001 for i in range(1, len(bounds))):
            warnings.append("Scene ranges overlap or are not in chronological order.")
        if any(not any(start <= e.start < end for start, end in bounds) for e in events):
            warnings.append("One or more events begin outside all declared scenes.")
    else:
        duration = max(e.end for e in events)
        warnings.append("No scene bounds found; duration inferred from event end times.")
    return Episode(int(number_match.group(1)), source, _metadata(text, "EPISODE LOGLINE"), _metadata(text, "CONTINUITY NOTES"), duration, events, warnings)


def _validate_pack(episodes: list[Episode]) -> list[Episode]:
    if not episodes:
        raise ValueError("No .txt episode scripts found")
    if len(episodes) > MAX_EPISODES:
        raise ValueError(f"At most {MAX_EPISODES} episodes are supported per run")
    seen = set()
    for episode in episodes:
        if episode.number in seen:
            raise ValueError(f"Duplicate episode number: {episode.number}")
        seen.add(episode.number)
    return sorted(episodes, key=lambda episode: episode.number)


def parse_zip_bytes(data: bytes) -> list[Episode]:
    """Read scripts in memory, never extract archive paths to disk."""
    if len(data) > MAX_ZIP_BYTES:
        raise ValueError("ZIP exceeds the 50 MiB compressed limit")
    try:
        archive = zipfile.ZipFile(BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValueError("Invalid ZIP file") from exc
    with archive:
        entries = archive.infolist()
        if sum(entry.file_size for entry in entries) > MAX_EXPANDED_BYTES:
            raise ValueError("ZIP exceeds the 100 MiB uncompressed limit")
        scripts = []
        for entry in entries:
            name = entry.filename.replace("\\", "/")
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or (path.parts and ":" in path.parts[0]):
                raise ValueError("ZIP contains an unsafe path")
            if entry.is_dir() or path.suffix.lower() != ".txt" or "__MACOSX" in path.parts:
                continue
            if entry.file_size > MAX_TEXT_BYTES:
                raise ValueError("Script exceeds the 2 MiB per-file limit")
            if len(scripts) >= MAX_EPISODES:
                raise ValueError(f"At most {MAX_EPISODES} episodes are supported per run")
            try:
                text = archive.read(entry).decode("utf-8-sig")
            except (UnicodeError, RuntimeError, zipfile.BadZipFile) as exc:
                raise ValueError(f"Cannot read UTF-8 script: {entry.filename}") from exc
            scripts.append(parse_episode(text, entry.filename))
    return _validate_pack(scripts)


def load_episodes(path: str | Path) -> list[Episode]:
    path = Path(path)
    if path.is_file() and path.suffix.lower() == ".zip":
        if path.stat().st_size > MAX_ZIP_BYTES:
            raise ValueError("ZIP exceeds the 50 MiB compressed limit")
        return parse_zip_bytes(path.read_bytes())
    paths = sorted(p for p in path.rglob("*") if p.is_file() and p.suffix.lower() == ".txt") if path.is_dir() else [path]
    if len(paths) > MAX_EPISODES:
        raise ValueError(f"At most {MAX_EPISODES} episodes are supported per run")
    episodes = []
    for file in paths:
        if file.suffix.lower() != ".txt" or not file.is_file():
            raise ValueError("Input must be a .txt script, .zip pack, or script directory")
        if file.stat().st_size > MAX_TEXT_BYTES:
            raise ValueError("Script exceeds the 2 MiB per-file limit")
        episodes.append(parse_episode(file.read_text(encoding="utf-8-sig"), file.name))
    return _validate_pack(episodes)
