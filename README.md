# Spotify Artist Tracker

A Python tool that **scrapes Spotify monthly-listener counts from the web** and
combines them with data from the **official Spotify Web API**, then tracks how
artists change over time. A scheduled GitHub Action scrapes once a day, so the
repo keeps building its own dataset in [`data/listeners/`](data/listeners/).

## Why scrape?

The Spotify Web API gives each artist a `popularity` score from 0 to 100, but
**not the monthly-listener count** shown on artist pages, which is the number
people actually talk about. [kworb.net](https://kworb.net/spotify/listeners.html)
publishes a public table of top artists by monthly listeners, so this project
scrapes that table and joins it with API data.

## Scraping responsibly

- **Spotify itself is not scraped.** Spotify's Terms of Use forbid automated
  collection from its service, so Spotify data comes only from the official API.
- **robots.txt is checked in code** before every fetch (kworb.net allows crawling).
- **The scraper identifies itself** with a descriptive `User-Agent` and uses timeouts.
- **One page request per run,** once a day, at an off-peak minute.
- **It fails loudly if the page layout changes**, instead of saving bad data.
- **Source credit:** monthly-listener figures are collected by kworb.net from Spotify.

## How it works

```
kworb.net page ──► scraper.py ──► data/listeners/YYYY-MM-DD.csv ──┐
  (requests + BeautifulSoup:      (one UTF-8 file per day)        │
   robots check, layout check,                                    ├──► compare.py ──► comparison + chart
   numbers parsed, Spotify ID                                     │    (joined by Spotify artist ID)
   taken from each artist link)                                   │
Spotify Web API ──► spotify_api.py ──► data/artist_popularity.csv ┘
  (spotipy, OAuth, credentials from env vars)
```

- **Matching by Spotify ID, not name.** Each artist link on the scraped page
  contains the artist's Spotify ID (`artist/0du5cEVh5yTK9QJze8zA0C_songs.html`),
  so scraped rows join to API rows exactly, regardless of spelling, accents
  (ROSÉ, Beyoncé), or artists who share a name.
- **One file per day.** Small git diffs, and re-running on the same day replaces
  that day's file instead of duplicating it.
- **Efficient API use.** Artists are fetched 50 at a time (2 requests for a
  60-artist playlist instead of 60), and local files or removed tracks in a
  playlist are skipped instead of crashing.

## Setup

```
git clone https://github.com/SanellaPalangic2/Spotify-Web-Scraper.git
cd Spotify-Web-Scraper
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
```

Scraping needs no Spotify account. The `playlist` and `compare` commands use the
Spotify API: create an app in the
[Spotify Developer Dashboard](https://developer.spotify.com/dashboard), add a
Redirect URI (the default is `http://localhost:3000`), and set your credentials
as environment variables. They are never stored in the code.

```
# PowerShell
$env:SPOTIPY_CLIENT_ID = "your-client-id"
$env:SPOTIPY_CLIENT_SECRET = "your-client-secret"
$env:SPOTIPY_REDIRECT_URI = "http://localhost:3000"   # optional

# macOS / Linux
export SPOTIPY_CLIENT_ID="your-client-id"
export SPOTIPY_CLIENT_SECRET="your-client-secret"
```

Spotipy saves your login token in a local `.cache` file, which is gitignored.

## Usage

```
python -m tracker scrape                      # scrape the top 500 artists by monthly listeners
python -m tracker scrape --top 100

python -m tracker playlist --playlist <ID>    # record API popularity for a playlist's artists
python -m tracker compare --playlist <ID>     # popularity vs monthly listeners (+ chart)

python -m tracker plot                        # monthly listeners over time, top 10 artists
python -m tracker plot --source popularity    # API popularity over time
python -m tracker plot --artist "Taylor Swift" --artist "Bad Bunny" --show
```

Charts are saved to `charts/`. Find a playlist ID in its share link:
`open.spotify.com/playlist/<ID>`.

## Data

| File | Columns |
|---|---|
| `data/listeners/YYYY-MM-DD.csv` | `scraped_at` (UTC), `rank`, `artist`, `spotify_id`, `monthly_listeners`, `daily_change`, `peak_rank`, `peak_listeners` |
| `data/artist_popularity.csv` | `timestamp`, `artist`, `popularity` (no header; includes the original Nov 2024 snapshots) |

## Automation

[`.github/workflows/scrape.yml`](.github/workflows/scrape.yml) runs daily at
06:17 UTC (or on demand from the **Actions** tab): it installs dependencies,
runs the test suite, scrapes, and commits the new snapshot. If the page layout
ever changes, the run fails and GitHub emails you, and no bad data is committed.

## Tests

```
python -m pytest
```

The tests never touch the network: they parse small hand-made HTML pages with
the same structure as the real one (`tests/fixtures/`) and use fake HTTP and
Spotify clients. They cover parsing, the layout-change check, robots.txt
handling, retries, character encoding, storage, ID-based matching, playlist
pagination and batching, and the command line.

## What I learned / what broke

- **Accented names came out garbled** ("BeyoncÃ©") on the first live scrape.
  kworb's server doesn't declare a charset in its HTTP header (only in the page's
  `<meta>` tag), so `requests` assumed ISO-8859-1. Fixed by defaulting to UTF-8,
  with a test that fails on the old behavior.
- **The original CSV had the same problem** ("ROS\xc9"): it was written in
  Windows' default encoding. Converted it to UTF-8, and all files are now
  written and read as UTF-8 explicitly.
- **Credentials were hardcoded** in the first version of this repo. They now come
  only from environment variables. Removing them from the code doesn't remove them
  from git history, so the exposed secret has to be rotated in the Spotify dashboard.

## Limitations

- Only artists in kworb's top list (500 by default) have monthly-listener data;
  others show up empty in comparisons.
- If kworb changes its layout, scraping stops (by design) until the parser is updated.
- Spotify restricted API access to some of its own editorial and algorithmic
  playlists for newer apps in late 2024. If a playlist returns a 404, try one you created.
- History starts on the first scrape; daily granularity only.
