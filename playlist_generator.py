"""
Playlist generation using Last.fm API
"""

import asyncio
import hashlib
import json
import logging
import random
import urllib.parse
from typing import Dict, List, Any, Optional
import aiohttp

logger = logging.getLogger(__name__)

class PlaylistGenerator:
    """Generates playlists using Last.fm API"""
    
    def __init__(self, api_key: str, shared_secret: str):
        self.api_key = api_key
        self.shared_secret = shared_secret
        self.base_url = "http://ws.audioscrobbler.com/2.0/"
        self.session = None
        self._session_lock = asyncio.Lock()
    
    async def _get_session(self):
        """Get or create aiohttp session with proper locking"""
        async with self._session_lock:
            if not self.session or self.session.closed:
                connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
                timeout = aiohttp.ClientTimeout(total=30)
                self.session = aiohttp.ClientSession(
                    connector=connector,
                    timeout=timeout
                )
        return self.session
    
    def _generate_signature(self, params: Dict[str, str]) -> str:
        """Generate API signature for Last.fm"""
        # Sort parameters and create signature string
        sorted_params = sorted(params.items())
        sig_string = ''.join([f"{k}{v}" for k, v in sorted_params])
        sig_string += self.shared_secret
        
        return hashlib.md5(sig_string.encode('utf-8')).hexdigest()
    
    async def _make_request(self, method: str, params: Dict[str, Any]) -> Dict:
        """Make authenticated request to Last.fm API"""
        try:
            session = await self._get_session()
            
            # Add common parameters
            request_params = {
                "method": method,
                "api_key": self.api_key,
                "format": "json"
            }
            request_params.update(params)
            
            # Convert all values to strings for the request
            str_params = {k: str(v) for k, v in request_params.items()}
            
            async with session.get(self.base_url, params=str_params) as response:
                if response.status == 200:
                    data = await response.json()
                    if "error" in data:
                        logger.error(f"Last.fm API error: {data['error']}")
                        return {}
                    return data
                else:
                    logger.error(f"Last.fm API HTTP error: {response.status}")
                    return {}
                    
        except asyncio.TimeoutError:
            logger.error("Request timed out")
            return {}
        except Exception as e:
            logger.error(f"Request failed: {str(e)}")
            return {}
    
    async def search_tracks(self, artist: str = "", track: str = "", tag: str = "", limit: int = 50) -> List[Dict]:
        """Search for tracks using Last.fm"""
        params: Dict[str, Any] = {"limit": limit}
        
        if artist:
            params["artist"] = artist
        if track:
            params["track"] = track
        if tag:
            params["tag"] = tag
            
        result = await self._make_request("track.search", params)
        
        if "results" in result and "trackmatches" in result["results"]:
            tracks = result["results"]["trackmatches"].get("track", [])
            # Ensure tracks is a list
            if isinstance(tracks, dict):
                tracks = [tracks]
            return tracks
        return []
    
    async def get_top_tracks_by_tag(self, tag: str, limit: int = 50) -> List[Dict]:
        """Get top tracks for a specific tag/genre"""
        params = {"tag": tag, "limit": limit}
        result = await self._make_request("tag.gettoptracks", params)
        
        if "tracks" in result and "track" in result["tracks"]:
            tracks = result["tracks"]["track"]
            # Ensure tracks is a list
            if isinstance(tracks, dict):
                tracks = [tracks]
            return tracks
        return []
    
    async def get_similar_tracks(self, artist: str, track: str, limit: int = 30) -> List[Dict]:
        """Get similar tracks to a given track"""
        params = {"artist": artist, "track": track, "limit": limit}
        result = await self._make_request("track.getsimilar", params)
        
        if "similartracks" in result and "track" in result["similartracks"]:
            tracks = result["similartracks"]["track"]
            # Ensure tracks is a list
            if isinstance(tracks, dict):
                tracks = [tracks]
            return tracks
        return []
    
    def create_consolidated_playlist_links(self, tracks: List[Dict], mood: str, languages: List[str]) -> Dict[str, Any]:
        """Create consolidated playlist links for streaming platforms"""
        # Create playlist name
        language_str = " & ".join(languages).title()
        playlist_name = f"{mood.title()} {language_str} Playlist"
        
        # Create search queries for different platforms
        spotify_query = f"{mood} {' '.join(languages)} playlist"
        encoded_spotify = urllib.parse.quote(spotify_query)
        
        apple_query = f"{mood} {' '.join(languages)} songs"
        encoded_apple = urllib.parse.quote(apple_query)
        
        youtube_query = f"{mood} {' '.join(languages)} music playlist"
        encoded_youtube = urllib.parse.quote(youtube_query)
        
        lastfm_query = urllib.parse.quote(f"{mood}+{'+'.join(languages)}")
        
        return {
            "playlist_name": playlist_name,
            "spotify_search": f"https://open.spotify.com/search/{encoded_spotify}",
            "apple_music_search": f"https://music.apple.com/search?term={encoded_apple}",
            "youtube_search": f"https://www.youtube.com/results?search_query={encoded_youtube}",
            "lastfm_search": f"https://www.last.fm/search?q={lastfm_query}",
            "track_list": [f"{track['artist']} - {track['track']}" for track in tracks]
        }
    
    def _normalize_track_data(self, track: Dict) -> Optional[Dict]:
        """Normalize track data from different API responses"""
        try:
            # Handle different track data structures
            artist = track.get("artist", {})
            if isinstance(artist, dict):
                artist_name = artist.get("name", "Unknown Artist")
            else:
                artist_name = str(artist)
            
            track_name = track.get("name", "Unknown Track")
            
            # Skip invalid tracks
            if not artist_name or not track_name or artist_name == "Unknown Artist" or track_name == "Unknown Track":
                return None
            
            return {
                "artist": artist_name,
                "track": track_name,
                "url": track.get("url", ""),
                "listeners": int(track.get("listeners", "0")) if track.get("listeners", "0").isdigit() else 0,
                "playcount": int(track.get("playcount", "0")) if track.get("playcount", "0").isdigit() else 0
            }
        except Exception as e:
            logger.debug(f"Error normalizing track: {str(e)}")
            return None
    
    async def generate_playlist(
        self, 
        mood: str, 
        genres: List[str], 
        languages: List[str], 
        duration_minutes: int,
        energy_level: float,
        valence: float
    ) -> str:
        """
        Generate a complete playlist based on analysis results
        """
        try:
            logger.info(f"Generating playlist: mood={mood}, genres={genres}, languages={languages}")
            
            # Calculate number of songs (assuming 4 minutes per song average)
            num_songs = max(3, min(50, duration_minutes // 4))
            
            all_tracks = []
            
            # Search by genres/tags with error handling
            for genre in genres[:3]:  # Limit to top 3 genres
                try:
                    tracks = await self.get_top_tracks_by_tag(genre, limit=20)
                    all_tracks.extend(tracks)
                    await asyncio.sleep(0.1)  # Rate limiting
                except Exception as e:
                    logger.warning(f"Failed to get tracks for genre {genre}: {str(e)}")
            
            # Add language-specific searches
            for language in languages:
                try:
                    if language == "hindi":
                        tracks = await self.get_top_tracks_by_tag("bollywood", limit=15)
                        all_tracks.extend(tracks)
                        await asyncio.sleep(0.1)
                        tracks = await self.get_top_tracks_by_tag("hindi", limit=15)
                        all_tracks.extend(tracks)
                    elif language == "english":
                        tracks = await self.get_top_tracks_by_tag("pop", limit=15)
                        all_tracks.extend(tracks)
                    else:
                        tracks = await self.get_top_tracks_by_tag(language, limit=10)
                        all_tracks.extend(tracks)
                    await asyncio.sleep(0.1)  # Rate limiting
                except Exception as e:
                    logger.warning(f"Failed to get tracks for language {language}: {str(e)}")
            
            # Remove duplicates and filter
            unique_tracks = []
            seen_tracks = set()
            
            for track in all_tracks:
                if not isinstance(track, dict):
                    continue
                
                normalized_track = self._normalize_track_data(track)
                if not normalized_track:
                    continue
                
                track_key = f"{normalized_track['artist'].lower()}|{normalized_track['track'].lower()}"
                
                if track_key not in seen_tracks:
                    seen_tracks.add(track_key)
                    unique_tracks.append(normalized_track)
            
            # Sort by popularity and select top tracks
            unique_tracks.sort(key=lambda x: x.get("listeners", 0) + x.get("playcount", 0), reverse=True)
            selected_tracks = unique_tracks[:num_songs] if len(unique_tracks) >= num_songs else unique_tracks
            
            # If we don't have enough tracks, pad with popular tracks
            if len(selected_tracks) < num_songs:
                try:
                    popular_tracks = await self.get_top_tracks_by_tag("popular", limit=num_songs)
                    for track in popular_tracks:
                        if len(selected_tracks) >= num_songs:
                            break
                            
                        normalized_track = self._normalize_track_data(track)
                        if not normalized_track:
                            continue
                            
                        track_key = f"{normalized_track['artist'].lower()}|{normalized_track['track'].lower()}"
                        
                        if track_key not in seen_tracks:
                            selected_tracks.append(normalized_track)
                            seen_tracks.add(track_key)
                except Exception as e:
                    logger.warning(f"Failed to get popular tracks: {str(e)}")
            
            # Create consolidated playlist
            consolidated_links = self.create_consolidated_playlist_links(
                selected_tracks, mood, languages
            )
            
            playlist_result = {
                "playlist_info": {
                    "mood": mood,
                    "genres": genres,
                    "languages": languages,
                    "duration_minutes": duration_minutes,
                    "energy_level": round(energy_level, 2),
                    "valence": round(valence, 2),
                    "total_tracks": len(selected_tracks)
                },
                "consolidated_playlist": {
                    "name": consolidated_links["playlist_name"],
                    "streaming_links": {
                        "spotify": consolidated_links["spotify_search"],
                        "apple_music": consolidated_links["apple_music_search"], 
                        "youtube": consolidated_links["youtube_search"],
                        "lastfm": consolidated_links["lastfm_search"]
                    },
                    "track_list": consolidated_links["track_list"],
                    "description": f"A {duration_minutes}-minute {mood} playlist in {', '.join(languages)} with {len(selected_tracks)} tracks"
                },
                "tracks": selected_tracks
            }
            
            return json.dumps(playlist_result, indent=2, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"Error generating playlist: {str(e)}")
            return json.dumps({"error": str(e)}, indent=2)
    
    async def get_supported_options(self) -> str:
        """Get supported genres and languages"""
        try:
            # Get popular tags from Last.fm with error handling
            lastfm_genres = []
            try:
                result = await self._make_request("tag.getTopTags", {})
                if "toptags" in result and "tag" in result["toptags"]:
                    tags = result["toptags"]["tag"]
                    if isinstance(tags, list):
                        lastfm_genres = [tag["name"] for tag in tags[:20] if isinstance(tag, dict) and "name" in tag]
                    elif isinstance(tags, dict):
                        lastfm_genres = [tags["name"]] if "name" in tags else []
            except Exception as e:
                logger.warning(f"Failed to get Last.fm genres: {str(e)}")
                lastfm_genres = ["pop", "rock", "electronic", "indie", "alternative"]
            
            options = {
                "supported_languages": [
                    "hindi", "english", "punjabi", "bengali", "tamil", 
                    "telugu", "marathi", "gujarati", "spanish", "french", 
                    "korean", "japanese"
                ],
                "popular_genres": lastfm_genres,
                "mood_categories": [
                    "happy", "sad", "angry", "excited", "calm", 
                    "romantic", "nostalgic", "energetic", "neutral"
                ],
                "duration_formats": [
                    "30 minutes", "1 hour", "45 minutes", "5 songs", "10 tracks"
                ],
                "example_queries": [
                    "I want a 40 minutes playlist of hindi songs that makes me feel 😎",
                    "Generate a sad english playlist for 1 hour",
                    "Create an energetic punjabi playlist with 10 songs",
                    "I need romantic bollywood music for 30 minutes"
                ]
            }
            
            return json.dumps(options, indent=2, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"Error getting supported options: {str(e)}")
            return json.dumps({"error": str(e)}, indent=2)
    
    async def close(self):
        """Close the aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    def __del__(self):
        """Cleanup when object is destroyed"""
        if self.session and not self.session.closed:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.session.close())
            except:
                pass