import os
from typing import Dict, Any, Optional, Tuple
import spotipy
from spotipy.oauth2 import SpotifyOAuth

class SpotifyAuthHandler:
    """Handles Spotify OAuth authentication and API client management."""
    
    def __init__(self):
        self.client_id = os.getenv("SPOTIFY_CLIENT_ID")
        self.client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        self.redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8080/callback")
        
        if not self.client_id or not self.client_secret:
            raise ValueError("Spotify credentials not found in environment variables")
        
        self.oauth = SpotifyOAuth(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            scope="playlist-modify-public playlist-modify-private user-read-recently-played user-top-read user-library-read user-read-playback-state"
        )
        
        self.client: Optional[spotipy.Spotify] = None
    
    def get_authorization_url(self) -> str:
        """Get Spotify authorization URL for user authentication."""
        return self.oauth.get_authorize_url()
    
    def authenticate_with_code(self, code: str) -> bool:
        """
        Authenticate using authorization code from callback.
        
        Args:
            code: Authorization code from Spotify callback
            
        Returns:
            bool: True if authentication successful
        """
        try:
            token_info = self.oauth.get_access_token(code)
            self.client = spotipy.Spotify(auth=token_info['access_token'])
            return True
        except Exception as e:
            print(f"Authentication error: {e}")
            return False
    
    def get_cached_client(self) -> Optional[spotipy.Spotify]:
        """Get authenticated Spotify client from cached token."""
        try:
            token_info = self.oauth.get_cached_token()
            if token_info:
                self.client = spotipy.Spotify(auth=token_info['access_token'])
                return self.client
        except Exception as e:
            print(f"Token cache error: {e}")
        return None
    
    def get_user_profile(self) -> Dict[str, Any]:
        """Get current user's Spotify profile."""
        if not self.client:
            raise ValueError("Not authenticated with Spotify")
        
        return self.client.current_user()
    
    def get_user_top_tracks(self, limit: int = 20, time_range: str = "medium_term") -> Dict[str, Any]:
        """
        Get user's top tracks.
        
        Args:
            limit: Number of tracks to fetch (max 50)
            time_range: short_term, medium_term, or long_term
        """
        if not self.client:
            raise ValueError("Not authenticated with Spotify")
        
        return self.client.current_user_top_tracks(limit=limit, time_range=time_range)
    
    def get_user_recently_played(self, limit: int = 50) -> Dict[str, Any]:
        """Get user's recently played tracks."""
        if not self.client:
            raise ValueError("Not authenticated with Spotify")
        
        return self.client.current_user_recently_played(limit=limit)
    
    def search_tracks(self, query: str, limit: int = 20) -> Dict[str, Any]:
        """Search for tracks on Spotify."""
        if not self.client:
            raise ValueError("Not authenticated with Spotify")
        
        return self.client.search(q=query, type="track", limit=limit)
    
    def get_recommendations(self, **kwargs) -> Dict[str, Any]:
        """
        Get track recommendations from Spotify.
        
        Args:
            seed_artists: List of artist IDs
            seed_genres: List of genre names
            seed_tracks: List of track IDs
            target_valence: Target valence (0.0 to 1.0)
            target_energy: Target energy (0.0 to 1.0)
            target_danceability: Target danceability (0.0 to 1.0)
            limit: Number of recommendations (max 100)
        """
        if not self.client:
            raise ValueError("Not authenticated with Spotify")
        
        return self.client.recommendations(**kwargs)
    
    def create_playlist(self, user_id: str, name: str, description: str = "", public: bool = True) -> Dict[str, Any]:
        """Create a new playlist."""
        if not self.client:
            raise ValueError("Not authenticated with Spotify")
        
        return self.client.user_playlist_create(
            user=user_id,
            name=name,
            description=description,
            public=public
        )
    
    def add_tracks_to_playlist(self, playlist_id: str, track_uris: list) -> Dict[str, Any]:
        """Add tracks to a playlist."""
        if not self.client:
            raise ValueError("Not authenticated with Spotify")
        
        # Spotify API allows max 100 tracks per request
        results = []
        for i in range(0, len(track_uris), 100):
            batch = track_uris[i:i+100]
            result = self.client.playlist_add_items(playlist_id, batch)
            results.append(result)
        
        return {"results": results}
    
    def get_track_audio_features(self, track_ids: list) -> Dict[str, Any]:
        """Get audio features for tracks."""
        if not self.client:
            raise ValueError("Not authenticated with Spotify")
        
        return self.client.audio_features(track_ids)