#!/usr/bin/env python3
"""
Fixed Playlist Generator for Mood-based Music
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
        sorted_params = sorted(params.items())
        sig_string = ''.join([f"{k}{v}" for k, v in sorted_params])
        sig_string += self.shared_secret
        return hashlib.md5(sig_string.encode('utf-8')).hexdigest()

    async def _make_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make authenticated request to Last.fm API"""
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        params.update({
            'method': method,
            'api_key': self.api_key,
            'format': 'json'
        })
        
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with self.session.get(self.base_url, params=params, timeout=timeout) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'error' in data:
                        logger.error(f"Last.fm API error: {data.get('message', 'Unknown error')}")
                        return {}
                    return data
                else:
                    logger.error(f"HTTP error {response.status}")
                    return {}
        except asyncio.TimeoutError:
            logger.error(f"Request timeout for method: {method}")
            return {}
        except Exception as e:
            logger.error(f"Request failed for {method}: {e}")
            return {}

    def _extract_tracks_from_response(self, data: Dict, response_key: str) -> List[Dict[str, str]]:
        """Extract tracks from various API response formats"""
        tracks = []
        
        if response_key not in data:
            return tracks
            
        track_container = data[response_key]
        track_list = track_container.get('track', [])
        
        # Handle both list and single dict responses
        if isinstance(track_list, dict):
            track_list = [track_list]
        elif not isinstance(track_list, list):
            return tracks
            
        for track in track_list:
            if not isinstance(track, dict):
                continue
                
            track_name = track.get('name', '').strip()
            artist_info = track.get('artist', {})
            
            # Handle different artist field formats
            if isinstance(artist_info, dict):
                artist_name = artist_info.get('name', '').strip()
            else:
                artist_name = str(artist_info).strip()
            
            if track_name and artist_name:
                tracks.append({
                    'track': track_name,
                    'artist': artist_name
                })
                
        return tracks

    async def get_top_tracks_by_tag(self, tag: str, limit: int = 50) -> List[Dict[str, str]]:
        """Get top tracks for a specific tag/genre"""
        params = {'tag': tag, 'limit': limit}
        data = await self._make_request('tag.gettoptracks', params)
        
        tracks = self._extract_tracks_from_response(data, 'tracks')
        logger.info(f"Found {len(tracks)} tracks for tag '{tag}'")
        return tracks

    async def get_artist_top_tracks(self, artist: str, limit: int = 10) -> List[Dict[str, str]]:
        """Get top tracks for a specific artist"""
        params = {'artist': artist, 'limit': limit}
        data = await self._make_request('artist.gettoptracks', params)
        
        tracks = self._extract_tracks_from_response(data, 'toptracks')
        logger.info(f"Found {len(tracks)} tracks for artist '{artist}'")
        return tracks

    async def search_tracks(self, query: str, limit: int = 20) -> List[Dict[str, str]]:
        """Search for tracks"""
        params = {'track': query, 'limit': limit}
        data = await self._make_request('track.search', params)
        
        tracks = []
        if 'results' in data and 'trackmatches' in data['results']:
            tracks = self._extract_tracks_from_response(data['results'], 'trackmatches')
        
        logger.info(f"Found {len(tracks)} tracks for search '{query}'")
        return tracks

    async def search_artists_by_tag(self, tag: str, limit: int = 20) -> List[str]:
        """Get artists by tag"""
        params = {'tag': tag, 'limit': limit}
        data = await self._make_request('tag.gettopartists', params)
        
        artists = []
        if 'topartists' in data and 'artist' in data['topartists']:
            artist_list = data['topartists']['artist']
            if isinstance(artist_list, dict):
                artist_list = [artist_list]
            elif not isinstance(artist_list, list):
                return artists
                
            for artist in artist_list:
                if isinstance(artist, dict) and 'name' in artist:
                    artists.append(artist['name'])
                    
        logger.info(f"Found {len(artists)} artists for tag '{tag}'")
        return artists

    def _is_language_relevant(self, artist: str, track: str, languages: List[str]) -> bool:
        """Check if track is relevant to requested languages"""
        artist_lower = artist.lower()
        track_lower = track.lower()
        
        # Language-specific indicators
        language_indicators = {
            'hindi': ['bollywood', 'hindi', 'indian', 'mumbai', 'desi', 'kumar', 'sharma', 'singh', 'khan'],
            'punjabi': ['punjabi', 'bhangra', 'patiala', 'lahore'],
            'english': [],  # English is default, no specific indicators needed
            'tamil': ['tamil', 'chennai', 'kollywood'],
            'bengali': ['bengali', 'kolkata', 'bangla']
        }
        
        for lang in languages:
            lang_lower = lang.lower()
            if lang_lower == 'english':
                continue  # Accept all for English unless specifically non-English indicators
            
            indicators = language_indicators.get(lang_lower, [])
            if any(indicator in artist_lower or indicator in track_lower for indicator in indicators):
                return True
                
        # If no specific language match found and English is requested, allow it
        return 'english' in [l.lower() for l in languages]

    def estimate_track_count(self, duration_minutes: int) -> int:
        """Estimate number of tracks needed for duration"""
        avg_song_length = 3.5
        return max(5, min(20, int(duration_minutes / avg_song_length)))

    async def generate_playlist_data(self, mood: str, genres: List[str], languages: List[str], 
                                   duration_minutes: int, energy_level: float, valence: float) -> Dict[str, Any]:
        """Generate playlist data structure"""
        target_tracks = self.estimate_track_count(duration_minutes)
        all_tracks = []
        
        logger.info(f"Generating playlist: mood={mood}, languages={languages}, duration={duration_minutes}min, target_tracks={target_tracks}")
        
        # Create comprehensive search strategy
        search_strategies = []
        
        # Strategy 1: Language-specific searches
        for language in languages:
            if language.lower() == 'hindi':
                search_strategies.extend([
                    ('tag', 'bollywood'),
                    ('tag', 'hindi'),
                    ('tag', 'indian'),
                    ('search', f'bollywood {mood}'),
                    ('search', f'hindi {mood}')
                ])
            elif language.lower() == 'punjabi':
                search_strategies.extend([
                    ('tag', 'punjabi'),
                    ('tag', 'bhangra'),
                    ('search', f'punjabi {mood}')
                ])
            elif language.lower() == 'english':
                search_strategies.extend([
                    ('search', f'{mood} songs'),
                    ('search', f'{mood} music')
                ])
        
        # Strategy 2: Mood + Genre combinations
        for genre in genres:
            search_strategies.extend([
                ('tag', genre),
                ('search', f'{genre} {mood}')
            ])
        
        # Strategy 3: Get artists first, then their tracks
        artist_search_strategies = []
        for language in languages:
            if language.lower() == 'hindi':
                artist_search_strategies.extend(['bollywood', 'hindi', 'indian'])
            elif language.lower() == 'punjabi':
                artist_search_strategies.extend(['punjabi', 'bhangra'])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_strategies = []
        for strategy in search_strategies:
            if strategy not in seen:
                seen.add(strategy)
                unique_strategies.append(strategy)
        
        search_strategies = unique_strategies[:10]  # Limit to prevent too many API calls
        
        logger.info(f"Using {len(search_strategies)} search strategies")
        
        # Execute search strategies
        for strategy_type, query in search_strategies:
            try:
                if strategy_type == 'tag':
                    tracks = await self.get_top_tracks_by_tag(query, limit=30)
                elif strategy_type == 'search':
                    tracks = await self.search_tracks(query, limit=20)
                else:
                    continue
                
                # Filter tracks by language relevance
                relevant_tracks = []
                for track in tracks:
                    if self._is_language_relevant(track['artist'], track['track'], languages):
                        relevant_tracks.append(track)
                
                all_tracks.extend(relevant_tracks)
                logger.info(f"Strategy '{query}' yielded {len(relevant_tracks)} relevant tracks")
                
                # Rate limiting
                await asyncio.sleep(0.2)
                
            except Exception as e:
                logger.warning(f"Error with strategy '{query}': {e}")
                continue
        
        # Strategy 4: Get tracks from relevant artists
        for tag in artist_search_strategies[:3]:
            try:
                artists = await self.search_artists_by_tag(tag, limit=10)
                for artist in artists[:5]:  # Limit to prevent too many calls
                    try:
                        artist_tracks = await self.get_artist_top_tracks(artist, limit=5)
                        relevant_tracks = []
                        for track in artist_tracks:
                            if self._is_language_relevant(track['artist'], track['track'], languages):
                                relevant_tracks.append(track)
                        all_tracks.extend(relevant_tracks)
                        await asyncio.sleep(0.1)
                    except Exception as e:
                        logger.warning(f"Error getting tracks for artist '{artist}': {e}")
                        continue
            except Exception as e:
                logger.warning(f"Error getting artists for tag '{tag}': {e}")
                continue
        
        # Remove duplicates based on artist + track combination
        unique_tracks = []
        seen_combinations = set()
        
        for track in all_tracks:
            # Create a normalized identifier
            identifier = f"{track['artist'].lower().strip()}_{track['track'].lower().strip()}"
            if identifier not in seen_combinations and len(identifier) > 2:
                seen_combinations.add(identifier)
                unique_tracks.append(track)
        
        logger.info(f"Total unique tracks found: {len(unique_tracks)}")
        
        # Shuffle and select desired number of tracks
        random.shuffle(unique_tracks)
        selected_tracks = unique_tracks[:target_tracks]
        
        # If we still don't have enough tracks, log the issue but don't add generic fallbacks
        if len(selected_tracks) < target_tracks:
            logger.warning(f"Could only find {len(selected_tracks)} relevant tracks out of {target_tracks} requested")
            logger.warning(f"Search terms used: {[s[1] for s in search_strategies]}")
        
        logger.info(f"Returning {len(selected_tracks)} selected tracks")
        
        # Log a sample of tracks for debugging
        if selected_tracks:
            logger.info(f"Sample tracks: {selected_tracks[:2]}")
        
        return {
            'tracks': selected_tracks,
            'metadata': {
                'mood': mood,
                'genres': genres,
                'languages': languages,
                'duration_minutes': duration_minutes,
                'energy_level': energy_level,
                'valence': valence,
                'total_tracks': len(selected_tracks),
                'search_strategies_used': len(search_strategies)
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
            try:
                asyncio.get_event_loop().create_task(self.close())
            except RuntimeError:
                pass