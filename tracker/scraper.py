"""Scrape Spotify monthly listeners from kworb.net.

The Spotify Web API gives each artist a 0-100 "popularity" score but not the
monthly-listener count shown on artist pages. kworb.net publishes a public
table of top artists by monthly listeners, and its robots.txt allows crawling.
(Spotify's own Terms of Use forbid scraping Spotify, so we don't.)

Good-citizen rules this module follows:
- check robots.txt before fetching
- identify ourselves with a descriptive User-Agent
- one page request per run, with a timeout
- fail loudly if the page layout changes, instead of saving bad data
"""

from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

URL = "https://kworb.net/spotify/listeners.html"
USER_AGENT = (
    "spotify-artist-tracker/1.0 "
    "(portfolio project; https://github.com/SanellaPalangic2/Spotify-Web-Scraper)"
)
EXPECTED_HEADERS = ["#", "Artist", "Listeners", "Daily +/-", "Peak", "PkListeners"]
TIMEOUT_SECONDS = 20

# Artist links look like "artist/0du5cEVh5yTK9QJze8zA0C_songs.html";
# the 22 characters after "artist/" are the Spotify artist ID.
SPOTIFY_ID_IN_LINK = re.compile(r"artist/([A-Za-z0-9]{22})_")


class ScrapeError(Exception):
    """The page couldn't be fetched, wasn't allowed, or didn't look as expected."""


@dataclass(frozen=True)
class ArtistListeners:
    rank: int
    artist: str
    spotify_id: str | None
    monthly_listeners: int
    daily_change: int | None
    peak_rank: int | None
    peak_listeners: int | None

    def to_dict(self) -> dict:
        return asdict(self)


def is_allowed(url: str, robots_txt: str, user_agent: str = USER_AGENT) -> bool:
    """Would this site's robots.txt let us fetch `url`?"""
    parser = RobotFileParser()
    parser.parse(robots_txt.splitlines())
    return parser.can_fetch(user_agent, url)


def fetch(url: str = URL, session: requests.Session | None = None, retries: int = 3) -> str:
    """Download a page after checking robots.txt. Retries brief server errors."""
    session = session or requests.Session()
    headers = {"User-Agent": USER_AGENT}

    robots_url = urljoin(f"{urlparse(url).scheme}://{urlparse(url).netloc}", "/robots.txt")
    robots = session.get(robots_url, headers=headers, timeout=TIMEOUT_SECONDS)
    # No robots.txt (404) means no restrictions; anything else must allow us.
    if robots.status_code != 404 and not is_allowed(url, robots.text):
        raise ScrapeError(f"robots.txt at {robots_url} does not allow fetching {url}")

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
            if response.status_code < 500:
                response.raise_for_status()
                # kworb sends no charset in its Content-Type header (only
                # <meta charset="UTF-8"> in the page), and requests then
                # assumes ISO-8859-1, turning "Beyoncé" into "BeyoncÃ©".
                if "charset=" not in response.headers.get("Content-Type", "").lower():
                    response.encoding = "utf-8"
                return response.text
            last_error = ScrapeError(f"HTTP {response.status_code} from {url}")
        except requests.RequestException as error:
            last_error = error
        if attempt < retries:
            time.sleep(2 ** attempt)  # back off: 2s, 4s

    raise ScrapeError(f"Could not fetch {url}: {last_error}")


def _to_int(text: str, field: str, allow_empty: bool = False) -> int | None:
    """'127,951,989' -> 127951989, '-330,218' -> -330218, '+54,112' -> 54112."""
    cleaned = text.strip().replace(",", "").replace("+", "").replace("−", "-")
    if cleaned == "" and allow_empty:
        return None
    try:
        return int(cleaned)
    except ValueError:
        raise ScrapeError(f"Unexpected value {text!r} in column {field!r}") from None


def parse_listeners(html: str) -> list[ArtistListeners]:
    """Turn the kworb listeners page into rows. Raises ScrapeError if the layout changed."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        raise ScrapeError("No table found on the page; the layout may have changed.")

    headers = [th.get_text(strip=True) for th in table.find_all("th")]
    if headers != EXPECTED_HEADERS:
        raise ScrapeError(f"Page layout changed. Expected columns {EXPECTED_HEADERS}, got {headers}.")

    rows: list[ArtistListeners] = []
    body = table.find("tbody") or table
    for tr in body.find_all("tr"):
        cells = tr.find_all("td")
        if not cells:
            continue  # header row inside the body
        if len(cells) != len(EXPECTED_HEADERS):
            raise ScrapeError(f"Row has {len(cells)} cells, expected {len(EXPECTED_HEADERS)}: {tr.get_text(' ', strip=True)!r}")

        link = cells[1].find("a")
        id_match = SPOTIFY_ID_IN_LINK.search(link.get("href", "")) if link else None
        artist = cells[1].get_text(strip=True)
        if not artist:
            raise ScrapeError(f"Empty artist name in row {tr.get_text(' ', strip=True)!r}")

        rows.append(ArtistListeners(
            rank=_to_int(cells[0].get_text(), "#"),
            artist=artist,
            spotify_id=id_match.group(1) if id_match else None,
            monthly_listeners=_to_int(cells[2].get_text(), "Listeners"),
            daily_change=_to_int(cells[3].get_text(), "Daily +/-", allow_empty=True),
            peak_rank=_to_int(cells[4].get_text(), "Peak", allow_empty=True),
            peak_listeners=_to_int(cells[5].get_text(), "PkListeners", allow_empty=True),
        ))

    if not rows:
        raise ScrapeError("The table had no artist rows; the layout may have changed.")
    return rows


def scrape(top: int | None = None, session: requests.Session | None = None) -> list[ArtistListeners]:
    """Fetch and parse the page. `top` keeps only the first N artists."""
    rows = parse_listeners(fetch(URL, session=session))
    return rows[:top] if top else rows
