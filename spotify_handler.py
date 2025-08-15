import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from typing import Optional, List, Dict, Any
import tekore as tk


SERVICE_NAME = "SpotifyPlaylistMCP"
logging.basicConfig(
    level=logging.INFO,
    format=f"[%(asctime)s] [{SERVICE_NAME}.%(name)s:%(lineno)d] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

class SpotifyHandler:
    """Simplified Spotify handler using Tekore."""
    
    def __init__(self):
        """Initialize Spotify handler with environment variables."""
        load_dotenv()
        self.client_id = os.getenv("SPOTIFY_CLIENT_ID", '')
        self.client_secret = os.getenv("SPOTIFY_CLIENT_SECRET", '') 
        
        if not self.client_id or not self.client_secret:
            raise ValueError("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set")
        
        port = int(os.getenv("PORT", 10000))
        self.redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", f"http://localhost:{port}/spotify/callback")
        
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
        self.app_client: Optional[tk.Spotify] = None
        
        # App token for search without authentication
        self._initialize_app_client()
    
    def _initialize_app_client(self):
        """Initialize app client for public operations."""
        try:
            app_token = tk.request_client_token(self.client_id, self.client_secret)
            self.app_client = tk.Spotify(app_token)
            logger.info("App client initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to get app token: {e}")
            self.app_client = None
    
    def get_auth_url(self) -> str:
        """Get Spotify authorization URL."""
        auth_url = self.cred.user_authorisation_url(scope=self.scope)
        logger.info(f"Generated auth URL: {auth_url}")
        return auth_url
    
    def authenticate_with_code(self, code: str) -> bool:
        """Authenticate with authorization code."""
        try:
            logger.info(f"Attempting to authenticate with code: {code[:10]}...")
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
        
        logger.info("Fetching user data...")
        
        user_data = {
            "timestamp": datetime.now().isoformat(),
            "user_profile": self._get_user_profile(),
            "top_tracks": self._get_top_tracks(),
            "recent_tracks": self._get_recent_tracks(),
            "playlists": self._get_playlists()
        }
        
        # Save to file
        filename = f"user_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, indent=2, default=str, ensure_ascii=False)
        
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
                    "uri": item.track.uri,
                    "popularity": getattr(item.track, 'popularity', 0)
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
            
            user = self.client.current_user()
            playlists = self.client.playlists(user.id, limit=limit)
            playlist_list = []
            
            for playlist in playlists.items:
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
            # Use authenticated client if available, otherwise use app client
            client = self.client if self.is_authenticated() else self.app_client
            if not client:
                logger.error("No Spotify client available for search")
                return []
            
            logger.info(f"Searching for tracks: '{query}' (limit: {limit})")
            results = client.search(query=query, types=('track',), limit=limit)
            
            if results and len(results) > 0:
                tracks = results[0]  # First element is tracks paging
                track_list = [
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
                logger.info(f"Found {len(track_list)} tracks for query '{query}'")
                return track_list
            return []
        except Exception as e:
            logger.error(f"Search failed for '{query}': {e}")
            return []
    
    def get_recommendations(self, seed_track_ids: List[str], limit: int = 20) -> List[Dict[str, Any]]:
        """Get track recommendations."""
        if not self.is_authenticated():
            logger.warning("Not authenticated - cannot get recommendations")
            return []
        
        try:
            if not self.client:
                return []
            
            # Filter valid track IDs
            valid_seeds = [track_id for track_id in seed_track_ids if track_id][:5]  # Max 5 seeds
            if not valid_seeds:
                logger.warning("No valid seed tracks for recommendations")
                return []
            
            logger.info(f"Getting recommendations with {len(valid_seeds)} seed tracks")
            recommendations = self.client.recommendations(
                seed_tracks=valid_seeds,
                limit=limit
            )
            
            rec_list = [
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
            logger.info(f"Got {len(rec_list)} recommendations")
            return rec_list
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
            logger.info(f"Creating playlist '{name}' for user {user.display_name}")
            
            playlist = self.client.playlist_create(
                user_id=user.id,
                name=name,
                description=description,
                public=public
            )
            
            playlist_url = f"https://open.spotify.com/playlist/{playlist.id}"
            logger.info(f"Created playlist: {name} (ID: {playlist.id}) - {playlist_url}")
            return playlist_url
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
            
            # Filter valid track URIs
            valid_uris = [uri for uri in track_uris if uri and uri.startswith('spotify:track:')]
            
            if not valid_uris:
                logger.warning("No valid track URIs to add")
                return 0
            
            logger.info(f"Adding {len(valid_uris)} tracks to playlist {playlist_id}")
            
            # Add tracks in batches (Spotify API limit is 100 per request)
            batch_size = 100
            added_count = 0
            
            for i in range(0, len(valid_uris), batch_size):
                batch = valid_uris[i:i + batch_size]
                self.client.playlist_add(playlist_id, batch)
                added_count += len(batch)
                logger.info(f"Added batch of {len(batch)} tracks")
            
            logger.info(f"Successfully added {added_count} tracks to playlist")
            return added_count
            
        except Exception as e:
            logger.error(f"Adding tracks failed: {e}")
            raise