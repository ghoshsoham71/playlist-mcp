import re
import emoji
from typing import Dict, List, Any
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification

class SentimentAnalyzer:
    """Analyzes sentiment using lightweight HuggingFace models."""
    
    def __init__(self):
        # Initialize lightweight sentiment analysis model
        try:
            self.sentiment_pipeline = pipeline(
                "text-classification",
                model="cardiffnlp/twitter-roberta-base-sentiment-latest",
                tokenizer="cardiffnlp/twitter-roberta-base-sentiment-latest",
                device=-1  # Use CPU for simplicity
            )
        except Exception:
            # Fallback to a smaller model
            self.sentiment_pipeline = pipeline(
                "text-classification",
                model="distilbert-base-uncased-finetuned-sst-2-english",
                device=-1
            )
        
        # Emoji sentiment mapping
        self.emoji_sentiments = {
            "😊": "joy", "😂": "joy", "😍": "joy", "🥰": "joy", "😄": "joy",
            "😢": "sadness", "😭": "sadness", "😔": "sadness", "😞": "sadness",
            "😡": "anger", "😠": "anger", "🤬": "anger", "😤": "anger",
            "😨": "fear", "😰": "fear", "😱": "fear", "😳": "surprise",
            "🤔": "neutral", "😐": "neutral", "😑": "neutral"
        }
    
    async def analyze_sentiment(self, text: str) -> Dict[str, float]:
        """
        Analyze sentiment of text using HuggingFace model.
        
        Args:
            text: Input text to analyze
            
        Returns:
            Dict with sentiment scores
        """
        # Clean text
        cleaned_text = self._preprocess_text(text)
        
        if not cleaned_text.strip():
            return {"neutral": 1.0}
        
        try:
            # Get sentiment predictions
            results = self.sentiment_pipeline(cleaned_text)
            
            # Normalize results to our emotion categories
            normalized_scores = self._normalize_sentiment_scores(results)
            
            return normalized_scores
            
        except Exception as e:
            print(f"Sentiment analysis error: {e}")
            return {"neutral": 1.0}
    
    def analyze_emojis(self, text: str) -> Dict[str, float]:
        """
        Analyze sentiment based on emojis in the text.
        
        Args:
            text: Text containing emojis
            
        Returns:
            Dict with emoji-based sentiment scores
        """
        # Extract emojis
        emojis_in_text = [char for char in text if char in emoji.EMOJI_DATA]
        
        if not emojis_in_text:
            return {"neutral": 1.0}
        
        # Count sentiment types
        sentiment_counts = {
            "joy": 0, "sadness": 0, "anger": 0, 
            "fear": 0, "surprise": 0, "neutral": 0
        }
        
        for emoji_char in emojis_in_text:
            sentiment = self.emoji_sentiments.get(emoji_char, "neutral")
            sentiment_counts[sentiment] += 1
        
        # Normalize to probabilities
        total = sum(sentiment_counts.values())
        if total == 0:
            return {"neutral": 1.0}
        
        return {emotion: count/total for emotion, count in sentiment_counts.items()}
    
    def _preprocess_text(self, text: str) -> str:
        """Clean and preprocess text for sentiment analysis."""
        # Remove URLs
        text = re.sub(r'http\S+|www\S+|https\S+', '', text, flags=re.MULTILINE)
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove emojis for text-only analysis (we analyze them separately)
        text = ''.join(char for char in text if char not in emoji.EMOJI_DATA)
        
        return text
    
    def _normalize_sentiment_scores(self, results: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Normalize HuggingFace sentiment results to our emotion categories.
        
        Args:
            results: Results from HuggingFace sentiment pipeline
            
        Returns:
            Normalized sentiment scores
        """
        # Initialize scores
        emotion_scores = {
            "joy": 0.0, "sadness": 0.0, "anger": 0.0,
            "fear": 0.0, "surprise": 0.0, "neutral": 0.0
        }
        
        # Map HuggingFace labels to our emotions
        label_mapping = {
            "POSITIVE": "joy",
            "NEGATIVE": "sadness",
            "NEUTRAL": "neutral",
            "LABEL_0": "sadness",  # DistilBERT negative
            "LABEL_1": "joy",      # DistilBERT positive
            "LABEL_2": "neutral"   # Some models have 3 classes
        }
        
        total_score = 0.0
        
        for result in results:
            label = result.get('label', '').upper()
            score = result.get('score', 0.0)
            
            mapped_emotion = label_mapping.get(label, "neutral")
            emotion_scores[mapped_emotion] += score
            total_score += score
        
        # Normalize scores
        if total_score > 0:
            emotion_scores = {emotion: score/total_score for emotion, score in emotion_scores.items()}
        else:
            emotion_scores["neutral"] = 1.0
        
        return emotion_scores
    
    def analyze_duration_keywords(self, text: str) -> Dict[str, Any]:
        """
        Analyze text for duration and energy level keywords.
        
        Args:
            text: Input text
            
        Returns:
            Dict with duration and energy analysis
        """
        text_lower = text.lower()
        
        # Duration keywords
        duration_keywords = {
            "short": ["short", "quick", "brief", "small"],
            "medium": ["medium", "normal", "regular", "standard"],
            "long": ["long", "extended", "marathon", "all night", "hours"]
        }
        
        # Energy level keywords
        energy_keywords = {
            "low": ["chill", "relax", "calm", "peaceful", "quiet", "mellow"],
            "medium": ["moderate", "casual", "normal", "balanced"],
            "high": ["energetic", "pump up", "intense", "powerful", "hype", "workout"]
        }
        
        # Check for duration hints
        duration_hint = "medium"
        for duration, keywords in duration_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                duration_hint = duration
                break
        
        # Check for energy hints
        energy_hint = "medium"
        for energy, keywords in energy_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                energy_hint = energy
                break
        
        return {
            "duration_hint": duration_hint,
            "energy_hint": energy_hint
        }
    
    def get_mood_descriptors(self, sentiment_scores: Dict[str, float]) -> List[str]:
        """
        Get descriptive mood words based on sentiment scores.
        
        Args:
            sentiment_scores: Sentiment analysis results
            
        Returns:
            List of mood descriptors
        """
        mood_descriptors = {
            "joy": ["upbeat", "happy", "cheerful", "energetic", "positive"],
            "sadness": ["melancholic", "emotional", "reflective", "slow", "contemplative"],
            "anger": ["intense", "aggressive", "powerful", "driving", "bold"],
            "fear": ["dark", "mysterious", "atmospheric", "haunting", "ambient"],
            "surprise": ["unexpected", "unique", "experimental", "eclectic"],
            "neutral": ["balanced", "mainstream", "versatile", "general"]
        }
        
        # Get primary sentiment
        primary_sentiment = max(sentiment_scores.items(), key=lambda x: x[1])[0]
        
        return mood_descriptors.get(primary_sentiment, mood_descriptors["neutral"])