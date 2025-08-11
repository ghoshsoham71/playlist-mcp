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
        track_uris = [track.uri for track in all_tracks]
        for i in range(0, len(track_uris), 100):
            batch = track_uris[i:i + 100]
            self.client.playlist_add(playlist.id, batch)
        
        return playlist.external_urls['spotify']
    
    async def _get_user_tracks(self, count: int, analysis_result: Dict[str, Any]) -> List[Union[tk.model.Track, tk.model.FullTrack]]:
        """Get tracks from user's listening history."""
        all_tracks = []
        
        try:
            # Get top tracks and recent tracks
            top_tracks = self.client.current_user_top_tracks(limit=50, time_range='medium_term')
            all_tracks.extend(top_tracks.items)
            
            recent = self.client.playback_recently_played(limit=50)
            all_tracks.extend([item.track for item in recent.items])
        except Exception as e:
            print(f"Error getting user tracks: {e}")
            return []
        
        # Remove duplicates
        unique_tracks = {track.id: track for track in all_tracks}.values()
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
        sentiment_scores = analysis_result['sentiment']
        primary_sentiment = max(sentiment_scores.items(), key=lambda x: x[1])[0]
        features = self.sentiment_mapping.get(primary_sentiment, self.sentiment_mapping['neutral'])
        
        # Use user tracks as seeds
        seed_tracks = [track.id for track in user_tracks[:5]] if user_tracks else None
        
        try:
            recs = self.client.recommendations(
                seed_tracks=seed_tracks,
                limit=min(100, count * 2),
                target_valence=features['valence'],
                target_energy=features['energy'],
                target_danceability=features['danceability']
            )
            
            # Filter out duplicates from user tracks
            user_ids = {track.id for track in user_tracks}
            filtered = [track for track in recs.tracks if track.id not in user_ids]
            return filtered[:count]
            
        except Exception as e:
            print(f"Error getting recommendations: {e}")
            return await self._fallback_search(count, primary_sentiment)
    
    async def _filter_by_sentiment(self, tracks: List, analysis_result: Dict[str, Any]) -> List:
        """Filter tracks based on audio features matching sentiment."""
        track_ids = [track.id for track in tracks]
        
        try:
            # Get audio features in batches
            all_features = []
            for i in range(0, len(track_ids), 100):
                batch = track_ids[i:i + 100]
                features = self.client.tracks_audio_features(batch)
                all_features.extend(features)
            
            # Score tracks by sentiment match
            sentiment_scores = analysis_result['sentiment']
            primary_sentiment = max(sentiment_scores.items(), key=lambda x: x[1])[0]
            target = self.sentiment_mapping.get(primary_sentiment, self.sentiment_mapping['neutral'])
            
            scored_tracks = []
            for track, features in zip(tracks, all_features):
                if features:
                    score = self._sentiment_match_score(features, target)
                    scored_tracks.append((track, score))
            
            # Sort by score and return tracks
            scored_tracks.sort(key=lambda x: x[1], reverse=True)
            return [track for track, _ in scored_tracks]
            
        except Exception as e:
            print(f"Error filtering by sentiment: {e}")
            return tracks
    
    def _sentiment_match_score(self, features: tk.model.AudioFeatures, target: Dict[str, float]) -> float:
        """Calculate sentiment match score for a track."""
        scores = []
        for feature, target_val in target.items():
            track_val = getattr(features, feature, 0.5)
            scores.append(1.0 - abs(track_val - target_val))
        return sum(scores) / len(scores) if scores else 0.0
    
    async def _fallback_search(self, count: int, sentiment: str) -> List[tk.model.FullTrack]:
        """Fallback search when recommendations fail."""
        keywords = {
            "joy": ["happy", "upbeat", "positive"],
            "sadness": ["sad", "melancholy", "emotional"],
            "anger": ["rock", "intense", "aggressive"],
            "fear": ["dark", "ambient", "mysterious"],
            "surprise": ["experimental", "unique"],
            "neutral": ["popular", "trending"]
        }.get(sentiment, ["popular"])
        
        all_tracks = []
        for keyword in keywords:
            try:
                results = self.client.search(query=keyword, types=('track',), limit=25)
                if results[0]:  # tracks is first in tuple
                    all_tracks.extend(results[0].items)
            except Exception as e:
                print(f"Search error for {keyword}: {e}")
        
        # Remove duplicates and return random selection
        unique_tracks = {track.id: track for track in all_tracks}.values()
        tracks_list = list(unique_tracks)
        return random.sample(tracks_list, min(count, len(tracks_list)))