"""Spotify Web API: playlist artists and their popularity scores."""

from __future__ import annotations

import os

SCOPE = "playlist-read-private playlist-read-collaborative"
DEFAULT_REDIRECT_URI = "http://localhost:3000"
BATCH_SIZE = 50  # the API's limit for fetching several artists in one call


class CredentialsError(Exception):
    pass


def get_client():
    """An authenticated spotipy client. Credentials come only from environment variables."""
    client_id = os.getenv("SPOTIPY_CLIENT_ID")
    client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise CredentialsError(
            "Missing Spotify credentials. Set the SPOTIPY_CLIENT_ID and "
            "SPOTIPY_CLIENT_SECRET environment variables (see README)."
        )

    # Imported here so the scraper works without spotipy credentials or setup.
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth

    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI", DEFAULT_REDIRECT_URI),
        scope=SCOPE,
    ))


def get_playlist_tracks(sp, playlist_id: str) -> list[dict]:
    """All tracks in a playlist, following pagination."""
    results = sp.playlist_tracks(playlist_id)
    items = list(results["items"])
    while results.get("next"):
        results = sp.next(results)
        items.extend(results["items"])
    return items


def get_playlist_artists(sp, playlist_id: str) -> list[dict]:
    """Unique artists in a playlist with their popularity: [{id, name, popularity}].

    Looks artists up 50 at a time instead of one request per artist, and skips
    local files and removed tracks (which have no track or artist ID).
    """
    artist_ids: list[str] = []
    for item in get_playlist_tracks(sp, playlist_id):
        track = item.get("track")
        if not track:
            continue
        for artist in track.get("artists", []):
            artist_id = artist.get("id")
            if artist_id and artist_id not in artist_ids:
                artist_ids.append(artist_id)

    artists = []
    for start in range(0, len(artist_ids), BATCH_SIZE):
        batch = sp.artists(artist_ids[start:start + BATCH_SIZE])["artists"]
        artists.extend(
            {"id": a["id"], "name": a["name"], "popularity": a["popularity"]}
            for a in batch if a
        )
    return artists


def get_playlist_name(sp, playlist_id: str) -> str:
    return sp.playlist(playlist_id, fields="name")["name"]
