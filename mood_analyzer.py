"""Mood analysis with fallback to rule-based detection"""
import re
import logging
from typing import Dict, List, Any
import asyncio

logger = logging.getLogger(__name__)

class MoodAnalyzer:
    def __init__(self):
        self.initialized = False
        self.emotion_pipeline = None
        
    async def initialize(self):
        """Try to load AI models with timeout, fallback to rule-based"""
        try:
            # Add timeout for model loading
            await asyncio.wait_for(self._load_model(), timeout=30.0)
            logger.info("✅ AI emotion model loaded successfully")
        except asyncio.TimeoutError:
            logger.warning("⚠️ AI model loading timed out. Using rule-based analysis")
            self.initialized = False
        except Exception as e:
            logger.warning(f"⚠️ AI models failed: {e}. Using rule-based analysis")
            self.initialized = False
    
    async def _load_model(self):
        """Load AI model in a separate method for timeout control"""
        try:
            from transformers import pipeline
            import torch
            
            # Use a smaller, faster model
            model_name = "cardiffnlp/twitter-roberta-base-emotion-multilabel-latest"
            
            # Configure pipeline for faster loading
            self.emotion_pipeline = pipeline(
                "text-classification", 
                model=model_name,
                return_all_scores=False,
                device=-1,  # Force CPU usage
                model_kwargs={"torch_dtype": torch.float32}
            )
            self.initialized = True
            
        except ImportError:
            logger.info("Transformers not available, using rule-based analysis")
            self.initialized = False
        except Exception as e:
            logger.warning(f"Model loading failed: {e}")
            self.initialized = False
    
    def extract_emojis(self, text: str) -> List[str]:
        """Extract emojis"""
        pattern = re.compile(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F]+')
        return pattern.findall(text)
    
    def analyze_emoji_mood(self, emojis: List[str]) -> str:
        """Map emojis to moods with better romantic detection"""
        if not emojis:
            return "neutral"
            
        # Enhanced emoji mapping
        emoji_mood_map = {
            "romantic": ["😍", "🥰", "💕", "❤️", "💖", "💘", "😘", "🌹", "💝", "💞", "💗", "💓", "💌"],
            "sad": ["😢", "😭", "😞", "😔", "💔", "🥺", "😿", "😪", "😟", "🙁", "☹️"],
            "angry": ["😠", "😡", "🤬", "👿", "💢", "😾", "😤", "🔥"],
            "excited": ["🎉", "🥳", "🔥", "💪", "⚡", "🚀", "🙌", "🎊", "✨", "💥"],
            "calm": ["😌", "🧘‍♀️", "🧘‍♂️", "🕯️", "☮️", "😴", "🍃", "🌙", "🌸"],
            "energetic": ["🏃‍♀️", "🏃‍♂️", "💪", "🔋", "⚡", "🏋️", "🚴‍♀️", "🚴‍♂️", "⭐", "🌟"],
            "happy": ["😊", "😃", "😄", "🤗", "😆", "🙂", "😁", "🤩", "😋", "😎"]
        }
        
        # Check each emoji against mood categories
        for mood, mood_emojis in emoji_mood_map.items():
            for emoji in emojis:
                if emoji in mood_emojis:
                    return mood
        
        return "neutral"
    
    def extract_duration(self, text: str) -> int:
        """Extract duration in minutes with better pattern matching"""
        patterns = [
            (r'(\d+)\s*(?:hours?|hrs?|h)\b', lambda x: int(x) * 60),
            (r'(\d+)\s*(?:minutes?|mins?|m)\b', lambda x: int(x)),
            (r'(\d+)\s*(?:songs?|tracks?)\b', lambda x: int(x) * 4)  # Assume 4 min per song
        ]
        
        text_lower = text.lower()
        for pattern, converter in patterns:
            match = re.search(pattern, text_lower)
            if match:
                try:
                    return converter(match.group(1))
                except (ValueError, IndexError):
                    continue
        
        return 30  # Default 30 minutes
    
    def extract_languages(self, text: str) -> List[str]:
        """Extract language preferences with better detection"""
        text_lower = text.lower()
        
        lang_keywords = {
            "hindi": ["hindi", "bollywood", "bhojpuri", "indian"],
            "english": ["english", "hollywood", "western", "american"],
            "punjabi": ["punjabi", "bhangra"],
            "bengali": ["bengali", "bangla", "bengali", "kolkata"],
            "tamil": ["tamil", "kollywood", "chennai"],
            "telugu": ["telugu", "tollywood", "hyderabad"],
            "spanish": ["spanish", "latino", "latina"],
            "korean": ["korean", "k-pop", "kpop", "korea"],
            "french": ["french", "france"],
            "german": ["german", "germany"]
        }
        
        found = []
        for lang, keywords in lang_keywords.items():
            if any(k in text_lower for k in keywords):
                found.append(lang)
        
        # Default to Hindi and English if nothing specific found
        return found if found else ["hindi", "english"]
    
    def analyze_text_mood(self, text: str) -> str:
        """Enhanced rule-based mood detection"""
        text_lower = text.lower()
        
        # Expanded mood keywords with scores
        mood_keywords = {
            "happy": {
                "keywords": ["happy", "joy", "joyful", "cheerful", "good", "great", "awesome", "fun", "celebration", "upbeat", "positive", "bright"],
                "weight": 1.0
            },
            "sad": {
                "keywords": ["sad", "depressed", "depression", "cry", "crying", "heartbreak", "heartbroken", "lonely", "hurt", "down", "blue", "melancholy", "sorrow"],
                "weight": 1.0
            },
            "angry": {
                "keywords": ["angry", "mad", "hate", "frustrated", "annoyed", "irritated", "furious", "rage"],
                "weight": 1.0
            },
            "excited": {
                "keywords": ["excited", "thrilled", "pumped", "party", "hype", "electric", "buzzing"],
                "weight": 1.0
            },
            "calm": {
                "keywords": ["calm", "peaceful", "relax", "relaxing", "chill", "meditation", "zen", "tranquil", "serene", "quiet"],
                "weight": 1.0
            },
            "romantic": {
                "keywords": ["love", "romantic", "valentine", "heart", "date", "romance", "intimate", "passion", "affection"],
                "weight": 1.2  # Higher weight for romantic
            },
            "energetic": {
                "keywords": ["energetic", "workout", "gym", "dance", "dancing", "motivation", "motivational", "power", "strong"],
                "weight": 1.0
            }
        }
        
        best_mood = "neutral"
        max_score = 0
        
        for mood, config in mood_keywords.items():
            keywords = config["keywords"]
            weight = config["weight"]
            
            # Count keyword matches
            score = sum(1 for k in keywords if k in text_lower) * weight
            
            # Bonus for exact mood mentions
            if mood in text_lower:
                score += 2
            
            if score > max_score:
                max_score = score
                best_mood = mood
        
        return best_mood
    
    async def analyze_query(self, query: str) -> Dict[str, Any]:
        """Main analysis function with improved logic"""
        logger.info(f"Analyzing query: '{query}'")
        
        # Extract basic components
        emojis = self.extract_emojis(query)
        emoji_mood = self.analyze_emoji_mood(emojis)
        text_mood = self.analyze_text_mood(query)
        
        logger.info(f"Emoji mood: {emoji_mood}, Text mood: {text_mood}")
        
        # Determine final mood with priority system
        final_mood = "neutral"
        confidence = 0.5
        
        # Priority 1: Emoji mood (if not neutral)
        if emoji_mood != "neutral":
            final_mood = emoji_mood
            confidence = 0.8
            logger.info(f"Using emoji mood: {final_mood}")
        
        # Priority 2: Text mood (if no emoji mood)
        elif text_mood != "neutral":
            final_mood = text_mood
            confidence = 0.7
            logger.info(f"Using text mood: {final_mood}")
        
        # Priority 3: Try AI analysis if available and initialized
        if self.initialized and self.emotion_pipeline:
            try:
                # Clean text for AI analysis
                text_clean = re.sub(r'[^\w\s]', ' ', query).strip()
                if text_clean and len(text_clean) > 3:
                    
                    # Run AI analysis with timeout
                    ai_result = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            None, self.emotion_pipeline, text_clean
                        ),
                        timeout=5.0
                    )
                    
                    if isinstance(ai_result, list):
                        ai_result = ai_result[0]
                    
                    # Map AI emotions to our mood categories
                    emotion_map = {
                        "joy": "happy", 
                        "happiness": "happy",
                        "sadness": "sad", 
                        "anger": "angry",
                        "fear": "calm", 
                        "surprise": "excited", 
                        "love": "romantic",
                        "admiration": "romantic",
                        "desire": "romantic",
                        "caring": "romantic",
                        "excitement": "excited",
                        "optimism": "happy"
                    }
                    
                    ai_mood = emotion_map.get(ai_result.get('label', '').lower(), final_mood)
                    ai_confidence = ai_result.get('score', 0)
                    
                    # Use AI result if confidence is high and no strong emoji override
                    if ai_confidence > 0.6 and (emoji_mood == "neutral" or ai_confidence > 0.8):
                        final_mood = ai_mood
                        confidence = ai_confidence
                        logger.info(f"AI analysis used: {ai_mood} (confidence: {ai_confidence:.2f})")
                    else:
                        logger.info(f"AI analysis ignored: {ai_mood} (confidence: {ai_confidence:.2f})")
            
            except asyncio.TimeoutError:
                logger.warning("AI analysis timed out")
            except Exception as e:
                logger.warning(f"AI analysis failed: {e}")
        
        # Import config here to avoid circular imports
        from config import Config
        config = Config()
        
        # Calculate energy and valence based on mood
        energy_map = {
            "excited": 0.9, "energetic": 0.9, "angry": 0.8, "happy": 0.7,
            "romantic": 0.5, "neutral": 0.5, "calm": 0.3, "sad": 0.2
        }
        
        valence_map = {
            "happy": 0.9, "excited": 0.9, "romantic": 0.8, "energetic": 0.7,
            "calm": 0.6, "neutral": 0.5, "sad": 0.2, "angry": 0.1
        }
        
        result = {
            "mood": final_mood,
            "emotion": final_mood,
            "sentiment": "positive" if final_mood in ["happy", "excited", "romantic"] else "negative" if final_mood in ["sad", "angry"] else "neutral",
            "confidence": confidence,
            "genres": config.get_emotion_genres(final_mood),
            "languages": self.extract_languages(query),
            "duration_minutes": self.extract_duration(query),
            "num_songs": max(5, min(20, self.extract_duration(query) // 4)),
            "energy_level": energy_map.get(final_mood, 0.5),
            "valence": valence_map.get(final_mood, 0.5),
            "emojis": emojis
        }
        
        logger.info(f"Final analysis: mood={final_mood}, confidence={confidence:.2f}")
        return result