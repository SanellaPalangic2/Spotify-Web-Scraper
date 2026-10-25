from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from tracker import spotify_api, storage
from tracker.compare import compare
from tracker.scraper import parse_listeners

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def rows():
    return parse_listeners((FIXTURES / "listeners_sample.html").read_text(encoding="utf-8"))


def test_snapshot_is_utf8_and_one_file_per_day(tmp_path, rows):
    day = datetime(2026, 10, 25, 6, 17, tzinfo=timezone.utc)

    path = storage.save_listeners_snapshot(rows, day, directory=tmp_path)
    storage.save_listeners_snapshot(rows, day, directory=tmp_path)  # same day again

    assert path.name == "2026-10-25.csv"
    assert list(tmp_path.iterdir()) == [path]
    text = path.read_text(encoding="utf-8")
    assert "Zoë Fictional" in text
    assert text.count("Example Artist") == 1  # replaced, not duplicated


def test_history_and_latest_snapshot(tmp_path, rows):
    storage.save_listeners_snapshot(rows, datetime(2026, 10, 24, tzinfo=timezone.utc), directory=tmp_path)
    storage.save_listeners_snapshot(rows[:1], datetime(2026, 10, 25, tzinfo=timezone.utc), directory=tmp_path)

    history = storage.load_listeners_history(tmp_path)
    latest = storage.latest_listeners(tmp_path)

    assert len(history) == 4
    assert len(latest) == 1
    assert latest.loc[0, "artist"] == "Example Artist"


def test_popularity_round_trip_keeps_accents(tmp_path):
    path = tmp_path / "artist_popularity.csv"

    storage.append_popularity([{"name": "ROSÉ", "popularity": 85}], datetime(2026, 10, 25, 12), path=path)
    df = storage.load_popularity(path)

    assert df.loc[0, "artist"] == "ROSÉ"
    assert df.loc[0, "popularity"] == 85


def test_compare_matches_by_spotify_id_not_name(tmp_path, rows):
    storage.save_listeners_snapshot(rows, datetime(2026, 10, 25, tzinfo=timezone.utc), directory=tmp_path)
    listeners = storage.latest_listeners(tmp_path)

    result = compare([
        {"id": "BBBBBBBBBBBBBBBBBBBBB2", "name": "Zoe Fictional", "popularity": 88},   # spelled differently
        {"id": "ZZZZZZZZZZZZZZZZZZZZZ9", "name": "Example Artist", "popularity": 40},  # same name, different artist
    ], listeners)

    by_id = result.set_index("id")
    assert by_id.loc["BBBBBBBBBBBBBBBBBBBBB2", "monthly_listeners"] == 98_000_000
    assert by_id.loc["BBBBBBBBBBBBBBBBBBBBB2", "listeners_rank"] == 2
    assert pd.isna(by_id.loc["ZZZZZZZZZZZZZZZZZZZZZ9", "monthly_listeners"])


class FakeSpotify:
    """Just enough of spotipy.Spotify for get_playlist_artists."""

    def __init__(self, tracks_pages, artists):
        self.pages = tracks_pages
        self.artists_by_id = artists
        self.artist_batches = []

    def playlist_tracks(self, playlist_id):
        return self.pages[0]

    def next(self, results):
        return self.pages[self.pages.index(results) + 1]

    def artists(self, ids):
        self.artist_batches.append(list(ids))
        return {"artists": [self.artists_by_id[i] for i in ids]}


def track(*artist_ids):
    return {"track": {"artists": [{"id": a} for a in artist_ids]}}


def test_playlist_artists_follow_pages_dedupe_skip_local_files_and_batch():
    ids = [f"{n:022d}" for n in range(60)]
    page2 = {"items": [track(ids[0]), {"track": None}, track(None)], "next": None}  # repeat, removed, local
    page1 = {"items": [track(i) for i in ids], "next": "page2"}
    sp = FakeSpotify([page1, page2], {i: {"id": i, "name": f"Artist {i}", "popularity": 50} for i in ids})

    artists = spotify_api.get_playlist_artists(sp, "playlist")

    assert len(artists) == 60
    assert [len(batch) for batch in sp.artist_batches] == [50, 10]  # 2 API calls, not 60


def test_missing_credentials_give_a_clear_error(monkeypatch):
    monkeypatch.delenv("SPOTIPY_CLIENT_ID", raising=False)
    monkeypatch.delenv("SPOTIPY_CLIENT_SECRET", raising=False)

    with pytest.raises(spotify_api.CredentialsError, match="SPOTIPY_CLIENT_ID"):
        spotify_api.get_client()
