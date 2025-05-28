import spotipy
from spotipy.oauth2 import SpotifyOAuth

# Replace with your Spotify API credentials
CLIENT_ID = 'c798243109ac4543be01179d648837d9'
CLIENT_SECRET = '4ec223e6d89d43f5b87c1d6aa1b2a8c7'
REDIRECT_URI = 'http://127.0.0.1:8888/callback'

def eliminar_todos_los_podcasts():
    scope = "user-library-read user-library-modify"
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=CLIENT_ID,
                                                   client_secret=CLIENT_SECRET,
                                                   redirect_uri=REDIRECT_URI,
                                                   scope=scope))
    # Fetch all saved episodes
    results = sp.current_user_saved_episodes(limit=50)
    while results['items']:
        for item in results['items']:
            episode_id = item['episode']['id']
            sp.current_user_saved_episodes_delete([episode_id])
            print(f"Deleted episode: {item['episode']['name']}")

        # Fetch the next batch of episodes
        results = sp.current_user_saved_episodes(limit=50, offset=len(results['items']))

if __name__ == "__main__":
    eliminar_todos_los_podcasts()
