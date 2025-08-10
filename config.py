"""
Configuration management for the Mood Playlist MCP Server
"""

import os
from typing import List

class Config:
    """Configuration class for environment variables and settings"""
    
    def __init__(self):
        # Last.fm API credentials
        self.lastfm_api_key = os.getenv("LASTFM_API_KEY")
        self.lastfm_shared_secret = os.getenv("LASTFM_SHARED_SECRET")
        
        # MCP Server settings
        self.auth_token = os.getenv("AUTH_TOKEN", "your_secret_token_here")
        
        # Default settings
        self.default_languages = ["hindi", "english"]
        self.default_playlist_length = 5  # songs
        self.default_duration_minutes = 30
        
        # Hugging Face model settings (all free models)
        self.sentiment_model = "lxyuan/distilbert-base-multilingual-cased-sentiments-student"
        self.emotion_model = "SamLowe/roberta-base-go_emotions"
        self.language_detection_model = "papluca/xlm-roberta-base-language-detection"
        
        # Music platform URLs
        self.spotify_base_url = "https://open.spotify.com/search/"
        self.apple_music_base_url = "https://music.apple.com/search?term="
        
        # Supported languages (can be extended)
        self.supported_languages = [
            "hindi", "english", "punjabi", "bengali", "tamil", "telugu", 
            "marathi", "gujarati", "kannada", "malayalam", "spanish", 
            "french", "german", "italian", "japanese", "korean"
        ]
        
        # Genre mappings for different moods/emotions
        self.emotion_genre_map = {
            "happy": ["pop", "dance", "bollywood", "reggae", "funk"],
            "sad": ["ballad", "blues", "indie", "melancholic", "ghazal"],
            "angry": ["rock", "metal", "punk", "rap", "aggressive"],
            "excited": ["electronic", "dance", "pop", "party", "energetic"],
            "calm": ["ambient", "classical", "instrumental", "chill", "meditation"],
            "romantic": ["romantic", "love songs", "r&b", "slow", "ballad"],
            "nostalgic": ["retro", "oldies", "vintage", "classic", "throwback"],
            "energetic": ["workout", "high energy", "dance", "electronic", "upbeat"],
            "neutral": ["pop", "alternative", "indie"]
        }
    
    def validate(self) -> bool:
        """Validate required environment variables"""
        missing_vars = []
        
        if not self.lastfm_api_key:
            missing_vars.append("LASTFM_API_KEY")
        if not self.lastfm_shared_secret:
            missing_vars.append("LASTFM_SHARED_SECRET")
            
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        return True
    
    def get_emotion_genres(self, emotion: str) -> List[str]:
        """Get genres associated with an emotion"""
        return self.emotion_genre_map.get(emotion.lower(), ["pop", "bollywood"])
    
    def get_all_genres(self) -> List[str]:
        """Get all available genres"""
        genres = set()
        for genre_list in self.emotion_genre_map.values():
            genres.update(genre_list)
        return sorted(list(genres))