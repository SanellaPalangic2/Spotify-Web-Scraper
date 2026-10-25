"""Command line: python -m tracker <command>

  scrape     Scrape monthly listeners (no Spotify login needed)
  playlist   Record API popularity for a playlist's artists
  compare    Popularity vs monthly listeners for a playlist's artists
  plot       Charts of how artists change over time
"""

from __future__ import annotations

import argparse
import sys

from tracker import storage
from tracker.scraper import URL, ScrapeError, scrape

DEFAULT_PLAYLIST = "37i9dQZF1DXcBWIGoYBM5M"  # replace with your own playlist ID


def cmd_scrape(args) -> int:
    try:
        rows = scrape(top=args.top)
    except ScrapeError as error:
        print(f"Scrape failed: {error}", file=sys.stderr)
        return 1

    path = storage.save_listeners_snapshot(rows)
    print(f"Scraped {len(rows)} artists from {URL}")
    print(f"Saved {path.relative_to(storage.DATA_DIR.parent)}")
    for row in rows[:5]:
        print(f"  {row.rank:>3}. {row.artist}: {row.monthly_listeners:,} monthly listeners")
    return 0


def _playlist_artists(playlist_id: str):
    from tracker import spotify_api

    sp = spotify_api.get_client()
    print(f"Playlist: {spotify_api.get_playlist_name(sp, playlist_id)}")
    return spotify_api.get_playlist_artists(sp, playlist_id)


def cmd_playlist(args) -> int:
    from tracker.spotify_api import CredentialsError

    try:
        artists = _playlist_artists(args.playlist)
    except CredentialsError as error:
        print(error, file=sys.stderr)
        return 1

    path = storage.append_popularity(artists)
    print(f"Recorded popularity for {len(artists)} artists in {path.relative_to(storage.DATA_DIR.parent)}")
    for artist in sorted(artists, key=lambda a: a["popularity"], reverse=True)[:10]:
        print(f"  {artist['popularity']:>3}  {artist['name']}")
    return 0


def cmd_compare(args) -> int:
    from tracker.compare import compare
    from tracker.spotify_api import CredentialsError

    listeners = storage.latest_listeners()
    if listeners.empty:
        print("No scraped data yet. Run: python -m tracker scrape", file=sys.stderr)
        return 1

    try:
        artists = _playlist_artists(args.playlist)
    except CredentialsError as error:
        print(error, file=sys.stderr)
        return 1

    result = compare(artists, listeners)
    out = storage.DATA_DIR / "comparison.csv"
    result.to_csv(out, index=False, encoding="utf-8")
    print(result.to_string(index=False))
    print(f"\nSaved {out.relative_to(storage.DATA_DIR.parent)}")

    if not args.no_chart:
        from tracker.plots import plot_comparison

        try:
            print(f"Chart: {plot_comparison(result, show=args.show)}")
        except ValueError as error:
            print(error)
    return 0


def cmd_plot(args) -> int:
    from tracker.plots import plot_history

    if args.source == "listeners":
        df = storage.load_listeners_history()
        options = dict(value="monthly_listeners", time_col="date", title="Monthly listeners over time",
                       ylabel="Monthly listeners", filename="monthly_listeners.png")
    else:
        df = storage.load_popularity()
        options = dict(value="popularity", time_col="timestamp", title="Spotify popularity over time",
                       ylabel="Popularity (0-100)", filename="popularity.png")

    try:
        path = plot_history(df, artists=args.artist, top=args.top, show=args.show, **options)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"Chart: {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m tracker", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("scrape", help="scrape monthly listeners from kworb.net")
    p.add_argument("--top", type=int, default=500, help="keep the top N artists (default 500)")
    p.set_defaults(func=cmd_scrape)

    p = sub.add_parser("playlist", help="record API popularity for a playlist's artists")
    p.add_argument("--playlist", default=DEFAULT_PLAYLIST, help="Spotify playlist ID")
    p.set_defaults(func=cmd_playlist)

    p = sub.add_parser("compare", help="popularity vs monthly listeners for a playlist")
    p.add_argument("--playlist", default=DEFAULT_PLAYLIST, help="Spotify playlist ID")
    p.add_argument("--no-chart", action="store_true", help="skip the chart")
    p.add_argument("--show", action="store_true", help="open the chart in a window")
    p.set_defaults(func=cmd_compare)

    p = sub.add_parser("plot", help="chart artists over time")
    p.add_argument("--source", choices=["listeners", "popularity"], default="listeners")
    p.add_argument("--artist", action="append", help="artist to include (repeatable)")
    p.add_argument("--top", type=int, default=10, help="otherwise, the top N by latest value (default 10)")
    p.add_argument("--show", action="store_true", help="open the chart in a window")
    p.set_defaults(func=cmd_plot)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
