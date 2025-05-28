import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get Spotify API credentials from environment variables
CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI', 'http://127.0.0.1:8888/callback')

def eliminar_todos_los_podcasts():
    # Validate credentials
    if not all([CLIENT_ID, CLIENT_SECRET]):
        raise ValueError("Faltan credenciales de Spotify. Asegúrate de configurar SPOTIFY_CLIENT_ID y SPOTIFY_CLIENT_SECRET en tu archivo .env")
    
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
