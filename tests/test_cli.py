from pathlib import Path

import pytest

from tracker import __main__ as cli
from tracker import storage
from tracker.scraper import ScrapeError, parse_listeners

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def isolated_data(monkeypatch, tmp_path):
    """Point all data files at a temp folder so tests never touch data/."""
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(storage, "LISTENERS_DIR", tmp_path / "data" / "listeners")
    monkeypatch.setattr(storage, "POPULARITY_FILE", tmp_path / "data" / "artist_popularity.csv")
    return tmp_path


def test_scrape_command_saves_a_snapshot(monkeypatch, isolated_data, capsys):
    rows = parse_listeners((FIXTURES / "listeners_sample.html").read_text(encoding="utf-8"))
    monkeypatch.setattr(cli, "scrape", lambda top=None: rows[:top])

    assert cli.main(["scrape", "--top", "2"]) == 0

    out = capsys.readouterr().out
    assert "Scraped 2 artists" in out
    assert "Example Artist: 127,951,989 monthly listeners" in out
    saved = list((isolated_data / "data" / "listeners").glob("*.csv"))
    assert len(saved) == 1
    assert len(storage.latest_listeners()) == 2


def test_scrape_command_reports_failure(monkeypatch, capsys):
    def broken(top=None):
        raise ScrapeError("Page layout changed")

    monkeypatch.setattr(cli, "scrape", broken)

    assert cli.main(["scrape"]) == 1
    assert "Scrape failed: Page layout changed" in capsys.readouterr().err


def test_playlist_command_without_credentials_fails_clearly(monkeypatch, capsys):
    monkeypatch.delenv("SPOTIPY_CLIENT_ID", raising=False)
    monkeypatch.delenv("SPOTIPY_CLIENT_SECRET", raising=False)

    assert cli.main(["playlist"]) == 1
    assert "Missing Spotify credentials" in capsys.readouterr().err


def test_compare_needs_a_scrape_first(capsys):
    assert cli.main(["compare"]) == 1
    assert "No scraped data yet" in capsys.readouterr().err


def test_plot_with_no_data_fails_clearly(capsys):
    assert cli.main(["plot"]) == 1
    assert "No data to plot yet" in capsys.readouterr().err
