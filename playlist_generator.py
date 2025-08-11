import random
from typing import Dict, List, Any, Optional, Union
import tekore as tk


class PlaylistGenerator:
    """Generates Spotify playlists using Tekore client based on sentiment analysis."""
    
    def __init__(self, client: tk.Spotify):
        self.client = client
        
        # Sentiment to audio features mapping
        self.sentiment_mapping = {
            "joy": {"valence": 0.8, "energy": 0.7, "danceability": 0.8},
            "sadness": {"valence": 0.2, "energy": 0.3, "danceability": 0.4},
            "anger": {"valence": 0.3, "energy": 0.9, "danceability": 0.6},
            "fear": {"valence": 0.2, "energy": 0.4, "danceability": 0.3},
            "surprise": {"valence": 0.6, "energy": 0.6, "danceability": 0.7},
            "neutral": {"valence": 0.5, "energy": 0.5, "danceability": 0.5}
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
        target_tracks = max(10, int(duration_minutes / 3.5))
        
        # Get tracks: 30% from user history, 70% from recommendations
        user_tracks_count = int(target_tracks * 0.3)
        rec_tracks_count = target_tracks - user_tracks_count
        
        user_tracks = await self._get_user_tracks(user_tracks_count, analysis_result)
        rec_tracks = await self._get_recommended_tracks(rec_tracks_count, analysis_result, user_tracks)
        
        # Combine and shuffle
        all_tracks = user_tracks + rec_tracks
        random.shuffle(all_tracks)
        
        # Create playlist
        description = f"AI-generated playlist based on: {analysis_result['raw_prompt'][:100]}..."
        playlist = self.client.playlist_create(
            user_id=user.id,
            name=playlist_name,
            description=description,
            public=False
        )
        
        # Add tracks in batches
        track_uris = [track.uri for track in all_tracks if track and hasattr(track, 'uri')]
        for i in range(0, len(track_uris), 100):
            batch = track_uris[i:i + 100]
            if batch:  # Only add if batch is not empty
                self.client.playlist_add(playlist.id, batch)
        
        return playlist.external_urls['spotify']
    
    async def _get_user_tracks(self, count: int, analysis_result: Dict[str, Any]) -> List[Union[tk.model.Track, tk.model.FullTrack]]:
        """Get tracks from user's listening history."""
        all_tracks = []
        
        try:
            # Get top tracks and recent tracks
            top_tracks = self.client.current_user_top_tracks(limit=50, time_range='medium_term')
            all_tracks.extend([track for track in top_tracks.items if track])
            
            recent = self.client.playback_recently_played(limit=50)
            all_tracks.extend([item.track for item in recent.items if item.track])
        except Exception as e:
            print(f"Error getting user tracks: {e}")
            return []
        
        # Remove duplicates and None values
        unique_tracks = {track.id: track for track in all_tracks if track and hasattr(track, 'id')}.values()
        tracks_list = list(unique_tracks)
        
        # Filter by sentiment if enough tracks
        if len(tracks_list) > count * 2:
            tracks_list = await self._filter_by_sentiment(tracks_list, analysis_result)
        
        return random.sample(tracks_list, min(count, len(tracks_list)))
    
    async def _get_recommended_tracks(
        self, count: int, analysis_result: Dict[str, Any], user_tracks: List
    ) -> List[tk.model.FullTrack]:
        """Get recommended tracks based on sentiment."""
        # Get primary sentiment
        sentiment_scores = analysis_result.get('sentiment', {})
        if not sentiment_scores:
            sentiment_scores = {'neutral': 1.0}
        
        primary_sentiment = max(sentiment_scores.items(), key=lambda x: x[1])[0]
        features = self.sentiment_mapping.get(primary_sentiment, self.sentiment_mapping['neutral'])
        
        # Prepare seed tracks (limit to 5 as per Spotify API)
        seed_track_ids = None
        if user_tracks:
            seed_track_ids = [track.id for track in user_tracks[:5] if track and hasattr(track, 'id')]
        
        # Get market based on detected language
        language = analysis_result.get('language', 'en')
        market = self.language_markets.get(language, 'US')
        
        try:
            # Use correct parameter name for seed tracks
            rec_params = {
                'limit': min(100, count * 2),
                'market': market,
                'target_valence': features['valence'],
                'target_energy': features['energy'],
                'target_danceability': features['danceability']
            }
            
            # Use correct parameter name for tekore - track_ids instead of seed_tracks
            if seed_track_ids:
                rec_params['track_ids'] = seed_track_ids
            else:
                # Use seed genres as fallback
                rec_params['genres'] = self._get_genre_seeds(primary_sentiment)
            
            recs = self.client.recommendations(**rec_params)
            
            # Filter out duplicates from user tracks and None values
            user_ids = {track.id for track in user_tracks if track and hasattr(track, 'id')}
            filtered = [track for track in recs.tracks if track and track.id not in user_ids]
            return filtered[:count]
            
        except Exception as e:
            print(f"Error getting recommendations: {e}")
            return await self._fallback_search(count, primary_sentiment, language)
    
    def _get_genre_seeds(self, sentiment: str) -> List[str]:
        """Get genre seeds based on sentiment."""
        genre_mapping = {
            "joy": ["pop", "dance", "funk"],
            "sadness": ["blues", "folk", "indie"],
            "anger": ["rock", "metal", "punk"],
            "fear": ["ambient", "electronic", "classical"],
            "surprise": ["jazz", "world-music", "experimental"],
            "neutral": ["pop", "rock", "indie"]
        }
        return genre_mapping.get(sentiment, ["pop", "rock", "indie"])[:5]  # Limit to 5 genres
    
    async def _filter_by_sentiment(self, tracks: List, analysis_result: Dict[str, Any]) -> List:
        """Filter tracks based on audio features matching sentiment."""
        if not tracks:
            return tracks
        
        track_ids = [track.id for track in tracks if track and hasattr(track, 'id')]
        if not track_ids:
            return tracks
        
        try:
            # Get audio features in smaller batches to avoid URL length issues
            all_features = []
            batch_size = 50  # Reduced batch size to avoid URL length issues
            
            for i in range(0, len(track_ids), batch_size):
                batch_ids = track_ids[i:i + batch_size]
                try:
                    # Make individual requests for each track ID to avoid URL length issues
                    batch_features = []
                    for track_id in batch_ids:
                        try:
                            features = self.client.tracks_audio_features([track_id])
                            batch_features.extend(features if features else [None])
                        except Exception as single_error:
                            print(f"Error getting audio features for track {track_id}: {single_error}")
                            batch_features.append(None)
                    
                    all_features.extend(batch_features)
                except Exception as batch_error:
                    print(f"Error getting audio features for batch {i//batch_size + 1}: {batch_error}")
                    # Skip this batch and continue with others
                    all_features.extend([None] * len(batch_ids))
            
            # Score tracks by sentiment match
            sentiment_scores = analysis_result.get('sentiment', {})
            if not sentiment_scores:
                return tracks
            
            primary_sentiment = max(sentiment_scores.items(), key=lambda x: x[1])[0]
            target = self.sentiment_mapping.get(primary_sentiment, self.sentiment_mapping['neutral'])
            
            scored_tracks = []
            for track, features in zip(tracks, all_features):
                if track and features:
                    score = self._sentiment_match_score(features, target)
                    scored_tracks.append((track, score))
                elif track:
                    # Include track with neutral score if no features available
                    scored_tracks.append((track, 0.5))
            
            # Sort by score and return tracks
            scored_tracks.sort(key=lambda x: x[1], reverse=True)
            return [track for track, _ in scored_tracks]
            
        except Exception as e:
            print(f"Error filtering by sentiment: {e}")
            return tracks
    
    def _sentiment_match_score(self, features: tk.model.AudioFeatures, target: Dict[str, float]) -> float:
        """Calculate sentiment match score for a track."""
        if not features:
            return 0.5
        
        scores = []
        for feature, target_val in target.items():
            track_val = getattr(features, feature, 0.5)
            if track_val is not None:
                scores.append(1.0 - abs(track_val - target_val))
        return sum(scores) / len(scores) if scores else 0.5
    
    async def _fallback_search(self, count: int, sentiment: str, language: str = 'en') -> List[tk.model.FullTrack]:
        """Fallback search when recommendations fail."""
        keywords_by_sentiment = {
            "joy": ["happy", "upbeat", "positive", "dance", "party"],
            "sadness": ["sad", "melancholy", "emotional", "ballad", "slow"],
            "anger": ["rock", "intense", "aggressive", "metal", "punk"],
            "fear": ["dark", "ambient", "mysterious", "atmospheric", "electronic"],
            "surprise": ["experimental", "unique", "jazz", "world", "fusion"],
            "neutral": ["popular", "trending", "top", "hits", "mainstream"]
        }
        
        keywords = keywords_by_sentiment.get(sentiment, ["popular", "trending"])
        market = self.language_markets.get(language, 'US')
        
        all_tracks = []
        for keyword in keywords:
            try:
                results = self.client.search(
                    query=keyword, 
                    types=('track',), 
                    limit=20,
                    market=market
                )
                if results and len(results) > 0 and results[0]:  # tracks is first in tuple
                    tracks_page = results[0]
                    if hasattr(tracks_page, 'items'):
                        all_tracks.extend([track for track in tracks_page.items if track])
            except Exception as e:
                print(f"Search error for {keyword}: {e}")
        
        # Remove duplicates and return random selection
        if all_tracks:
            unique_tracks = {track.id: track for track in all_tracks if track and hasattr(track, 'id')}.values()
            tracks_list = list(unique_tracks)
            return random.sample(tracks_list, min(count, len(tracks_list)))
        else:
            return []
    
    def _filter_by_language(self, tracks: List, target_language: str) -> List:
        """Filter tracks by language/market preference."""
        # This is a simplified approach - in practice, you might want to use
        # track metadata or artist information for better language filtering
        if not tracks or target_language == 'en':
            return tracks
        
        # For now, return all tracks since determining track language
        # requires additional API calls or external services
        # In a production system, you might:
        # 1. Use artist country information
        # 2. Use lyrics analysis services
        # 3. Use track popularity in specific markets
        
        return tracks