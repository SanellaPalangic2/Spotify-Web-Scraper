"""Charts. Saved as PNG files; pass show=True to also open a window."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

CHARTS_DIR = Path(__file__).resolve().parent.parent / "charts"


def _finish(fig, filename: str, show: bool) -> Path:
    CHARTS_DIR.mkdir(exist_ok=True)
    path = CHARTS_DIR / filename
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    if show:
        plt.show()
    plt.close(fig)
    return path


def plot_history(df: pd.DataFrame, value: str, time_col: str, artists: list[str] | None,
                 top: int, title: str, ylabel: str, filename: str, show: bool = False) -> Path:
    """Line chart over time for chosen artists, or the top N by latest value
    (not every artist at once, which made the original chart unreadable)."""
    if df.empty:
        raise ValueError("No data to plot yet.")

    if artists:
        chosen = [a for a in artists if a in set(df["artist"])]
        missing = sorted(set(artists) - set(chosen))
        if missing:
            print(f"Not in the data: {', '.join(missing)}")
    else:
        latest = df[df[time_col] == df[time_col].max()]
        chosen = latest.nlargest(top, value)["artist"].tolist()

    fig, ax = plt.subplots(figsize=(10, 6))
    for artist in chosen:
        series = df[df["artist"] == artist].sort_values(time_col)
        ax.plot(series[time_col], series[value], marker="o", label=artist)
    ax.set_title(title)
    ax.set_xlabel("Date")
    ax.set_ylabel(ylabel)
    ax.legend(loc="center left", bbox_to_anchor=(1, 0.5))
    fig.autofmt_xdate()
    return _finish(fig, filename, show)


def plot_comparison(comparison: pd.DataFrame, show: bool = False) -> Path:
    """Scatter: API popularity vs scraped monthly listeners."""
    matched = comparison.dropna(subset=["monthly_listeners"])
    if matched.empty:
        raise ValueError("None of the playlist's artists are in the scraped top list.")

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.scatter(matched["monthly_listeners"].astype(float), matched["popularity"])
    for _, row in matched.iterrows():
        ax.annotate(row["name"], (float(row["monthly_listeners"]), row["popularity"]),
                    fontsize=8, xytext=(4, 2), textcoords="offset points")
    ax.set_xscale("log")
    ax.set_title("Spotify popularity score vs monthly listeners")
    ax.set_xlabel("Monthly listeners (scraped, log scale)")
    ax.set_ylabel("Popularity (Spotify API, 0-100)")
    return _finish(fig, "popularity_vs_listeners.png", show)
