The Web Scraper Application is a Python-based tool that integrates with the Spotify API to analyze and visualize artist popularity trends from playlists.
Key features include fetching detailed playlist information, extracting unique artists, and saving their popularity scores over time into a CSV file. 
The application also provides the ability to plot popularity trends for individual artists, enabling users to observe changes in popularity across different timeframes. 
This program leverages Spotify's OAuth for secure access and supports handling large playlists through pagination.

## Setup

Install the dependencies:

```
pip install spotipy pandas matplotlib
```

Create an app in the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and add a Redirect URI (the script defaults to `http://localhost:3000`). Then set your credentials as environment variables. They are never stored in the code.

PowerShell (Windows):

```
$env:SPOTIPY_CLIENT_ID = "your-client-id"
$env:SPOTIPY_CLIENT_SECRET = "your-client-secret"
# optional, if your app uses a different Redirect URI:
$env:SPOTIPY_REDIRECT_URI = "http://localhost:3000"
python spotify_scraper.py
```

macOS / Linux:

```
export SPOTIPY_CLIENT_ID="your-client-id"
export SPOTIPY_CLIENT_SECRET="your-client-secret"
python spotify_scraper.py
```

Spotipy caches your login token in a local `.cache` file. It is gitignored; don't commit it.
