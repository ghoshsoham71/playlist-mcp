import os
from typing import Optional, List, Dict, Any
import tekore as tk


class TekoreHandler:
    """Simplified Tekore handler for Spotify operations."""
    
    def __init__(self):
        self.client_id = os.getenv("SPOTIFY_CLIENT_ID")
        self.client_secret = os.getenv("SPOTIFY_CLIENT_SECRET") 
        self.redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8080/callback")
        
        if not self.client_id or not self.client_secret:
            raise ValueError("Missing Spotify credentials in environment variables")
        
        self.cred = tk.Credentials(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri
        )
        
        self.scope = (
            tk.scope.playlist_modify_public + tk.scope.playlist_modify_private +
            tk.scope.user_read_recently_played + tk.scope.user_top_read +
            tk.scope.user_library_read + tk.scope.user_read_private
        )
        
        self.client: Optional[tk.Spotify] = None
        self.token: Optional[tk.Token] = None
    
    def get_auth_url(self) -> str:
        """Get Spotify authorization URL."""
        return self.cred.user_authorisation_url(scope=self.scope)
    
    def authenticate(self, code: str) -> bool:
        """Authenticate with authorization code."""
        try:
            self.token = self.cred.request_user_token(code)
            if self.token:
                self.client = tk.Spotify(self.token)
                return True
            return False
        except Exception:
            return False
    
    def refresh_if_needed(self) -> bool:
        """Refresh token if expiring."""
        if not self.token or not self.token.refresh_token:
            return False
        
        if self.token.is_expiring:
            try:
                self.token = self.cred.refresh_user_token(self.token.refresh_token)
                self.client = tk.Spotify(self.token)
                return True
            except Exception:
                return False
        return True
    
    def is_authenticated(self) -> bool:
        """Check if authenticated and token is valid."""
        return self.client is not None and self.refresh_if_needed()
    
    # Core API methods
    def get_user_top_tracks(self, limit: int = 50, time_range: str = "medium_term"):
        """Get user's top tracks."""
        if not self.is_authenticated() or not self.client:
            raise RuntimeError("Not authenticated")
        return self.client.current_user_top_tracks(limit=limit, time_range=time_range)
    
    def get_recent_tracks(self, limit: int = 50):
        """Get recently played tracks."""
        if not self.is_authenticated() or not self.client:
            raise RuntimeError("Not authenticated")
        return self.client.playback_recently_played(limit=limit)
        
    def get_recommendations(self, **kwargs):
        """Get track recommendations."""
        if not self.is_authenticated() or not self.client:
            raise RuntimeError("Not authenticated")
        return self.client.recommendations(**kwargs)
    
    def search_tracks(self, query: str, limit: int = 20):
        """Search for tracks."""
        if not self.is_authenticated() or not self.client:
            raise RuntimeError("Not authenticated")
        results = self.client.search(query=query, types=('track',), limit=limit)
        return results[0]  # Return tracks paging
    
    def create_playlist(self, name: str, description: str = "", public: bool = False):
        """Create a new playlist."""
        if not self.is_authenticated() or not self.client:
            raise RuntimeError("Not authenticated")
        user = self.client.current_user()
        return self.client.playlist_create(
            user_id=user.id,
            name=name,
            description=description,
            public=public
        )
    
    def add_tracks_to_playlist(self, playlist_id: str, track_uris: List[str]):
        """Add tracks to playlist in batches."""
        if not self.is_authenticated() or not self.client:
            raise RuntimeError("Not authenticated")
        
        # Add tracks in batches of 100
        for i in range(0, len(track_uris), 100):
            batch = track_uris[i:i + 100]
            self.client.playlist_add(playlist_id, batch)
    
    def get_audio_features(self, track_ids: List[str]):
        """Get audio features for tracks."""
        if not self.is_authenticated() or not self.client:
            raise RuntimeError("Not authenticated")
        return self.client.tracks_audio_features(track_ids)