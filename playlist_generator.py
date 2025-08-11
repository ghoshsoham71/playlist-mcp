import random
from typing import Dict, List, Any, Tuple
import spotipy
from spotify_handler import SpotifyAuthHandler

class PlaylistGenerator:
    """Generates Spotify playlists based on sentiment analysis and user preferences."""
    
    def __init__(self, spotify_client: spotipy.Spotify):
        self.spotify = spotify_client
        self.handler = SpotifyAuthHandler()
        self.handler.client = spotify_client
        
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
        user_profile = self.handler.get_user_profile()
        user_id = user_profile['id']
        
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
        playlist = self.handler.create_playlist(
            user_id=user_id,
            name=playlist_name,
            description=playlist_description,
            public=False
        )
        
        # Add tracks to playlist
        track_uris = [track['uri'] for track in all_tracks]
        self.handler.add_tracks_to_playlist(playlist['id'], track_uris)
        
        return playlist['external_urls']['spotify']
    
    async def _get_user_tracks(self, count: int, analysis_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get tracks from user's listening history that match the sentiment."""
        try:
            # Get user's top tracks and recent tracks
            top_tracks = self.handler.get_user_top_tracks(limit=50)['items']
            recent_tracks = [item['track'] for item in self.handler.get_user_recently_played(limit=50)['items']]
            
            # Combine and deduplicate
            all_user_tracks = {track['id']: track for track in top_tracks + recent_tracks}.values()
            
            # Filter tracks based on sentiment if we have enough data
            if len(all_user_tracks) > count * 2:
                filtered_tracks = await self._filter_tracks_by_sentiment(list(all_user_tracks), analysis_result)
            else:
                filtered_tracks = list(all_user_tracks)
            
            # Return random selection
            return random.sample(filtered_tracks, min(count, len(filtered_tracks)))
            
        except Exception as e:
            print(f"Error getting user tracks: {e}")
            return []
    
    async def _get_recommended_tracks(self, count: int, analysis_result: Dict[str, Any], user_tracks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get recommended tracks based on sentiment analysis."""
        # Determine primary sentiment
        sentiment_scores = analysis_result['sentiment']
        primary_sentiment = max(sentiment_scores.items(), key=lambda x: x[1])[0]
        
        # Get audio features for sentiment
        target_features = self.sentiment_mapping.get(primary_sentiment, self.sentiment_mapping['neutral'])
        
        # Use user tracks as seeds if available
        seed_tracks = [track['id'] for track in user_tracks[:5]] if user_tracks else []
        
        # Get recommendations
        try:
            recommendations = self.handler.get_recommendations(
                seed_tracks=seed_tracks,
                limit=min(100, count * 2),  # Get more than needed for filtering
                target_valence=target_features['valence'],
                target_energy=target_features['energy'],
                target_danceability=target_features['danceability']
            )
            
            # Filter out duplicates from user tracks
            user_track_ids = {track['id'] for track in user_tracks}
            filtered_recs = [
                track for track in recommendations['tracks'] 
                if track['id'] not in user_track_ids
            ]
            
            return filtered_recs[:count]
            
        except Exception as e:
            print(f"Error getting recommendations: {e}")
            # Fallback: search for tracks based on sentiment keywords
            return await self._fallback_search(count, primary_sentiment)
    
    async def _filter_tracks_by_sentiment(self, tracks: List[Dict[str, Any]], analysis_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Filter tracks based on their audio features matching the sentiment."""
        # Get audio features for all tracks
        track_ids = [track['id'] for track in tracks]
        
        try:
            audio_features = self.handler.get_track_audio_features(track_ids)
            
            # Determine target sentiment
            sentiment_scores = analysis_result['sentiment']
            primary_sentiment = max(sentiment_scores.items(), key=lambda x: x[1])[0]
            target_features = self.sentiment_mapping.get(primary_sentiment, self.sentiment_mapping['neutral'])
            
            # Score tracks based on how well they match target sentiment
            scored_tracks = []
            for track, features in zip(tracks, audio_features):
                if features and isinstance(features, dict):
                    score = self._calculate_sentiment_match_score(features, target_features)
                    scored_tracks.append((track, score))
            
            # Sort by score and return top matches
            scored_tracks.sort(key=lambda x: x[1], reverse=True)
            return [track for track, _ in scored_tracks]
            
        except Exception as e:
            print(f"Error filtering tracks by sentiment: {e}")
            return tracks
    
    def _calculate_sentiment_match_score(self, track_features: Dict[str, Any], target_features: Dict[str, float]) -> float:
        """Calculate how well a track's features match target sentiment features."""
        score = 0.0
        for feature, target_value in target_features.items():
            if feature in track_features and track_features[feature] is not None:
                # Calculate proximity to target (closer = higher score)
                diff = abs(track_features[feature] - target_value)
                score += 1.0 - diff
        
        return score / len(target_features)
    
    async def _fallback_search(self, count: int, sentiment: str) -> List[Dict[str, Any]]:
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
                search_results = self.handler.search_tracks(keyword, limit=25)
                all_tracks.extend(search_results['tracks']['items'])
            except Exception as e:
                print(f"Search error for keyword {keyword}: {e}")
        
        # Remove duplicates and return random selection
        unique_tracks = {track['id']: track for track in all_tracks}.values()
        return random.sample(list(unique_tracks), min(count, len(unique_tracks)))