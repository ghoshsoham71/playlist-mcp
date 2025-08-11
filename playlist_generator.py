import random
from typing import Dict, List, Any, Tuple, Optional, Union
import tekore as tk


class PlaylistGenerator:
    """Generates Spotify playlists based on sentiment analysis and user preferences."""
    
    def __init__(self, spotify_client: tk.Spotify):
        self.spotify = spotify_client
        
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
        """
        Create a consolidated Spotify playlist based on analysis.
        
        Args:
            analysis_result: Sentiment and language analysis results
            duration_minutes: Target duration in minutes
            playlist_name: Name for the playlist
            
        Returns:
            str: Spotify playlist URL
        """
        # Get user profile
        user_profile = self.spotify.current_user()
        user_id = user_profile.id
        
        # Calculate target number of tracks (assuming ~3.5 minutes per track)
        target_tracks = max(10, int(duration_minutes / 3.5))
        
        # Split: 30% from user history, 70% from recommendations
        user_tracks_count = int(target_tracks * 0.3)
        recommendation_tracks_count = target_tracks - user_tracks_count
        
        # Get user's listening history
        user_tracks = await self._get_user_tracks(user_tracks_count, analysis_result)
        
        # Get recommendations based on sentiment
        recommended_tracks = await self._get_recommended_tracks(
            recommendation_tracks_count, 
            analysis_result,
            user_tracks
        )
        
        # Combine and shuffle tracks
        all_tracks = user_tracks + recommended_tracks
        random.shuffle(all_tracks)
        
        # Create playlist
        playlist_description = f"AI-generated playlist based on: {analysis_result['raw_prompt'][:100]}..."
        playlist = self.spotify.playlist_create(
            user_id=user_id,
            name=playlist_name,
            description=playlist_description,
            public=False
        )
        
        # Add tracks to playlist in batches (Spotify API limit is 100 tracks per request)
        track_uris = [track.uri for track in all_tracks]
        batch_size = 100
        
        for i in range(0, len(track_uris), batch_size):
            batch = track_uris[i:i + batch_size]
            self.spotify.playlist_add(playlist.id, batch)
        
        return playlist.external_urls['spotify']
    
    async def _get_user_tracks(self, count: int, analysis_result: Dict[str, Any]) -> List[Union[tk.model.Track, tk.model.FullTrack]]:
        """Get tracks from user's listening history that match the sentiment."""
        try:
            all_user_tracks = []
            
            # Get user's top tracks
            try:
                top_tracks = self.spotify.current_user_top_tracks(limit=50, time_range='medium_term')
                all_user_tracks.extend(top_tracks.items)
            except Exception as e:
                print(f"Error getting top tracks: {e}")
            
            # Get user's recently played tracks
            try:
                recent_tracks = self.spotify.playback_recently_played(limit=50)
                all_user_tracks.extend([item.track for item in recent_tracks.items])
            except Exception as e:
                print(f"Error getting recent tracks: {e}")
            
            # Remove duplicates by track ID
            unique_tracks = {}
            for track in all_user_tracks:
                if track.id not in unique_tracks:
                    unique_tracks[track.id] = track
            
            all_user_tracks = list(unique_tracks.values())
            
            # Filter tracks based on sentiment if we have enough data
            if len(all_user_tracks) > count * 2:
                filtered_tracks = await self._filter_tracks_by_sentiment(all_user_tracks, analysis_result)
            else:
                filtered_tracks = all_user_tracks
            
            # Return random selection
            return random.sample(filtered_tracks, min(count, len(filtered_tracks)))
            
        except Exception as e:
            print(f"Error getting user tracks: {e}")
            return []
    
    async def _get_recommended_tracks(self, count: int, analysis_result: Dict[str, Any], user_tracks: List[Union[tk.model.Track, tk.model.FullTrack]]) -> List[tk.model.FullTrack]:
        """Get recommended tracks based on sentiment analysis."""
        # Determine primary sentiment
        sentiment_scores = analysis_result['sentiment']
        primary_sentiment = max(sentiment_scores.items(), key=lambda x: x[1])[0]
        
        # Get audio features for sentiment
        target_features = self.sentiment_mapping.get(primary_sentiment, self.sentiment_mapping['neutral'])
        
        # Use user tracks as seeds if available
        seed_tracks = [track.id for track in user_tracks[:5]] if user_tracks else None
        
        # Get recommendations
        try:
            recommendations = self.spotify.recommendations(
                seed_tracks=seed_tracks,
                limit=min(100, count * 2),  # Get more than needed for filtering
                target_valence=target_features['valence'],
                target_energy=target_features['energy'],
                target_danceability=target_features['danceability']
            )
            
            # Filter out duplicates from user tracks
            user_track_ids = {track.id for track in user_tracks}
            filtered_recs = [
                track for track in recommendations.tracks 
                if track.id not in user_track_ids
            ]
            
            return filtered_recs[:count]
            
        except Exception as e:
            print(f"Error getting recommendations: {e}")
            # Fallback: search for tracks based on sentiment keywords
            return await self._fallback_search(count, primary_sentiment)
    
    async def _filter_tracks_by_sentiment(self, tracks: List[Union[tk.model.Track, tk.model.FullTrack]], analysis_result: Dict[str, Any]) -> List[Union[tk.model.Track, tk.model.FullTrack]]:
        """Filter tracks based on their audio features matching the sentiment."""
        # Get audio features for all tracks
        track_ids = [track.id for track in tracks]
        
        try:
            # Split into batches of 100 (API limit)
            batch_size = 100
            all_audio_features = []
            
            for i in range(0, len(track_ids), batch_size):
                batch_ids = track_ids[i:i + batch_size]
                audio_features_batch = self.spotify.tracks_audio_features(batch_ids)
                all_audio_features.extend(audio_features_batch)
            
            # Determine target sentiment
            sentiment_scores = analysis_result['sentiment']
            primary_sentiment = max(sentiment_scores.items(), key=lambda x: x[1])[0]
            target_features = self.sentiment_mapping.get(primary_sentiment, self.sentiment_mapping['neutral'])
            
            # Score tracks based on how well they match target sentiment
            scored_tracks = []
            for track, features in zip(tracks, all_audio_features):
                if features:  # features can be None for some tracks
                    score = self._calculate_sentiment_match_score(features, target_features)
                    scored_tracks.append((track, score))
            
            # Sort by score and return top matches
            scored_tracks.sort(key=lambda x: x[1], reverse=True)
            return [track for track, _ in scored_tracks]
            
        except Exception as e:
            print(f"Error filtering tracks by sentiment: {e}")
            return tracks
    
    def _calculate_sentiment_match_score(self, track_features: tk.model.AudioFeatures, target_features: Dict[str, float]) -> float:
        """Calculate how well a track's features match target sentiment features."""
        score = 0.0
        feature_count = 0
        
        for feature, target_value in target_features.items():
            track_value = getattr(track_features, feature, None)
            if track_value is not None:
                # Calculate proximity to target (closer = higher score)
                diff = abs(track_value - target_value)
                score += 1.0 - diff
                feature_count += 1
        
        return score / feature_count if feature_count > 0 else 0.0
    
    async def _fallback_search(self, count: int, sentiment: str) -> List[tk.model.FullTrack]:
        """Fallback method to search for tracks when recommendations fail."""
        sentiment_keywords = {
            "joy": ["happy", "upbeat", "celebration", "positive"],
            "sadness": ["sad", "melancholy", "slow", "emotional"],
            "anger": ["rock", "metal", "intense", "aggressive"],
            "fear": ["dark", "mysterious", "ambient", "haunting"],
            "surprise": ["experimental", "unique", "unexpected"],
            "neutral": ["popular", "trending", "mainstream"]
        }
        
        keywords = sentiment_keywords.get(sentiment, sentiment_keywords['neutral'])
        all_tracks = []
        
        for keyword in keywords:
            try:
                search_results = self.spotify.search(
                    query=keyword, 
                    types=('track',), 
                    limit=25
                )
                if search_results[0]:  # search_results is a tuple (tracks, None, None, None)
                    all_tracks.extend(search_results[0].items)
            except Exception as e:
                print(f"Search error for keyword {keyword}: {e}")
        
        # Remove duplicates and return random selection
        unique_tracks = {}
        for track in all_tracks:
            if track.id not in unique_tracks:
                unique_tracks[track.id] = track
        
        unique_tracks_list = list(unique_tracks.values())
        return random.sample(unique_tracks_list, min(count, len(unique_tracks_list)))