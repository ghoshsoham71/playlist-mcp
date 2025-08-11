import re
import emoji
from typing import Dict, List, Any
import asyncio


class SentimentAnalyzer:
    """Ultra-lightweight sentiment analyzer using rule-based approach with minimal dependencies."""
    
    def __init__(self):
        # No ML models loaded - pure rule-based approach
        self.positive_keywords = {
            "happy", "joy", "love", "amazing", "awesome", "great", "wonderful", 
            "fantastic", "excellent", "good", "nice", "beautiful", "perfect", 
            "excited", "thrilled", "delighted", "cheerful", "upbeat", "energetic",
            "motivational", "inspiring", "uplifting", "positive", "optimistic",
            "celebrate", "party", "dance", "fun", "laugh", "smile", "bright"
        }
        
        self.negative_keywords = {
            "sad", "angry", "hate", "terrible", "awful", "bad", "horrible", 
            "depressed", "disappointed", "frustrated", "annoyed", "upset",
            "crying", "tears", "broken", "hurt", "pain", "lonely", "dark",
            "gloomy", "melancholy", "heartbreak", "grief", "sorrow", "down",
            "tired", "exhausted", "stressed", "worried", "anxious", "scared"
        }
        
        self.anger_keywords = {
            "angry", "rage", "furious", "mad", "pissed", "irritated", "annoyed",
            "frustrated", "aggressive", "hostile", "violent", "fight", "argue",
            "hate", "disgusted", "outraged", "livid", "intense", "fierce"
        }
        
        self.fear_keywords = {
            "scared", "afraid", "terrified", "anxious", "worried", "nervous",
            "panic", "fear", "frightened", "overwhelmed", "stressed", "tense",
            "uneasy", "uncomfortable", "insecure", "vulnerable", "helpless"
        }
        
        self.surprise_keywords = {
            "surprised", "shocked", "amazed", "astonished", "wow", "unexpected",
            "sudden", "bizarre", "strange", "weird", "curious", "interesting",
            "unique", "different", "unusual", "remarkable", "extraordinary"
        }
        
        # Energy level indicators
        self.high_energy_keywords = {
            "energetic", "pumped", "hyped", "intense", "explosive", "powerful",
            "dynamic", "electric", "wild", "crazy", "loud", "fast", "rapid",
            "workout", "exercise", "running", "dancing", "party", "club"
        }
        
        self.low_energy_keywords = {
            "calm", "peaceful", "relaxed", "chill", "slow", "quiet", "soft",
            "mellow", "gentle", "soothing", "ambient", "meditation", "sleep",
            "tired", "lazy", "laid-back", "tranquil", "serene", "subtle"
        }
        
        # Musical context keywords
        self.genre_sentiment_mapping = {
            "rock": {"anger": 0.4, "energy": 0.8},
            "metal": {"anger": 0.6, "energy": 0.9},
            "pop": {"joy": 0.6, "energy": 0.7},
            "jazz": {"neutral": 0.6, "energy": 0.4},
            "classical": {"neutral": 0.5, "energy": 0.3},
            "hip hop": {"neutral": 0.4, "energy": 0.7},
            "rap": {"anger": 0.3, "energy": 0.8},
            "blues": {"sadness": 0.7, "energy": 0.3},
            "country": {"neutral": 0.5, "energy": 0.4},
            "electronic": {"neutral": 0.4, "energy": 0.8},
            "edm": {"joy": 0.5, "energy": 0.9},
            "ambient": {"neutral": 0.8, "energy": 0.2},
            "folk": {"neutral": 0.6, "energy": 0.3},
            "reggae": {"joy": 0.4, "energy": 0.5},
            "funk": {"joy": 0.6, "energy": 0.7},
            "soul": {"neutral": 0.5, "energy": 0.5},
            "indie": {"neutral": 0.6, "energy": 0.4},
            "punk": {"anger": 0.5, "energy": 0.9},
            "lofi": {"neutral": 0.7, "energy": 0.2},
            "chill": {"neutral": 0.8, "energy": 0.2}
        }
        
        # Emoji sentiment mapping (expanded)
        self.emoji_sentiments = {
            # Joy/Happiness
            "😊": "joy", "😂": "joy", "😍": "joy", "🥰": "joy", "😄": "joy",
            "😃": "joy", "😁": "joy", "😆": "joy", "🤣": "joy", "😇": "joy",
            "🤩": "joy", "😎": "joy", "🔥": "joy", "💖": "joy", "❤️": "joy",
            "💕": "joy", "💯": "joy", "🎉": "joy", "🎊": "joy", "✨": "joy",
            "🌟": "joy", "⭐": "joy", "🎵": "joy", "🎶": "joy", "🎸": "joy",
            
            # Sadness
            "😢": "sadness", "😭": "sadness", "😔": "sadness", "😞": "sadness",
            "😟": "sadness", "😦": "sadness", "😧": "sadness", "😿": "sadness",
            "💔": "sadness", "🖤": "sadness", "⛈️": "sadness", "🌧️": "sadness",
            
            # Anger
            "😡": "anger", "😠": "anger", "🤬": "anger", "😤": "anger",
            "👿": "anger", "💢": "anger", "🔴": "anger", "💀": "anger",
            
            # Fear/Anxiety
            "😨": "fear", "😰": "fear", "😱": "fear", "😖": "fear",
            "😵": "fear", "🤯": "fear", "💊": "fear", "⚡": "fear",
            
            # Surprise
            "😳": "surprise", "😲": "surprise", "🤯": "surprise", "😵‍💫": "surprise",
            "🤔": "surprise", "🧐": "surprise", "👀": "surprise",
            
            # Neutral
            "😐": "neutral", "😑": "neutral", "🤷": "neutral", "🙂": "neutral",
            "😌": "neutral", "🎧": "neutral", "🎤": "neutral"
        }
    
    async def analyze_sentiment(self, text: str) -> Dict[str, float]:
        """Analyze sentiment using rule-based approach."""
        cleaned_text = self._preprocess_text(text)
        
        if not cleaned_text.strip():
            return {"neutral": 1.0}
        
        # Initialize sentiment scores
        sentiment_scores = {
            "joy": 0.0, "sadness": 0.0, "anger": 0.0, 
            "fear": 0.0, "surprise": 0.0, "neutral": 0.0
        }
        
        text_lower = cleaned_text.lower()
        words = text_lower.split()
        total_weight = 0
        
        # Score based on keywords
        for word in words:
            weight = 1.0
            
            # Check for emphasis (ALL CAPS, exclamation marks)
            if word.isupper() and len(word) > 2:
                weight = 2.0
            
            # Sentiment scoring
            if word in self.positive_keywords:
                sentiment_scores["joy"] += weight
                total_weight += weight
            elif word in self.negative_keywords:
                sentiment_scores["sadness"] += weight
                total_weight += weight
            elif word in self.anger_keywords:
                sentiment_scores["anger"] += weight
                total_weight += weight
            elif word in self.fear_keywords:
                sentiment_scores["fear"] += weight
                total_weight += weight
            elif word in self.surprise_keywords:
                sentiment_scores["surprise"] += weight
                total_weight += weight
        
        # Check for musical genres and adjust sentiment
        genre_influence = self._analyze_genre_context(text_lower)
        for emotion, score in genre_influence.items():
            sentiment_scores[emotion] += score * 2
            total_weight += 2
        
        # Analyze punctuation and emphasis
        punctuation_sentiment = self._analyze_punctuation(text)
        for emotion, score in punctuation_sentiment.items():
            sentiment_scores[emotion] += score
            total_weight += score
        
        # If no sentiment detected, default to neutral
        if total_weight == 0:
            sentiment_scores["neutral"] = 1.0
            total_weight = 1.0
        else:
            # Add small neutral baseline
            sentiment_scores["neutral"] += 0.1
            total_weight += 0.1
        
        # Normalize scores
        normalized_scores = {
            emotion: score / total_weight 
            for emotion, score in sentiment_scores.items()
        }
        
        return normalized_scores
    
    def analyze_emojis(self, text: str) -> Dict[str, float]:
        """Analyze sentiment based on emojis."""
        emojis_found = [char for char in text if char in emoji.EMOJI_DATA]
        
        if not emojis_found:
            return {"neutral": 1.0}
        
        sentiment_counts = {"joy": 0.0, "sadness": 0.0, "anger": 0.0, "fear": 0.0, "surprise": 0.0, "neutral": 0.0}
        
        for emoji_char in emojis_found:
            sentiment = self.emoji_sentiments.get(emoji_char, "neutral")
            sentiment_counts[sentiment] += 1
        
        total = sum(sentiment_counts.values())
        return {
            emotion: count / total for emotion, count in sentiment_counts.items()
        } if total > 0 else {"neutral": 1.0}
    
    def _preprocess_text(self, text: str) -> str:
        """Clean text for analysis."""
        # Remove URLs
        text = re.sub(r'http\S+|www\S+|https\S+', '', text, flags=re.MULTILINE)
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def _analyze_genre_context(self, text: str) -> Dict[str, float]:
        """Analyze musical genre context."""
        genre_scores = {"joy": 0.0, "sadness": 0.0, "anger": 0.0, "fear": 0.0, "surprise": 0.0, "neutral": 0.0}
        
        for genre, sentiment_map in self.genre_sentiment_mapping.items():
            if genre in text:
                for emotion, score in sentiment_map.items():
                    genre_scores[emotion] += score
        
        return genre_scores
    
    def _analyze_punctuation(self, text: str) -> Dict[str, float]:
        """Analyze punctuation for emotional intensity."""
        scores = {"joy": 0.0, "sadness": 0.0, "anger": 0.0, "fear": 0.0, "surprise": 0.0, "neutral": 0.0}
        
        # Count exclamation marks (excitement/intensity)
        exclamation_count = text.count('!')
        if exclamation_count > 0:
            scores["joy"] += exclamation_count * 0.2
            scores["anger"] += exclamation_count * 0.1
        
        # Count question marks (curiosity/surprise)
        question_count = text.count('?')
        if question_count > 0:
            scores["surprise"] += question_count * 0.1
        
        # ALL CAPS detection (intensity/emotion)
        caps_words = re.findall(r'\b[A-Z]{3,}\b', text)
        if caps_words:
            caps_intensity = len(caps_words) * 0.3
            # Distribute caps intensity based on context
            if any(word.lower() in self.positive_keywords for word in caps_words):
                scores["joy"] += caps_intensity
            elif any(word.lower() in self.anger_keywords for word in caps_words):
                scores["anger"] += caps_intensity
            else:
                scores["surprise"] += caps_intensity * 0.5
                scores["joy"] += caps_intensity * 0.3
        
        # Repeated letters (emphasis)
        repeated_letters = re.findall(r'(.)\1{2,}', text.lower())
        if repeated_letters:
            emphasis_score = len(repeated_letters) * 0.1
            scores["joy"] += emphasis_score * 0.6
            scores["surprise"] += emphasis_score * 0.4
        
        return scores
    
    def get_energy_level(self, text: str) -> float:
        """Determine energy level from text (0.0 = low energy, 1.0 = high energy)."""
        text_lower = text.lower()
        
        high_energy_score = sum(1 for word in self.high_energy_keywords if word in text_lower)
        low_energy_score = sum(1 for word in self.low_energy_keywords if word in text_lower)
        
        # Punctuation influence
        exclamation_count = text.count('!')
        caps_words = len(re.findall(r'\b[A-Z]{3,}\b', text))
        
        high_energy_score += exclamation_count * 0.5 + caps_words * 0.3
        
        if high_energy_score + low_energy_score == 0:
            return 0.5  # Default medium energy
        
        energy_ratio = high_energy_score / (high_energy_score + low_energy_score)
        return min(1.0, max(0.0, energy_ratio))
    
    def get_dominant_emotion(self, sentiment_scores: Dict[str, float]) -> str:
        """Get the dominant emotion from sentiment scores."""
        return max(sentiment_scores.items(), key=lambda x: x[1])[0]