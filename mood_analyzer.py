"""Mood analysis with fallback to rule-based detection"""
import re
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

class MoodAnalyzer:
    def __init__(self):
        self.initialized = False
        
    async def initialize(self):
        """Try to load AI models, fallback to rule-based"""
        try:
            from transformers import pipeline
            self.emotion_pipeline = pipeline(
                "text-classification", 
                model="j-hartmann/emotion-english-distilroberta-base",
                return_all_scores=False
            )
            self.initialized = True
            logger.info("✅ AI emotion model loaded")
        except Exception as e:
            logger.warning(f"AI models failed: {e}. Using rule-based analysis")
            self.initialized = False
    
    def extract_emojis(self, text: str) -> List[str]:
        """Extract emojis"""
        pattern = re.compile(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF]+')
        return pattern.findall(text)
    
    def analyze_emoji_mood(self, emojis: List[str]) -> str:
        """Map emojis to moods with better romantic detection"""
        if not emojis:
            return "neutral"
            
        # Check each emoji individually for better accuracy
        for emoji in emojis:
            if emoji in "😍🥰💕❤️💖💘😘🌹💝💞":
                return "romantic"
            elif emoji in "😢😭😞😔💔🥺😿":
                return "sad"
            elif emoji in "😠😡🤬👿💢😾":
                return "angry"
            elif emoji in "🎉🥳🔥💪⚡🚀🙌":
                return "excited"
            elif emoji in "😌🧘‍♀️🕯️☮️😴":
                return "calm"
            elif emoji in "🏃‍♀️💪🔋⚡🏋️🚴‍♀️":
                return "energetic"
            elif emoji in "😊😃😄🤗😆🙂":
                return "happy"
        
        return "neutral"
    
    def extract_duration(self, text: str) -> int:
        """Extract duration in minutes"""
        patterns = [
            (r'(\d+)\s*(?:hour|hr|h)', lambda x: int(x) * 60),
            (r'(\d+)\s*(?:min|minute)', lambda x: int(x)),
            (r'(\d+)\s*(?:song|track)', lambda x: int(x) * 4)
        ]
        
        for pattern, converter in patterns:
            match = re.search(pattern, text.lower())
            if match:
                return converter(match.group(1))
        return 30
    
    def extract_languages(self, text: str) -> List[str]:
        """Extract language preferences"""
        text_lower = text.lower()
        
        lang_keywords = {
            "hindi": ["hindi", "bollywood", "bhojpuri"],
            "english": ["english", "hollywood", "western"],
            "punjabi": ["punjabi", "bhangra"],
            "bengali": ["bengali", "bangla"],
            "tamil": ["tamil", "kollywood"],
            "spanish": ["spanish", "latino"],
            "korean": ["korean", "k-pop", "kpop"]
        }
        
        found = []
        for lang, keywords in lang_keywords.items():
            if any(k in text_lower for k in keywords):
                found.append(lang)
        
        return found if found else ["hindi", "english"]
    
    def analyze_text_mood(self, text: str) -> str:
        """Rule-based mood detection"""
        text_lower = text.lower()
        
        mood_keywords = {
            "happy": ["happy", "joy", "cheerful", "good", "great", "awesome", "fun", "celebration"],
            "sad": ["sad", "depressed", "cry", "heartbreak", "lonely", "hurt", "down"],
            "angry": ["angry", "mad", "hate", "frustrated", "annoyed"],
            "excited": ["excited", "thrilled", "pumped", "party", "hype"],
            "calm": ["calm", "peaceful", "relax", "chill", "meditation", "zen"],
            "romantic": ["love", "romantic", "valentine", "heart", "date"],
            "energetic": ["energetic", "workout", "gym", "dance", "motivation"]
        }
        
        best_mood = "neutral"
        max_score = 0
        
        for mood, keywords in mood_keywords.items():
            score = sum(1 for k in keywords if k in text_lower)
            if score > max_score:
                max_score = score
                best_mood = mood
        
        return best_mood
    
    async def analyze_query(self, query: str) -> Dict[str, Any]:
        """Main analysis function"""
        logger.info(f"Analyzing: '{query}'")
        
        emojis = self.extract_emojis(query)
        emoji_mood = self.analyze_emoji_mood(emojis)
        text_mood = self.analyze_text_mood(query)
        
        # Prioritize emoji mood if found, otherwise use text mood
        final_mood = emoji_mood if emoji_mood != "neutral" else text_mood
        
        # Try AI analysis if available
        if self.initialized and self.emotion_pipeline:
            try:
                text_clean = re.sub(r'[^\w\s]', '', query).strip()
                if text_clean:
                    ai_result = self.emotion_pipeline(text_clean)
                    if isinstance(ai_result, list):
                        ai_result = ai_result[0]
                    
                    # Map AI emotions to our moods with better romantic detection
                    emotion_map = {
                        "joy": "happy", 
                        "sadness": "sad", 
                        "anger": "angry",
                        "fear": "calm", 
                        "surprise": "excited", 
                        "love": "romantic",
                        "admiration": "romantic",  # Added
                        "desire": "romantic",      # Added
                        "caring": "romantic"       # Added
                    }
                    
                    ai_mood = emotion_map.get(ai_result['label'], final_mood)
                    
                    # Don't override romantic detection from emojis
                    if emoji_mood == "romantic":
                        final_mood = "romantic"
                        logger.info(f"Emoji override: keeping romantic mood")
                    elif ai_result['score'] > 0.6:
                        final_mood = ai_mood
                        logger.info(f"AI detected: {ai_mood} (score: {ai_result['score']:.2f})")
                    else:
                        logger.info(f"AI confidence low, keeping: {final_mood}")
            except Exception as e:
                logger.warning(f"AI analysis failed: {e}")
        
        # Import config here to avoid circular imports
        from config import Config
        config = Config()
        
        return {
            "mood": final_mood,
            "emotion": final_mood,
            "sentiment": "positive" if final_mood in ["happy", "excited", "romantic"] else "negative" if final_mood in ["sad", "angry"] else "neutral",
            "confidence": 0.8,
            "genres": config.get_emotion_genres(final_mood),
            "languages": self.extract_languages(query),
            "duration_minutes": self.extract_duration(query),
            "num_songs": max(5, min(15, self.extract_duration(query) // 4)),
            "energy_level": 0.8 if final_mood in ["excited", "energetic", "angry"] else 0.3 if final_mood in ["calm", "sad"] else 0.5,
            "valence": 0.8 if final_mood in ["happy", "excited", "romantic"] else 0.2 if final_mood in ["sad", "angry"] else 0.5,
            "emojis": emojis
        }