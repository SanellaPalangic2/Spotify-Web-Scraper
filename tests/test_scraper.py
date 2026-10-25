from pathlib import Path

import pytest
import requests

from tracker import scraper
from tracker.scraper import ScrapeError, is_allowed, parse_listeners

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parses_every_row_with_numbers_and_spotify_ids():
    rows = parse_listeners(fixture("listeners_sample.html"))

    assert [r.artist for r in rows] == ["Example Artist", "Zoë Fictional", "The Placeholders"]
    first = rows[0]
    assert first.rank == 1
    assert first.spotify_id == "AAAAAAAAAAAAAAAAAAAAA1"
    assert first.monthly_listeners == 127_951_989
    assert first.daily_change == -330_218
    assert first.peak_rank == 1
    assert first.peak_listeners == 151_079_821


def test_handles_plus_signs_accents_and_empty_cells():
    rows = parse_listeners(fixture("listeners_sample.html"))

    assert rows[1].artist == "Zoë Fictional"
    assert rows[1].daily_change == 54_112
    assert rows[2].daily_change is None
    assert rows[2].monthly_listeners == 1_234


def test_fails_loudly_when_the_layout_changes():
    with pytest.raises(ScrapeError, match="layout changed"):
        parse_listeners(fixture("listeners_changed_layout.html"))


def test_fails_when_there_is_no_table():
    with pytest.raises(ScrapeError, match="No table"):
        parse_listeners("<html><body><p>Down for maintenance</p></body></html>")


def test_fails_on_a_non_numeric_value():
    html = fixture("listeners_sample.html").replace("127,951,989", "lots")

    with pytest.raises(ScrapeError, match="Unexpected value 'lots'"):
        parse_listeners(html)


def test_robots_rules_are_respected():
    assert is_allowed("https://example.com/spotify/listeners.html", "User-agent: *\nAllow: /")
    assert not is_allowed("https://example.com/spotify/listeners.html", "User-agent: *\nDisallow: /spotify/")


class FakeResponse:
    """Behaves like requests.Response: bytes on the wire, text decoded with
    `encoding`, which requests sets to ISO-8859-1 for HTML without a charset."""

    def __init__(self, text="", status_code=200, content_type="text/html"):
        self.content = text.encode("utf-8")
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}
        self.encoding = None if "charset=" in content_type else "ISO-8859-1"
        if "charset=" in content_type:
            self.encoding = content_type.split("charset=")[1]

    @property
    def text(self):
        return self.content.decode(self.encoding)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    """Records requests and replies from a dict of URL -> FakeResponse."""

    def __init__(self, responses):
        self.responses = responses
        self.requested = []

    def get(self, url, headers=None, timeout=None):
        self.requested.append((url, headers, timeout))
        return self.responses[url]


def test_fetch_never_requests_a_page_robots_txt_disallows():
    session = FakeSession({"https://kworb.net/robots.txt": FakeResponse("User-agent: *\nDisallow: /")})

    with pytest.raises(ScrapeError, match="does not allow"):
        scraper.fetch(scraper.URL, session=session)

    assert [url for url, _, _ in session.requested] == ["https://kworb.net/robots.txt"]


def test_fetch_identifies_itself_and_uses_a_timeout():
    session = FakeSession({
        "https://kworb.net/robots.txt": FakeResponse("User-agent: *\nAllow: /"),
        scraper.URL: FakeResponse(fixture("listeners_sample.html")),
    })

    html = scraper.fetch(scraper.URL, session=session)

    assert "Example Artist" in html
    for _, headers, timeout in session.requested:
        assert headers["User-Agent"] == scraper.USER_AGENT
        assert timeout == scraper.TIMEOUT_SECONDS


def test_fetch_decodes_utf8_when_the_server_sends_no_charset():
    # Real kworb behavior: UTF-8 bytes, "Content-Type: text/html" with no charset.
    session = FakeSession({
        "https://kworb.net/robots.txt": FakeResponse("User-agent: *\nAllow: /"),
        scraper.URL: FakeResponse(fixture("listeners_sample.html"), content_type="text/html"),
    })

    html = scraper.fetch(scraper.URL, session=session)

    assert "Zoë Fictional" in html
    assert "ZoÃ«" not in html


def test_fetch_respects_a_declared_charset():
    session = FakeSession({
        "https://kworb.net/robots.txt": FakeResponse("User-agent: *\nAllow: /"),
        scraper.URL: FakeResponse(fixture("listeners_sample.html"), content_type="text/html; charset=utf-8"),
    })

    assert "Zoë Fictional" in scraper.fetch(scraper.URL, session=session)


def test_fetch_retries_server_errors_then_gives_up(monkeypatch):
    monkeypatch.setattr(scraper.time, "sleep", lambda seconds: None)
    session = FakeSession({
        "https://kworb.net/robots.txt": FakeResponse("", status_code=404),  # no robots.txt = no rules
        scraper.URL: FakeResponse("", status_code=503),
    })

    with pytest.raises(ScrapeError, match="HTTP 503"):
        scraper.fetch(scraper.URL, session=session, retries=3)

    assert sum(1 for url, _, _ in session.requested if url == scraper.URL) == 3


def test_scrape_can_keep_only_the_top_n(monkeypatch):
    monkeypatch.setattr(scraper, "fetch", lambda url, session=None: fixture("listeners_sample.html"))

    assert [r.rank for r in scraper.scrape(top=2)] == [1, 2]
