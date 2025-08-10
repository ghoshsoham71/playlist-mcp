"""
Mood and query analysis using Hugging Face transformers
"""

import re
import asyncio
import logging
from typing import Dict, List, Any, Optional
import emoji

logger = logging.getLogger(__name__)

class MoodAnalyzer:
    """Analyzes user queries to extract mood, emotions, language, and duration preferences"""
    
    def __init__(self):
        self.sentiment_pipeline = None
        self.emotion_pipeline = None
        self.language_pipeline = None
        self.initialized = False
        
        # Emoji to emotion mapping (learned dynamically but with fallbacks)
        self.emoji_emotion_cache = {}
        
        # Duration parsing patterns
        self.duration_patterns = [
            (r'(\d+)\s*(?:hour|hr|h)(?:s)?', lambda x: int(x) * 60),
            (r'(\d+)\s*(?:minute|min|m)(?:s)?', lambda x: int(x)),
            (r'(\d+)\s*(?:song|track)(?:s)?', lambda x: int(x) * 4)  # Assume 4 min per song
        ]
    
    async def initialize(self):
        """Initialize Hugging Face models with error handling"""
        if self.initialized:
            return
            
        try:
            logger.info("Initializing AI models...")
            
            # Import transformers here to avoid issues
            from transformers import pipeline
            
            # Initialize sentiment analysis (multilingual)
            logger.info("Loading sentiment analysis model...")
            self.sentiment_pipeline = pipeline(
                "text-classification",
                model="lxyuan/distilbert-base-multilingual-cased-sentiments-student",
                return_all_scores=False
            )
            
            # Initialize emotion detection (more emotions)
            logger.info("Loading emotion detection model...")
            self.emotion_pipeline = pipeline(
                "text-classification",
                model="SamLowe/roberta-base-go_emotions",
                return_all_scores=False
            )
            
            # Initialize language detection
            logger.info("Loading language detection model...")
            self.language_pipeline = pipeline(
                "text-classification", 
                model="papluca/xlm-roberta-base-language-detection",
                return_all_scores=False
            )
            
            self.initialized = True
            logger.info("✅ AI models initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize models: {str(e)}")
            # Set fallback mode
            self.initialized = False
            logger.warning("Using fallback analysis mode without AI models")
    
    def extract_emojis(self, text: str) -> List[str]:
        """Extract emojis from text"""
        try:
            return [char for char in text if char in emoji.EMOJI_DATA]
        except:
            # Fallback: simple emoji detection
            emoji_pattern = re.compile(
                "["
                "\U0001F600-\U0001F64F"  # emoticons
                "\U0001F300-\U0001F5FF"  # symbols & pictographs
                "\U0001F680-\U0001F6FF"  # transport & map symbols
                "\U0001F1E0-\U0001F1FF"  # flags (iOS)
                "\U00002702-\U000027B0"
                "\U000024C2-\U0001F251"
                "]+"
            )
            return emoji_pattern.findall(text)
    
    def analyze_emoji_sentiment(self, emojis: List[str]) -> Dict[str, float]:
        """Analyze sentiment of emojis using cached results or heuristics"""
        if not emojis:
            return {"valence": 0.5, "energy": 0.5}
        
        total_valence = 0.0
        total_energy = 0.0
        count = 0
        
        for emo in emojis:
            if emo in self.emoji_emotion_cache:
                cached = self.emoji_emotion_cache[emo]
                total_valence += cached["valence"]
                total_energy += cached["energy"]
            else:
                # Heuristic analysis based on emoji categories
                valence, energy = self._heuristic_emoji_analysis(emo)
                self.emoji_emotion_cache[emo] = {"valence": valence, "energy": energy}
                total_valence += valence
                total_energy += energy
            count += 1
        
        return {
            "valence": total_valence / count if count > 0 else 0.5,
            "energy": total_energy / count if count > 0 else 0.5
        }
    
    def _heuristic_emoji_analysis(self, emo: str) -> tuple:
        """Heuristic emotion analysis for emojis"""
        # High valence (positive), high energy
        positive_energetic = "😎🤩🥳🎉💪🔥⚡🚀🎊🌟💥🎯"
        # High valence, low energy  
        positive_calm = "😊☺️😌🥰💕❤️🌸🌺💖😇🙏✨"
        # Low valence (negative), high energy
        negative_energetic = "😠😡🤬👿💢⚡😤🔥💥😾"
        # Low valence, low energy
        negative_calm = "😢😭😞😔💔😪😴😓🥺😰"
        
        if emo in positive_energetic:
            return (0.8, 0.8)  # High valence, high energy
        elif emo in positive_calm:
            return (0.8, 0.3)  # High valence, low energy
        elif emo in negative_energetic:
            return (0.2, 0.8)  # Low valence, high energy
        elif emo in negative_calm:
            return (0.2, 0.3)  # Low valence, low energy
        else:
            return (0.5, 0.5)  # Neutral
    
    def extract_duration(self, text: str) -> int:
        """Extract duration in minutes from text"""
        text_lower = text.lower()
        
        for pattern, converter in self.duration_patterns:
            match = re.search(pattern, text_lower)
            if match:
                return converter(match.group(1))
        
        # Default duration
        return 30
    
    def extract_languages(self, text: str) -> List[str]:
        """Extract language preferences from text"""
        text_lower = text.lower()
        languages = []
        
        # Common language keywords
        language_keywords = {
            "hindi": ["hindi", "bollywood", "bhojpuri", "हिंदी"],
            "english": ["english", "hollywood", "western"],
            "punjabi": ["punjabi", "ਪੰਜਾਬੀ"],
            "bengali": ["bengali", "bangla", "বাংলা"],
            "tamil": ["tamil", "தமிழ்"],
            "telugu": ["telugu", "తెలుగు"],
            "marathi": ["marathi", "मराठी"],
            "gujarati": ["gujarati", "ગુજરાતી"],
            "spanish": ["spanish", "español", "latino"],
            "french": ["french", "français"],
            "korean": ["korean", "k-pop", "kpop", "한국어"],
            "japanese": ["japanese", "j-pop", "jpop", "日本語"]
        }
        
        for lang, keywords in language_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                languages.append(lang)
        
        # If no languages detected, use default
        if not languages:
            languages = ["hindi", "english"]
            
        return languages
    
    def _fallback_analysis(self, query: str) -> Dict[str, Any]:
        """Fallback analysis when AI models are not available"""
        # Simple keyword-based analysis
        text_lower = query.lower()
        
        # Mood detection based on keywords
        mood_keywords = {
            "happy": ["happy", "joy", "cheerful", "upbeat", "good", "great", "amazing"],
            "sad": ["sad", "depressed", "down", "blue", "melancholy", "cry"],
            "angry": ["angry", "mad", "furious", "rage", "hate", "annoyed"],
            "excited": ["excited", "thrilled", "pumped", "energetic", "party"],
            "calm": ["calm", "peaceful", "relax", "chill", "serene", "quiet"],
            "romantic": ["love", "romantic", "valentine", "date", "heart"],
            "nostalgic": ["nostalgic", "memories", "old", "past", "remember"]
        }
        
        detected_mood = "neutral"
        for mood, keywords in mood_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                detected_mood = mood
                break
        
        return {
            "mood": detected_mood,
            "emotion": detected_mood,
            "sentiment": "positive" if detected_mood in ["happy", "excited", "romantic"] else "neutral",
            "confidence": 0.6
        }
    
    
    def _is_emoji(self, char: str) -> bool:
        """Check if character is an emoji"""
        try:
            return char in emoji.EMOJI_DATA
        except:
            # Fallback method
            return ord(char) > 0x1F300
    
    async def analyze_query(self, query: str) -> Dict[str, Any]:
        """
        Comprehensive analysis of user query
        
        Returns:
            Dictionary with mood, genres, languages, duration, energy, valence
        """
        # Try to initialize models
        await self.initialize()
        
        # Extract emojis
        emojis = self.extract_emojis(query)
        
        # Remove emojis for text analysis
        text_without_emojis = ''.join(char for char in query if not self._is_emoji(char)).strip()
        
        # Fallback if models failed to load
        if not self.initialized or not all([self.sentiment_pipeline, self.emotion_pipeline, self.language_pipeline]):
            logger.warning("Using fallback analysis - AI models not available")
            text_analysis = self._fallback_analysis(query)
        else:
            try:
                # Analyze sentiment
                if self.sentiment_pipeline is not None:
                    sentiment_result = self.sentiment_pipeline(text_without_emojis)[0]
                else:
                    raise RuntimeError("Sentiment pipeline is not initialized.")
                
                # Analyze emotions
                if self.emotion_pipeline is not None:
                    emotion_result = self.emotion_pipeline(text_without_emojis)[0]
                else:
                    raise RuntimeError("Emotion pipeline is not initialized.")
                
                text_analysis = {
                    "sentiment": sentiment_result,
                    "emotion": emotion_result
                }
            except Exception as e:
                logger.error(f"Error in AI analysis: {str(e)}")
                text_analysis = self._fallback_analysis(query)
        
        # Analyze emoji sentiment
        emoji_sentiment = self.analyze_emoji_sentiment(emojis)
        
        # Extract duration
        duration_minutes = self.extract_duration(query)
        
        # Extract languages
        languages = self.extract_languages(query)
        
        # Detect language of the text itself (with fallback)
        if text_without_emojis and self.initialized and self.language_pipeline:
            try:
                detected_lang = self.language_pipeline(text_without_emojis)[0]
                lang_code = detected_lang['label'].lower()
                # Map language codes to our supported languages
                lang_mapping = {
                    'hi': 'hindi', 'en': 'english', 'pa': 'punjabi', 
                    'bn': 'bengali', 'ta': 'tamil', 'te': 'telugu',
                    'mr': 'marathi', 'gu': 'gujarati', 'es': 'spanish',
                    'fr': 'french', 'ko': 'korean', 'ja': 'japanese'
                }
                if lang_code in lang_mapping and lang_mapping[lang_code] not in languages:
                    languages.append(lang_mapping[lang_code])
            except Exception as e:
                logger.warning(f"Language detection failed: {str(e)}")
        
        # Process results based on whether we have AI models or fallback
        if isinstance(text_analysis.get("sentiment"), dict):
            # AI model results
            sentiment_result = text_analysis["sentiment"]
            emotion_result = text_analysis["emotion"]
            
            text_valence = 0.8 if sentiment_result['label'] == 'positive' else (0.2 if sentiment_result['label'] == 'negative' else 0.5)
            combined_valence = (text_valence * 0.6) + (emoji_sentiment["valence"] * 0.4)
            
            # Energy level based on emotion and emojis
            high_energy_emotions = ["joy", "excitement", "anger", "happy", "excited"]
            emotion_energy = 0.8 if emotion_result['label'].lower() in high_energy_emotions else 0.4
            combined_energy = (emotion_energy * 0.6) + (emoji_sentiment["energy"] * 0.4)
            
            # Map emotion to mood categories (expanded for go_emotions model)
            mood_mapping = {
                "joy": "happy", "happiness": "happy", "excitement": "excited",
                "sadness": "sad", "grief": "sad", "disappointment": "sad",
                "anger": "angry", "annoyance": "angry", "rage": "angry",
                "fear": "anxious", "nervousness": "anxious", "worry": "anxious",
                "surprise": "excited", "amazement": "excited", "wonder": "excited",
                "disgust": "neutral", "boredom": "neutral",
                "love": "romantic", "caring": "romantic", "desire": "romantic",
                "calm": "calm", "peaceful": "calm", "relaxed": "calm",
                "energetic": "energetic", "enthusiasm": "energetic"
            }
            
            primary_mood = mood_mapping.get(emotion_result['label'].lower(), "neutral")
            confidence = emotion_result['score']
            
        else:
            # Fallback results
            text_valence = 0.8 if text_analysis['sentiment'] == 'positive' else (0.2 if text_analysis['sentiment'] == 'negative' else 0.5)
            combined_valence = (text_valence * 0.6) + (emoji_sentiment["valence"] * 0.4)
            combined_energy = 0.5 + (emoji_sentiment["energy"] * 0.5)
            primary_mood = text_analysis['mood']
            confidence = text_analysis['confidence']
        
        # Generate genres based on mood
        from config import Config
        config = Config()
        genres = config.get_emotion_genres(str(primary_mood))
        
        # Calculate number of songs based on duration
        avg_song_duration = 4  # minutes
        num_songs = max(3, min(50, duration_minutes // avg_song_duration))
        
        analysis_result = {
            "mood": primary_mood,
            "emotion": text_analysis.get("emotion", {}).get("label", primary_mood) if isinstance(text_analysis.get("emotion"), dict) else primary_mood,
            "sentiment": text_analysis.get("sentiment", {}).get("label", "neutral") if isinstance(text_analysis.get("sentiment"), dict) else text_analysis.get("sentiment", "neutral"),
            "confidence": confidence,
            "genres": genres,
            "languages": languages,
            "duration_minutes": duration_minutes,
            "num_songs": num_songs,
            "energy_level": combined_energy,
            "valence": combined_valence,
            "emojis": emojis,
            "text_analysis": text_analysis,
            "emoji_analysis": emoji_sentiment
        }
        
        logger.info(f"Query analysis complete: mood={primary_mood}, languages={languages}, duration={duration_minutes}min")
        
        return analysis_result