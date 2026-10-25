"""Read and write the tracker's CSV data (always UTF-8, so names like ROSÉ survive)."""

from __future__ import annotations

import csv
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

# Looked up at call time (not as default arguments) so tests can point them elsewhere.
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LISTENERS_DIR = DATA_DIR / "listeners"
POPULARITY_FILE = DATA_DIR / "artist_popularity.csv"

LISTENER_COLUMNS = [
    "scraped_at", "rank", "artist", "spotify_id",
    "monthly_listeners", "daily_change", "peak_rank", "peak_listeners",
]
POPULARITY_COLUMNS = ["timestamp", "artist", "popularity"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def save_listeners_snapshot(rows, scraped_at: datetime | None = None, directory: Path | None = None) -> Path:
    """Write one day's scrape to data/listeners/YYYY-MM-DD.csv.

    One file per day keeps git diffs small and makes re-running the same day
    safe: it replaces that day's file instead of adding duplicates.
    """
    scraped_at = scraped_at or utc_now()
    directory = directory or LISTENERS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{scraped_at.date().isoformat()}.csv"

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=LISTENER_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({"scraped_at": scraped_at.isoformat(), **row.to_dict()})
    return path


def load_listeners_history(directory: Path | None = None) -> pd.DataFrame:
    """All daily snapshots as one table, oldest first."""
    files = sorted((directory or LISTENERS_DIR).glob("*.csv"))
    if not files:
        return pd.DataFrame(columns=LISTENER_COLUMNS + ["date"])
    frames = [pd.read_csv(f, encoding="utf-8") for f in files]
    history = pd.concat(frames, ignore_index=True)
    history["date"] = pd.to_datetime(history["scraped_at"]).dt.date
    return history


def latest_listeners(directory: Path | None = None) -> pd.DataFrame:
    """The most recent snapshot only."""
    history = load_listeners_history(directory)
    if history.empty:
        return history
    return history[history["date"] == history["date"].max()].reset_index(drop=True)


def append_popularity(artists, timestamp: datetime | None = None, path: Path | None = None) -> Path:
    """Append API popularity scores (no header, same format as the original data)."""
    timestamp = timestamp or datetime.now()
    path = path or POPULARITY_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        for artist in artists:
            writer.writerow([timestamp.strftime("%Y-%m-%d %H:%M:%S"), artist["name"], artist["popularity"]])
    return path


def load_popularity(path: Path | None = None) -> pd.DataFrame:
    path = path or POPULARITY_FILE
    if not path.exists():
        return pd.DataFrame(columns=POPULARITY_COLUMNS)
    df = pd.read_csv(path, names=POPULARITY_COLUMNS, encoding="utf-8")
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def snapshot_date(path: Path) -> date:
    return date.fromisoformat(path.stem)
