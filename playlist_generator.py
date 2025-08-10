#!/usr/bin/env python3
"""
Playlist Generator for Mood-based Music
Generates playlists using Last.fm API based on mood and preferences
"""

import asyncio
import json
import logging
import random
import hashlib
import urllib.parse
from typing import List, Dict, Any
import aiohttp

logger = logging.getLogger(__name__)

class PlaylistGenerator:
    """Generate playlists based on mood and preferences using Last.fm API"""
    
    def __init__(self, lastfm_api_key: str, lastfm_shared_secret: str):
        self.api_key = lastfm_api_key
        self.shared_secret = lastfm_shared_secret
        self.base_url = "http://ws.audioscrobbler.com/2.0/"
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def close(self):
        """Close the HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None

    def _create_signature(self, params: Dict[str, str]) -> str:
        """Create API signature for Last.fm"""
        # Sort parameters and create signature string
        sorted_params = sorted(params.items())
        sig_string = ''.join([f"{k}{v}" for k, v in sorted_params])
        sig_string += self.shared_secret
        
        # Create MD5 hash
        return hashlib.md5(sig_string.encode('utf-8')).hexdigest()

    async def _make_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make authenticated request to Last.fm API"""
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        # Add common parameters
        params.update({
            'method': method,
            'api_key': self.api_key,
            'format': 'json'
        })
        
        try:
            async with self.session.get(self.base_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'error' in data:
                        logger.error(f"Last.fm API error: {data['message']}")
                        return {}
                    return data
                else:
                    logger.error(f"HTTP error {response.status}")
                    return {}
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return {}

    async def get_similar_artists(self, artist: str, limit: int = 20) -> List[str]:
        """Get similar artists from Last.fm"""
        params = {
            'artist': artist,
            'limit': limit
        }
        
        data = await self._make_request('artist.getsimilar', params)
        
        if 'similarartists' in data and 'artist' in data['similarartists']:
            artists = data['similarartists']['artist']
            if isinstance(artists, list):
                return [a['name'] for a in artists[:limit]]
            elif isinstance(artists, dict):
                return [artists['name']]
        
        return []

    async def get_top_tracks_by_tag(self, tag: str, limit: int = 50) -> List[Dict[str, str]]:
        """Get top tracks for a specific tag/genre"""
        params = {
            'tag': tag,
            'limit': limit
        }
        
        data = await self._make_request('tag.gettoptracks', params)
        
        tracks = []
        if 'tracks' in data and 'track' in data['tracks']:
            track_list = data['tracks']['track']
            if isinstance(track_list, list):
                for track in track_list:
                    if 'name' in track and 'artist' in track:
                        tracks.append({
                            'track': track['name'],
                            'artist': track['artist']['name'] if isinstance(track['artist'], dict) else str(track['artist'])
                        })
            elif isinstance(track_list, dict) and 'name' in track_list and 'artist' in track_list:
                tracks.append({
                    'track': track_list['name'],
                    'artist': track_list['artist']['name'] if isinstance(track_list['artist'], dict) else str(track_list['artist'])
                })
        
        return tracks

    async def get_artist_top_tracks(self, artist: str, limit: int = 10) -> List[Dict[str, str]]:
        """Get top tracks for a specific artist"""
        params = {
            'artist': artist,
            'limit': limit
        }
        
        data = await self._make_request('artist.gettoptracks', params)
        
        tracks = []
        if 'toptracks' in data and 'track' in data['toptracks']:
            track_list = data['toptracks']['track']
            if isinstance(track_list, list):
                for track in track_list:
                    if 'name' in track and 'artist' in track:
                        tracks.append({
                            'track': track['name'],
                            'artist': track['artist']['name'] if isinstance(track['artist'], dict) else str(track['artist'])
                        })
            elif isinstance(track_list, dict) and 'name' in track_list and 'artist' in track_list:
                tracks.append({
                    'track': track_list['name'],
                    'artist': track_list['artist']['name'] if isinstance(track_list['artist'], dict) else str(track_list['artist'])
                })
        
        return tracks

    async def search_tracks(self, query: str, limit: int = 20) -> List[Dict[str, str]]:
        """Search for tracks"""
        params = {
            'track': query,
            'limit': limit
        }
        
        data = await self._make_request('track.search', params)
        
        tracks = []
        if 'results' in data and 'trackmatches' in data['results'] and 'track' in data['results']['trackmatches']:
            track_list = data['results']['trackmatches']['track']
            if isinstance(track_list, list):
                for track in track_list:
                    if 'name' in track and 'artist' in track:
                        tracks.append({
                            'track': track['name'],
                            'artist': str(track['artist'])
                        })
            elif isinstance(track_list, dict) and 'name' in track_list and 'artist' in track_list:
                tracks.append({
                    'track': track_list['name'],
                    'artist': str(track_list['artist'])
                })
        
        return tracks

    def estimate_track_count(self, duration_minutes: int) -> int:
        """Estimate number of tracks needed for duration"""
        # Average song length is about 3.5 minutes
        avg_song_length = 3.5
        return max(1, int(duration_minutes / avg_song_length))

    async def generate_playlist_data(self, mood: str, genres: List[str], languages: List[str], 
                                   duration_minutes: int, energy_level: float, valence: float) -> Dict[str, Any]:
        """Generate playlist data structure"""
        target_tracks = self.estimate_track_count(duration_minutes)
        all_tracks = []
        
        # Create search terms combining mood, genres, and languages
        search_terms = []
        
        # Add genre-based searches
        for genre in genres:
            search_terms.append(genre)
            
        # Add language-specific genres
        for language in languages:
            if language.lower() == 'hindi':
                search_terms.extend(['bollywood', 'hindi pop', 'indian classical'])
            elif language.lower() == 'punjabi':
                search_terms.extend(['punjabi pop', 'bhangra'])
            elif language.lower() == 'english':
                search_terms.extend(['pop', 'rock', 'indie'])
                
        # Add mood-based searches
        mood_terms = {
            'happy': ['upbeat', 'cheerful', 'positive'],
            'sad': ['melancholy', 'emotional', 'ballad'],
            'energetic': ['dance', 'electronic', 'workout'],
            'calm': ['ambient', 'chill', 'relaxing'],
            'romantic': ['love songs', 'romantic', 'slow'],
            'angry': ['metal', 'punk', 'aggressive'],
            'nostalgic': ['classic', 'oldies', 'throwback']
        }
        
        if mood.lower() in mood_terms:
            search_terms.extend(mood_terms[mood.lower()])
            
        # Remove duplicates
        search_terms = list(set(search_terms))
        
        logger.info(f"Searching with terms: {search_terms}")
        
        # Collect tracks from different sources
        for term in search_terms[:5]:  # Limit to prevent too many API calls
            try:
                # Get tracks by tag
                tag_tracks = await self.get_top_tracks_by_tag(term, limit=20)
                all_tracks.extend(tag_tracks)
                
                # Add some delay to respect API limits
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.warning(f"Error searching for term '{term}': {e}")
                continue
        
        # Remove duplicates based on artist + track combination
        unique_tracks = []
        seen = set()
        for track in all_tracks:
            identifier = f"{track['artist'].lower()}_{track['track'].lower()}"
            if identifier not in seen:
                seen.add(identifier)
                unique_tracks.append(track)
        
        # Shuffle and select desired number of tracks
        random.shuffle(unique_tracks)
        selected_tracks = unique_tracks[:target_tracks]
        
        # If we don't have enough tracks, add some fallback tracks
        if len(selected_tracks) < target_tracks:
            logger.warning(f"Only found {len(selected_tracks)} tracks, needed {target_tracks}")
            
            # Add some popular tracks as fallback
            try:
                fallback_tracks = await self.get_top_tracks_by_tag('popular', limit=target_tracks - len(selected_tracks))
                selected_tracks.extend(fallback_tracks)
            except Exception as e:
                logger.warning(f"Error getting fallback tracks: {e}")
        
        return {
            'tracks': selected_tracks[:target_tracks],
            'metadata': {
                'mood': mood,
                'genres': genres,
                'languages': languages,
                'duration_minutes': duration_minutes,
                'energy_level': energy_level,
                'valence': valence,
                'total_tracks': len(selected_tracks[:target_tracks])
            }
        }

    async def generate_playlist(self, mood: str, genres: List[str], languages: List[str], 
                              duration_minutes: int, energy_level: float, valence: float) -> str:
        """Generate a formatted playlist string"""
        playlist_data = await self.generate_playlist_data(
            mood, genres, languages, duration_minutes, energy_level, valence
        )
        
        # Create formatted output
        lang_str = " & ".join(lang.title() for lang in languages)
        output = {
            "playlist": {
                "title": f"{mood.title()} {lang_str} Playlist",
                "duration_minutes": duration_minutes,
                "total_tracks": len(playlist_data['tracks']),
                "mood_analysis": {
                    "detected_mood": mood.title(),
                    "energy_level": f"{energy_level:.1f}/1.0",
                    "languages": languages,
                    "genres": genres
                },
                "tracks": playlist_data['tracks'],
                "streaming_links": {
                    "spotify_search": f"https://open.spotify.com/search/{urllib.parse.quote(f'{mood} {lang_str} music')}",
                    "apple_music_search": f"https://music.apple.com/search?term={urllib.parse.quote(f'{mood} {lang_str} music')}",
                    "youtube_search": f"https://www.youtube.com/results?search_query={urllib.parse.quote(f'{mood} {lang_str} music playlist')}"
                }
            }
        }
        
        return json.dumps(output, indent=2, ensure_ascii=False)

    def __del__(self):
        """Cleanup when object is destroyed"""
        if self.session and not self.session.closed:
            # Note: This is not ideal for async cleanup, but serves as a fallback
            try:
                asyncio.get_event_loop().create_task(self.close())
            except RuntimeError:
                pass  # Event loop might be closed already