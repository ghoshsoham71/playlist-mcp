import re
import emoji
from typing import Dict, List, Any
from transformers import pipeline


class SentimentAnalyzer:
    """Analyzes sentiment using lightweight HuggingFace models."""
    
    def __init__(self):
        # Initialize sentiment analysis model with fallback
        try:
            self.pipeline = pipeline(
                "text-classification",
                model="cardiffnlp/twitter-roberta-base-sentiment-latest",
                device=-1  # CPU
            )
        except Exception:
            self.pipeline = pipeline(
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
        """Analyze sentiment of text."""
        cleaned_text = self._preprocess_text(text)
        
        if not cleaned_text.strip():
            return {"neutral": 1.0}
        
        try:
            results = self.pipeline(cleaned_text)
            return self._normalize_scores(results)
        except Exception as e:
            print(f"Sentiment analysis error: {e}")
            return {"neutral": 1.0}
    
    def analyze_emojis(self, text: str) -> Dict[str, float]:
        """Analyze sentiment based on emojis."""
        emojis_found = [char for char in text if char in emoji.EMOJI_DATA]
        
        if not emojis_found:
            return {"neutral": 1.0}
        
        sentiment_counts = {"joy": 0, "sadness": 0, "anger": 0, "fear": 0, "surprise": 0, "neutral": 0}
        
        for emoji_char in emojis_found:
            sentiment = self.emoji_sentiments.get(emoji_char, "neutral")
            sentiment_counts[sentiment] += 1
        
        total = sum(sentiment_counts.values())
        return {emotion: count/total for emotion, count in sentiment_counts.items()} if total > 0 else {"neutral": 1.0}
    
    def _preprocess_text(self, text: str) -> str:
        """Clean text for analysis."""
        # Remove URLs and excessive whitespace
        text = re.sub(r'http\S+|www\S+|https\S+', '', text, flags=re.MULTILINE)
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove emojis for text-only analysis
        text = ''.join(char for char in text if char not in emoji.EMOJI_DATA)
        
        return text
    
    def _normalize_scores(self, results: List[Dict[str, Any]]) -> Dict[str, float]:
        """Normalize HuggingFace results to emotion categories."""
        emotion_scores = {"joy": 0.0, "sadness": 0.0, "anger": 0.0, "fear": 0.0, "surprise": 0.0, "neutral": 0.0}
        
        # Map HuggingFace labels to emotions
        label_mapping = {
            "POSITIVE": "joy", "NEGATIVE": "sadness", "NEUTRAL": "neutral",
            "LABEL_0": "sadness", "LABEL_1": "joy", "LABEL_2": "neutral"
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
            return {emotion: score/total_score for emotion, score in emotion_scores.items()}
        else:
            return {"neutral": 1.0}