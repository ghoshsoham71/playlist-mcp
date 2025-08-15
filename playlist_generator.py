import os
import json
import random
import logging
from typing import List, Dict, Any
from datetime import datetime
from dotenv import load_dotenv
from spotify_handler import SpotifyHandler

SERVICE_NAME = "SpotifyPlaylistMCP"
logging.basicConfig(
    level=logging.INFO,
    format=f"[%(asctime)s] [{SERVICE_NAME}.%(name)s:%(lineno)d] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

import google.generativeai as genai
from google.generativeai.generative_models import GenerativeModel
from google.generativeai.client import configure

class PlaylistGenerator:
    """Playlist generator using Gemini AI for recommendations."""
        
    def __init__(self, spotify_handler: SpotifyHandler):
        load_dotenv()
        self.spotify = spotify_handler
        self.model = None
        
        # Configure Gemini if available
        if genai:
            gemini_api_key = os.getenv("GEMINI_API_KEY")
            if gemini_api_key:
                try:
                    configure(api_key=gemini_api_key)
                    self.model = GenerativeModel('gemini-1.5-flash')
                    logger.info("Playlist generator initialized with Gemini")
                except Exception as e:
                    logger.warning(f"Failed to initialize Gemini: {e}")
                    self.model = None
            else:
                logger.warning("GEMINI_API_KEY not set, using fallback mode")
        else:
            logger.info("Using fallback mode without Gemini AI")
                    
    async def create_playlist(
        self, 
        prompt: str, 
        duration_minutes: int, 
        playlist_name: str
    ) -> str:
        """Create a playlist using AI recommendations."""
        
        logger.info(f"Creating playlist: '{playlist_name}' with prompt: '{prompt}'")
        
        # Step 1: Get user context if authenticated
        user_context = ""
        if self.spotify.is_authenticated():
            user_context = await self._get_user_context()
        
        # Step 2: Generate search queries (with or without AI)
        search_queries = await self._generate_search_queries(prompt, user_context)
        logger.info(f"Generated {len(search_queries)} search queries")
        
        # Step 3: Search for tracks using generated queries
        all_tracks = []
        for query in search_queries:
            tracks = self.spotify.search_tracks(query, limit=15)
            if tracks:
                all_tracks.extend(tracks)
                logger.info(f"Found {len(tracks)} tracks for query: '{query}'")
        
        logger.info(f"Total tracks found from searches: {len(all_tracks)}")
        
        # Step 4: Get recommendations if we have user data and found tracks
        if self.spotify.is_authenticated() and all_tracks:
            try:
                # Use some found tracks as seeds for recommendations
                seed_ids = [track["id"] for track in all_tracks[:5] if track.get("id")]
                if seed_ids:
                    rec_tracks = self.spotify.get_recommendations(seed_ids, limit=20)
                    if rec_tracks:
                        all_tracks.extend(rec_tracks)
                        logger.info(f"Added {len(rec_tracks)} recommended tracks")
            except Exception as e:
                logger.warning(f"Failed to get recommendations: {e}")
        
        # Step 5: Remove duplicates
        unique_tracks = self._remove_duplicates(all_tracks)
        logger.info(f"Unique tracks after deduplication: {len(unique_tracks)}")
        
        if not unique_tracks:
            # If no tracks found, try some fallback searches
            fallback_queries = self._get_bollywood_fallback_queries() if 'bollywood' in prompt.lower() else ['popular songs', 'top hits']
            for query in fallback_queries:
                tracks = self.spotify.search_tracks(query, limit=20)
                unique_tracks.extend(tracks)
            
            unique_tracks = self._remove_duplicates(unique_tracks)
            
            if not unique_tracks:
                raise Exception("No tracks found for the given prompt. Please try a different search term.")
        
        # Step 6: Curate the final playlist
        selected_tracks = await self._curate_playlist(
            unique_tracks, prompt, duration_minutes
        )
        
        logger.info(f"Selected {len(selected_tracks)} tracks for playlist")
        
        # Step 7: Save track data
        await self._save_playlist_data(selected_tracks, prompt, playlist_name)
        
        # Step 8: Create Spotify playlist
        playlist_url = self.spotify.create_playlist(
            name=playlist_name,
            description=f"AI-generated playlist: {prompt}"
        )
        
        # Step 9: Add tracks to playlist
        track_uris = [track["uri"] for track in selected_tracks if track.get("uri")]
        if track_uris:
            playlist_id = playlist_url.split("/")[-1]
            added_count = self.spotify.add_tracks_to_playlist(playlist_id, track_uris)
            logger.info(f"Added {added_count} tracks to playlist")
        
        logger.info(f"Playlist created successfully: {playlist_url}")
        return playlist_url
    
    def _get_bollywood_fallback_queries(self) -> List[str]:
        """Get Bollywood-specific fallback queries."""
        return [
            "bollywood hits",
            "hindi songs",
            "arijit singh",
            "shreya ghoshal", 
            "atif aslam",
            "rahat fateh ali khan",
            "armaan malik",
            "bollywood romantic",
            "bollywood dance",
            "latest bollywood",
            "90s bollywood",
            "ar rahman"
        ]
    
    async def _get_user_context(self) -> str:
        """Get user listening context for better recommendations."""
        try:
            # Load recent user data if available
            import glob
            data_files = glob.glob("user_data_*.json")
            if not data_files:
                return ""
            
            # Get the most recent file
            latest_file = max(data_files, key=os.path.getctime)
            with open(latest_file, 'r', encoding='utf-8') as f:
                user_data = json.load(f)
            
            # Extract key preferences
            top_artists = []
            if user_data.get("top_tracks"):
                top_artists = list(set([
                    track["artist"] for track in user_data["top_tracks"][:10]
                ]))[:5]
            
            context = f"User's top artists: {', '.join(top_artists)}" if top_artists else ""
            return context
            
        except Exception as e:
            logger.warning(f"Failed to get user context: {e}")
            return ""
    
    async def _generate_search_queries(self, prompt: str, user_context: str) -> List[str]:
        """Generate search queries using AI or fallback method."""
        # If Gemini is not available, use simple fallback
        if not self.model:
            return self._generate_fallback_queries(prompt)
            
        try:
            gemini_prompt = f"""
            Based on the user's request: "{prompt}"
            {f"And their listening history: {user_context}" if user_context else ""}
            
            Generate 5-7 specific music search queries that would find relevant songs on Spotify.
            Focus on:
            1. Genre keywords
            2. Mood/emotion keywords  
            3. Popular artist names in that genre
            4. Musical characteristics
            5. Popular songs that match the vibe
            
            For Bollywood requests, include popular Bollywood artists and Hindi music terms.
            
            Return only the search queries, one per line, without numbering or formatting.
            Each query should be 2-4 words max for best Spotify search results.
            
            Examples:
            - For "workout music": "high energy rock", "pump up songs", "electronic dance", "motivational rap"
            - For "bollywood music": "bollywood hits", "arijit singh", "hindi songs", "shreya ghoshal"
            - For "sad songs": "melancholy ballads", "acoustic sad", "emotional indie", "heartbreak songs"
            """
            
            response = self.model.generate_content(gemini_prompt)
            queries = [
                line.strip() 
                for line in response.text.split('\n') 
                if line.strip() and not line.strip().startswith('-') and not line.strip().startswith('*')
            ]
            
            # Fallback queries if Gemini response is empty or invalid
            if not queries or len(queries) == 0:
                logger.warning("Gemini returned no valid queries, using fallback")
                return self._generate_fallback_queries(prompt)
            
            logger.info(f"Gemini generated search queries: {queries}")
            return queries[:7]  # Limit to 7 queries
            
        except Exception as e:
            logger.error(f"Failed to generate search queries with Gemini: {e}")
            return self._generate_fallback_queries(prompt)
    
    def _generate_fallback_queries(self, prompt: str) -> List[str]:
        """Generate search queries without AI."""
        queries = [prompt]
        prompt_lower = prompt.lower()
        
        # Bollywood-specific queries
        if 'bollywood' in prompt_lower or 'hindi' in prompt_lower or 'indian' in prompt_lower:
            queries.extend([
                'bollywood hits',
                'arijit singh',
                'shreya ghoshal',
                'atif aslam',
                'hindi songs',
                'bollywood romantic',
                'ar rahman'
            ])
            return list(set(queries))[:7]
        
        # Add genre-based queries
        genres = ['pop', 'rock', 'hip hop', 'electronic', 'indie', 'jazz', 'country', 'r&b']
        for genre in genres:
            if genre in prompt_lower:
                queries.append(f"{genre} music")
                queries.append(f"best {genre}")
        
        # Add mood-based queries
        if any(word in prompt_lower for word in ['happy', 'upbeat', 'energetic', 'party']):
            queries.extend(['upbeat songs', 'dance music', 'party hits'])
        elif any(word in prompt_lower for word in ['sad', 'emotional', 'melancholy']):
            queries.extend(['sad songs', 'ballads', 'emotional music'])
        elif any(word in prompt_lower for word in ['chill', 'relax', 'calm']):
            queries.extend(['chill music', 'relaxing songs', 'ambient'])
        elif any(word in prompt_lower for word in ['workout', 'gym', 'exercise']):
            queries.extend(['workout music', 'high energy', 'pump up'])
        
        # Add popular fallbacks
        queries.extend(['popular music', 'trending songs'])
        
        return list(set(queries))[:7]  # Remove duplicates and limit
    
    async def _curate_playlist(
        self, 
        tracks: List[Dict[str, Any]], 
        prompt: str, 
        duration_minutes: int
    ) -> List[Dict[str, Any]]:
        """Curate and select the best tracks for the playlist."""
        # Estimate target number of tracks (average 3.5 min per song)
        target_count = max(10, min(50, int(duration_minutes / 3.5)))
        
        # If we don't have too many tracks, just return them shuffled
        if len(tracks) <= target_count:
            random.shuffle(tracks)
            return tracks
        
        # If Gemini is not available, use simple selection
        if not self.model:
            return self._simple_track_selection(tracks, target_count, prompt)
            
        try:
            # Prepare track data for Gemini (limit to first 100 for processing)
            tracks_to_process = tracks[:100]
            track_summaries = []
            for i, track in enumerate(tracks_to_process):
                summary = f"{i}: {track['name']} by {track['artist']} (popularity: {track.get('popularity', 0)})"
                track_summaries.append(summary)
            
            gemini_prompt = f"""
            You are a music curator. Select the best {target_count} tracks from this list for a playlist with the theme: "{prompt}"
            
            Available tracks:
            {chr(10).join(track_summaries)}
            
            Consider:
            1. How well each track matches the prompt/theme
            2. Musical variety and flow
            3. Track popularity and quality
            4. Good mix of familiar and discovery tracks
            5. For Bollywood playlists, prioritize well-known Bollywood artists and Hindi songs
            
            Return only the numbers (0-{len(track_summaries)-1}) of your selected tracks, separated by commas.
            Example: 0,5,12,18,25,33,41,48
            """
            
            response = self.model.generate_content(gemini_prompt)
            
            # Parse the response
            selected_indices = []
            try:
                indices_text = response.text.strip()
                # Remove any extra text and extract just the numbers
                indices_text = indices_text.split('\n')[0]  # Take first line
                selected_indices = [
                    int(idx.strip()) 
                    for idx in indices_text.split(',') 
                    if idx.strip().isdigit() and int(idx.strip()) < len(tracks_to_process)
                ]
            except:
                logger.warning("Failed to parse Gemini track selection")
                return self._simple_track_selection(tracks, target_count, prompt)
            
            # Validate indices and select tracks
            selected_tracks = []
            for idx in selected_indices:
                if 0 <= idx < len(tracks_to_process):
                    selected_tracks.append(tracks_to_process[idx])
            
            # If we don't have enough tracks, fill with random selection
            if len(selected_tracks) < target_count // 2:
                logger.warning("Gemini selection insufficient, using simple selection")
                return self._simple_track_selection(tracks, target_count, prompt)
            
            # If we still need more tracks, add some popular ones
            if len(selected_tracks) < target_count:
                remaining_tracks = [t for t in tracks if t not in selected_tracks]
                remaining_tracks.sort(key=lambda x: x.get('popularity', 0), reverse=True)
                needed = target_count - len(selected_tracks)
                selected_tracks.extend(remaining_tracks[:needed])
            
            random.shuffle(selected_tracks)
            logger.info(f"Curated {len(selected_tracks)} tracks from {len(tracks)} candidates")
            return selected_tracks[:target_count]
            
        except Exception as e:
            logger.error(f"Track curation failed: {e}")
            return self._simple_track_selection(tracks, target_count, prompt)
    
    def _simple_track_selection(
        self, 
        tracks: List[Dict[str, Any]], 
        target_count: int, 
        prompt: str
    ) -> List[Dict[str, Any]]:
        """Simple track selection without AI."""
        # Sort by popularity and select a mix
        sorted_tracks = sorted(tracks, key=lambda x: x.get('popularity', 0), reverse=True)
        
        # Take 70% popular tracks, 30% random for discovery
        popular_count = int(target_count * 0.7)
        random_count = target_count - popular_count
        
        selected = sorted_tracks[:popular_count]
        
        # Add random tracks from the rest
        remaining = sorted_tracks[popular_count:]
        if remaining and random_count > 0:
            random.shuffle(remaining)
            selected.extend(remaining[:random_count])
        
        # Final shuffle
        random.shuffle(selected)
        logger.info(f"Simple selection: {len(selected)} tracks selected")
        return selected[:target_count]
    
    def _remove_duplicates(self, tracks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate tracks based on ID."""
        seen = set()
        unique = []
        
        for track in tracks:
            track_id = track.get("id")
            if track_id and track_id not in seen:
                seen.add(track_id)
                unique.append(track)
            elif not track_id:
                # If no ID, use name+artist as identifier
                identifier = f"{track.get('name', '')}-{track.get('artist', '')}"
                if identifier not in seen:
                    seen.add(identifier)
                    unique.append(track)
        
        return unique
    
    async def _save_playlist_data(
        self, 
        tracks: List[Dict[str, Any]], 
        prompt: str, 
        playlist_name: str
    ):
        """Save playlist data to JSON file."""
        try:
            playlist_data = {
                "timestamp": datetime.now().isoformat(),
                "prompt": prompt,
                "playlist_name": playlist_name,
                "total_tracks": len(tracks),
                "tracks": tracks
            }
            
            filename = f"playlist_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(playlist_data, f, indent=2, default=str, ensure_ascii=False)
            
            logger.info(f"Playlist data saved to {filename}")
            
        except Exception as e:
            logger.error(f"Failed to save playlist data: {e}")