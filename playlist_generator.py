import random
from typing import Dict, List, Any, Optional, Union
import tekore as tk


class PlaylistGenerator:
    """Generates Spotify playlists using Tekore client - Updated for deprecated API endpoints."""
    
    def __init__(self, client: tk.Spotify):
        self.client = client
        
        # Sentiment to search keywords mapping (since audio features API is deprecated)
        self.sentiment_keywords = {
            "joy": ["happy", "upbeat", "energetic", "dance", "party", "fun", "positive", "cheerful", "bright"],
            "sadness": ["sad", "melancholy", "emotional", "ballad", "slow", "acoustic", "heartbreak", "blue"],
            "anger": ["rock", "metal", "intense", "aggressive", "punk", "hard", "heavy", "angry"],
            "fear": ["dark", "ambient", "electronic", "atmospheric", "mysterious", "haunting", "eerie"],
            "surprise": ["experimental", "jazz", "unique", "world", "fusion", "alternative", "indie", "eclectic"],
            "neutral": ["popular", "top", "hits", "trending", "mainstream", "classic", "best", "favorite"]
        }
        
        # Genre keywords for each sentiment
        self.sentiment_genres = {
            "joy": ["pop", "dance", "funk", "disco", "reggae", "latin"],
            "sadness": ["blues", "folk", "acoustic", "indie", "alternative", "country"],
            "anger": ["rock", "metal", "punk", "hardcore", "grunge", "industrial"],
            "fear": ["ambient", "electronic", "darkwave", "gothic", "post-rock", "experimental"],
            "surprise": ["jazz", "world", "fusion", "progressive", "avant-garde", "new age"],
            "neutral": ["pop", "rock", "indie", "alternative", "classic rock", "soul"]
        }
        
        # Language to market mapping for better recommendations
        self.language_markets = {
            'en': 'US', 'es': 'ES', 'fr': 'FR', 'de': 'DE', 'it': 'IT',
            'pt': 'BR', 'nl': 'NL', 'ja': 'JP', 'ko': 'KR', 'zh': 'CN',
            'ru': 'RU', 'hi': 'IN', 'ar': 'SA', 'sv': 'SE', 'no': 'NO',
            'da': 'DK', 'fi': 'FI', 'pl': 'PL', 'cs': 'CZ', 'hu': 'HU'
        }
    
    async def create_playlist(self, analysis_result: Dict[str, Any], duration_minutes: int, playlist_name: str) -> str:
        """Create a Spotify playlist based on analysis results."""
        user = self.client.current_user()
        target_tracks = max(15, int(duration_minutes / 3.5))  # Aim for ~3.5 min average per track
        
        # Get tracks: 40% from user history, 60% from search-based recommendations
        user_tracks_count = int(target_tracks * 0.4)
        search_tracks_count = target_tracks - user_tracks_count
        
        print(f"🎯 Target: {target_tracks} tracks ({user_tracks_count} from user, {search_tracks_count} from search)")
        
        user_tracks = await self._get_user_tracks(user_tracks_count, analysis_result)
        search_tracks = await self._get_search_based_tracks(search_tracks_count, analysis_result, user_tracks)
        
        # Combine and shuffle
        all_tracks = user_tracks + search_tracks
        random.shuffle(all_tracks)
        
        print(f"✅ Collected {len(all_tracks)} total tracks")
        
        # Create playlist
        description = f"AI-generated playlist based on: '{analysis_result['raw_prompt'][:80]}...'"
        playlist = self.client.playlist_create(
            user_id=user.id,
            name=playlist_name,
            description=description,
            public=False
        )
        
        # Add tracks in batches
        track_uris = [track.uri for track in all_tracks if track and hasattr(track, 'uri')]
        if track_uris:
            for i in range(0, len(track_uris), 100):
                batch = track_uris[i:i + 100]
                if batch:  # Only add if batch is not empty
                    self.client.playlist_add(playlist.id, batch)
        
        print(f"🎵 Created playlist with {len(track_uris)} tracks")
        return playlist.external_urls['spotify']
    
    async def _get_user_tracks(self, count: int, analysis_result: Dict[str, Any]) -> List[Union[tk.model.Track, tk.model.FullTrack]]:
        """Get tracks from user's listening history."""
        all_tracks = []
        
        try:
            # Get top tracks from different time ranges
            for time_range in ['short_term', 'medium_term', 'long_term']:
                try:
                    top_tracks = self.client.current_user_top_tracks(limit=20, time_range=time_range)
                    all_tracks.extend([track for track in top_tracks.items if track])
                except Exception as e:
                    print(f"Warning: Could not get {time_range} top tracks: {e}")
            
            # Get recent tracks
            try:
                recent = self.client.playback_recently_played(limit=30)
                all_tracks.extend([item.track for item in recent.items if item.track])
            except Exception as e:
                print(f"Warning: Could not get recent tracks: {e}")
                
        except Exception as e:
            print(f"Error getting user tracks: {e}")
            return []
        
        # Remove duplicates and None values
        unique_tracks = {track.id: track for track in all_tracks if track and hasattr(track, 'id')}.values()
        tracks_list = list(unique_tracks)
        
        print(f"📚 Found {len(tracks_list)} unique user tracks")
        
        # Return random selection
        return random.sample(tracks_list, min(count, len(tracks_list)))
    
    async def _get_search_based_tracks(
        self, count: int, analysis_result: Dict[str, Any], user_tracks: List
    ) -> List[tk.model.FullTrack]:
        """Get tracks through search (replacement for deprecated recommendations API)."""
        # Get primary sentiment
        sentiment_scores = analysis_result.get('sentiment', {})
        if not sentiment_scores:
            sentiment_scores = {'neutral': 1.0}
        
        primary_sentiment = max(sentiment_scores.items(), key=lambda x: x[1])[0]
        print(f"🎭 Primary sentiment: {primary_sentiment}")
        
        # Get market based on detected language
        language = analysis_result.get('language', 'en')
        market = self.language_markets.get(language, 'US')
        
        # Get search keywords and genres for this sentiment
        keywords = self.sentiment_keywords.get(primary_sentiment, self.sentiment_keywords['neutral'])
        genres = self.sentiment_genres.get(primary_sentiment, self.sentiment_genres['neutral'])
        
        all_found_tracks = []
        user_track_ids = {track.id for track in user_tracks if track and hasattr(track, 'id')}
        
        # Search with different strategies
        search_queries = []
        
        # Strategy 1: Genre-based searches
        for genre in genres[:3]:  # Limit to top 3 genres
            search_queries.append(f"genre:{genre}")
            
        # Strategy 2: Keyword-based searches
        for keyword in keywords[:4]:  # Limit to top 4 keywords
            search_queries.append(keyword)
            
        # Strategy 3: Combined searches
        search_queries.append(f"{keywords[0]} {genres[0]}")
        if len(keywords) > 1 and len(genres) > 1:
            search_queries.append(f"{keywords[1]} {genres[1]}")
        
        # Strategy 4: Year-based searches for variety
        current_year = 2025
        for year_offset in [0, -5, -10, -15]:  # Current, 2019, 2014, 2009
            year = current_year + year_offset
            search_queries.append(f"{keywords[0]} year:{year}")
        
        print(f"🔍 Using {len(search_queries)} search strategies")
        
        for query in search_queries:
            try:
                results = self.client.search(
                    query=query, 
                    types=('track',), 
                    limit=20,
                    market=market
                )
                
                if results and len(results) > 0 and results[0]:  # tracks is first in tuple
                    tracks_page = results[0]
                    if hasattr(tracks_page, 'items'):
                        # Filter out user tracks and None values
                        new_tracks = [
                            track for track in tracks_page.items 
                            if track and hasattr(track, 'id') and track.id not in user_track_ids
                        ]
                        all_found_tracks.extend(new_tracks)
                        
            except Exception as e:
                print(f"Search error for '{query}': {e}")
                continue
        
        # Remove duplicates
        if all_found_tracks:
            unique_tracks = {track.id: track for track in all_found_tracks if track and hasattr(track, 'id')}.values()
            tracks_list = list(unique_tracks)
            print(f"🔍 Found {len(tracks_list)} unique search results")
            
            # Return random selection
            return random.sample(tracks_list, min(count, len(tracks_list)))
        else:
            print("⚠️ No tracks found through search, using fallback")
            return await self._fallback_popular_search(count, market, user_track_ids)
    
    async def _fallback_popular_search(self, count: int, market: str, exclude_ids: set) -> List[tk.model.FullTrack]:
        """Fallback to popular/trending tracks when other searches fail."""
        fallback_queries = [
            "top hits", "trending", "popular", "best songs", "chart hits",
            "new releases", "viral", "most played", "radio hits", "favorites"
        ]
        
        all_tracks = []
        
        for query in fallback_queries:
            try:
                results = self.client.search(
                    query=query, 
                    types=('track',), 
                    limit=15,
                    market=market
                )
                
                if results and len(results) > 0 and results[0]:
                    tracks_page = results[0]
                    if hasattr(tracks_page, 'items'):
                        new_tracks = [
                            track for track in tracks_page.items 
                            if track and hasattr(track, 'id') and track.id not in exclude_ids
                        ]
                        all_tracks.extend(new_tracks)
                        
            except Exception as e:
                print(f"Fallback search error for '{query}': {e}")
        
        if all_tracks:
            unique_tracks = {track.id: track for track in all_tracks if track and hasattr(track, 'id')}.values()
            tracks_list = list(unique_tracks)
            print(f"🆘 Fallback found {len(tracks_list)} tracks")
            return random.sample(tracks_list, min(count, len(tracks_list)))
        else:
            print("❌ All search strategies failed")
            return []