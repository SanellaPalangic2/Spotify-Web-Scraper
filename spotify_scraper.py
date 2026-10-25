# Web Scraper Application


import requests
from spotipy.oauth2 import SpotifyClientCredentials
import spotipy
from spotipy.oauth2 import SpotifyOAuth

import csv
import os
import sys
from datetime import datetime

import pandas as pd
import matplotlib.pyplot as plt


# Spotify app credentials come from environment variables, never from the code.
# Set SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET before running (see README).
CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
# Must match the Redirect URI configured in your Spotify app
REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI", "http://localhost:3000")

if not CLIENT_ID or not CLIENT_SECRET:
    sys.exit(
        "Missing Spotify credentials. Set the SPOTIPY_CLIENT_ID and "
        "SPOTIPY_CLIENT_SECRET environment variables (see README)."
    )

# Define the required scope for permissions
SCOPE = "playlist-read-private playlist-read-collaborative"


# Authenticate with Spotify API
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    scope=SCOPE
))

def save_artist_popularity_to_csv(artists, filename="artist_popularity.csv"):
    """
    Save artist popularity data to a CSV file.
    """
    with open(filename, mode='a', newline='') as file:
        writer = csv.writer(file)
        # Add timestamp to track changes over time
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for artist, popularity in artists.items():
            writer.writerow([timestamp, artist, popularity])

    """
Each time the program runs, it adds new rows to the file.
Data from previous runs will remain in the file.
"""



def plot_popularity_trends(filename="artist_popularity.csv"):
    """
    Plot artist popularity trends from the CSV file.
    """
    try:
        df = pd.read_csv(filename, names=["timestamp", "artist", "popularity"], encoding="latin-1")
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        for artist in df['artist'].unique():
            artist_data = df[df['artist'] == artist]
            plt.plot(artist_data['timestamp'], artist_data['popularity'], label=artist)

        plt.xlabel("Date")
        plt.ylabel("Popularity")
        plt.title("Artist Popularity Trends")
        plt.legend()
        plt.show()

    except Exception as e:
        print(f"Error reading file: {e}")



def get_artist_popularity(artist_id):
    """
    Fetch the popularity of an artist.
    """
    artist = sp.artist(artist_id)
    return artist['name'], artist['popularity']

def get_artists_from_playlist(playlist_id):
    """
    Extract unique artists from a playlist and fetch their popularity.
    """
    tracks = get_playlist_tracks(playlist_id)
    artists = {}
    
    for item in tracks:
        for artist in item['track']['artists']:
            artist_id = artist['id']
            if artist_id not in artists:
                artist_name, popularity = get_artist_popularity(artist_id)
                artists[artist_name] = popularity
    
    return artists


def get_playlist_details(playlist_id):
    """
    Fetch details of a playlist including name, description, and total tracks.
    """
    playlist = sp.playlist(playlist_id)
    print(f"Playlist Name: {playlist['name']}")
    print(f"Description: {playlist['description']}")
    print(f"Total Tracks: {playlist['tracks']['total']}")
    print("-" * 30)
    return playlist

def get_playlist_tracks(playlist_id):
    """
    Fetch all tracks from a playlist.
    """
    results = sp.playlist_tracks(playlist_id)
    tracks = results['items']
    # Handle pagination
    while results['next']:
        results = sp.next(results)
        tracks.extend(results['items'])
    return tracks

if __name__ == "__main__":
    # Define playlist ID
    playlist_id = "37i9dQZF1DXcBWIGoYBM5M"  # Replace with your playlist ID

    # Fetch artists and their popularity
    artists = get_artists_from_playlist(playlist_id)
    print("Fetched Artists and Popularity:", artists)

    # Save artist popularity to CSV
    save_artist_popularity_to_csv(artists)
    print("Artist popularity saved to CSV.")

    # Plot popularity trends
    print("Plotting popularity trends...")
    plot_popularity_trends()

    # Fetch playlist details
    playlist = get_playlist_details(playlist_id)

    # Fetch and display tracks
    print(f"Tracks in the playlist '{playlist['name']}':")
    tracks = get_playlist_tracks(playlist_id)
    for idx, item in enumerate(tracks):
        track = item['track']
        print(f"{idx + 1}. {track['name']} by {', '.join(artist['name'] for artist in track['artists'])}")
