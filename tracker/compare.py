"""Combine API popularity (0-100) with scraped monthly listeners."""

from __future__ import annotations

import pandas as pd


def compare(playlist_artists: list[dict], listeners: pd.DataFrame) -> pd.DataFrame:
    """One row per playlist artist with popularity and, if found, monthly listeners.

    Matched by Spotify artist ID (taken from the scraped page's links), not by
    name, so spelling, accents, and same-named artists can't cause mismatches.
    Artists outside the scraped top list get empty listener columns.
    """
    artists = pd.DataFrame(playlist_artists, columns=["id", "name", "popularity"])
    scraped = listeners[["spotify_id", "rank", "monthly_listeners"]].rename(
        columns={"spotify_id": "id", "rank": "listeners_rank"}
    )
    merged = artists.merge(scraped, on="id", how="left")
    merged["listeners_rank"] = merged["listeners_rank"].astype("Int64")
    merged["monthly_listeners"] = merged["monthly_listeners"].astype("Int64")
    return merged.sort_values("monthly_listeners", ascending=False, na_position="last").reset_index(drop=True)
