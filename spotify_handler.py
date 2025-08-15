import os
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
import tekore as tk

logger = logging.getLogger(__name__)

class SpotifyHandler:
    """Simplified Spotify handler using Tekore."""
    
    def __init__(self):
        self.client_id = os.getenv("SPOTIFY_CLIENT_ID")
        self.client_secret = os.getenv("SPOTIFY_CLIENT_SECRET") 
        
        if not self.client_id or not self.client_secret:
            raise ValueError("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set")
        
        port = int(os.getenv("PORT", 10000))
        self.redirect_uri = f"http://localhost:{port}/callback"
        
        self.cred = tk.Credentials(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri
        )
        
        self.scope = (
            tk.scope.playlist_modify_public + tk.scope.playlist_modify_private +
            tk.scope.user_read_recently_played + tk.scope.user_top_read +
            tk.scope.user_library_read + tk.scope.user_read_private +
            tk.scope.playlist_read_private
        )
        
        self.client: Optional[tk.Spotify] = None
        self.token: Optional[tk.Token] = None
        
        # App token for search without authentication
        try:
            app_token = tk.request_client_token(self.client_id, self.client_secret)
            self.app_client = tk.Spotify(app_token)
        except Exception as e:
            logger.warning(f"Failed to get app token: {e}")
            self.app_client = None
    
    def get_auth_url(self) -> str:
        """Get Spotify authorization URL."""
        return self.cred.user_authorisation_url(scope=self.scope)
    
    def authenticate_with_code(self, code: str) -> bool:
        """Authenticate with authorization code."""
        try:
            self.token = self.cred.request_user_token(code)
            if self.token:
                self.client = tk.Spotify(self.token)
                # Test the connection
                user = self.client.current_user()
                logger.info(f"Authenticated user: {user.display_name}")
                return True
            return False
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return self.client is not None and self.token is not None
    
    async def fetch_all_user_data(self) -> Dict[str, Any]:
        """Fetch all user data and save to file."""
        if not self.is_authenticated():
            raise RuntimeError("Not authenticated")
        
        user_data = {
            "timestamp": datetime.now().isoformat(),
            "user_profile": self._get_user_profile(),
            "top_tracks": self._get_top_tracks(),
            "recent_tracks": self._get_recent_tracks(),
            "playlists": self._get_playlists()
        }
        
        # Save to file
        filename = f"user_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(user_data, f, indent=2, default=str)
        
        logger.info(f"User data saved to {filename}")
        return user_data
    
    def _get_user_profile(self) -> Optional[Dict[str, Any]]:
        """Get user profile."""
        try:
            if not self.client:
                return None
            user = self.client.current_user()
            return {
                "id": user.id,
                "display_name": user.display_name,
                "email": getattr(user, 'email', None),
                "country": getattr(user, 'country', None),
                "followers": user.followers.total if user.followers else 0
            }
        except Exception as e:
            logger.error(f"Failed to get user profile: {e}")
            return None
    
    def _get_top_tracks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get user's top tracks."""
        try:
            if not self.client:
                return []
            tracks = self.client.current_user_top_tracks(limit=limit)
            return [
                {
                    "name": track.name,
                    "artist": ", ".join([artist.name for artist in track.artists]),
                    "album": track.album.name,
                    "id": track.id,
                    "uri": track.uri,
                    "popularity": track.popularity
                }
                for track in tracks.items
            ]
        except Exception as e:
            logger.error(f"Failed to get top tracks: {e}")
            return []
    
    def _get_recent_tracks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recently played tracks."""
        try:
            if not self.client:
                return []
            recent = self.client.playback_recently_played(limit=limit)
            return [
                {
                    "name": item.track.name,
                    "artist": ", ".join([artist.name for artist in item.track.artists]),
                    "played_at": item.played_at.isoformat() if item.played_at else None,
                    "id": item.track.id,
                    "uri": item.track.uri
                }
                for item in recent.items
            ]
        except Exception as e:
            logger.error(f"Failed to get recent tracks: {e}")
            return []
    
    def _get_playlists(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get user's playlists."""
        try:
            if not self.client:
                return []
            
            # Use the correct method to get playlists
            user = self.client.current_user()
            playlists = self.client.playlists(user.id, limit=limit)
            playlist_list = []
            
            for playlist in playlists.items:
                # Handle potential None values in playlist attributes
                playlist_data = {
                    "name": getattr(playlist, 'name', 'Unknown'),
                    "description": getattr(playlist, 'description', '') or "",
                    "tracks_total": getattr(getattr(playlist, 'tracks', None), 'total', 0) if playlist else 0,
                    "id": getattr(playlist, 'id', ''),
                    "public": getattr(playlist, 'public', False)
                }
                playlist_list.append(playlist_data)
            
            return playlist_list
        except Exception as e:
            logger.error(f"Failed to get playlists: {e}")
            return []
    
    def search_tracks(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search for tracks."""
        try:
            client = self.client if self.is_authenticated() else self.app_client
            if not client:
                raise RuntimeError("No Spotify client available")
            
            results = client.search(query=query, types=('track',), limit=limit)
            if results and len(results) > 0:
                tracks = results[0]  # First element is tracks paging
                return [
                    {
                        "name": track.name,
                        "artist": ", ".join([artist.name for artist in track.artists]),
                        "album": track.album.name,
                        "id": track.id,
                        "uri": track.uri,
                        "popularity": track.popularity
                    }
                    for track in tracks.items
                ]
            return []
        except Exception as e:
            logger.error(f"Search failed for '{query}': {e}")
            return []
    
    def get_recommendations(self, seed_track_ids: List[str], limit: int = 20) -> List[Dict[str, Any]]:
        """Get track recommendations."""
        if not self.is_authenticated():
            raise RuntimeError("Not authenticated")
        
        try:
            if not self.client:
                return []
            recommendations = self.client.recommendations(
                seed_tracks=seed_track_ids[:5],  # Max 5 seeds
                limit=limit
            )
            return [
                {
                    "name": track.name,
                    "artist": ", ".join([artist.name for artist in track.artists]),
                    "album": track.album.name,
                    "id": track.id,
                    "uri": track.uri,
                    "popularity": track.popularity
                }
                for track in recommendations.tracks
            ]
        except Exception as e:
            logger.error(f"Recommendations failed: {e}")
            return []
    
    def create_playlist(self, name: str, description: str = "", public: bool = False) -> str:
        """Create a new playlist and return its URL."""
        if not self.is_authenticated():
            raise RuntimeError("Not authenticated")
        
        try:
            if not self.client:
                raise RuntimeError("Client not available")
            user = self.client.current_user()
            playlist = self.client.playlist_create(
                user_id=user.id,
                name=name,
                description=description,
                public=public
            )
            logger.info(f"Created playlist: {name} (ID: {playlist.id})")
            return f"https://open.spotify.com/playlist/{playlist.id}"
        except Exception as e:
            logger.error(f"Playlist creation failed: {e}")
            raise
    
    def add_tracks_to_playlist(self, playlist_id: str, track_uris: List[str]) -> int:
        """Add tracks to playlist."""
        if not self.is_authenticated():
            raise RuntimeError("Not authenticated")
        
        try:
            if not self.client:
                raise RuntimeError("Client not available")
            
            # Extract playlist ID from URL if needed
            if "playlist/" in playlist_id:
                playlist_id = playlist_id.split("playlist/")[-1]
            
            valid_uris = [uri for uri in track_uris if uri.startswith('spotify:track:')]
            
            if valid_uris:
                self.client.playlist_add(playlist_id, valid_uris)
                logger.info(f"Added {len(valid_uris)} tracks to playlist")
            
            return len(valid_uris)
        except Exception as e:
            logger.error(f"Adding tracks failed: {e}")
            raise