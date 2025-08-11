import re
from typing import Optional
from langdetect import detect, DetectorFactory

# Set seed for consistent language detection
DetectorFactory.seed = 0


def parse_duration(text: str) -> Optional[int]:
    """Parse duration from text in minutes."""
    text_lower = text.lower()
    
    # Explicit duration patterns
    patterns = [
        (r'(\d+)\s*hour[s]?', 60),     # hours
        (r'(\d+)\s*hr[s]?', 60),       # hrs
        (r'(\d+)\s*minute[s]?', 1),    # minutes
        (r'(\d+)\s*min[s]?', 1),       # mins
        (r'(\d+)\s*m(?!\w)', 1),       # m
    ]
    
    for pattern, multiplier in patterns:
        match = re.search(pattern, text_lower)
        if match:
            return int(match.group(1)) * multiplier
    
    # Contextual hints
    hints = {
        "short": 20, "quick": 15, "brief": 10, "long": 90, "extended": 120,
        "marathon": 180, "workout": 45, "commute": 30, "study": 60, 
        "party": 120, "background": 90
    }
    
    for hint, duration in hints.items():
        if hint in text_lower:
            return duration
    
    return None


def detect_language(text: str) -> str:
    """Detect language of text, default to English."""
    try:
        # Clean text for better detection
        clean_text = re.sub(r'[^\w\s]', ' ', text)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        if len(clean_text) < 3:
            return 'en'
        
        return detect(clean_text)
    except Exception:
        return 'en'


def extract_genres_from_text(text: str) -> list:
    """Extract music genres mentioned in text."""
    text_lower = text.lower()
    
    genres = [
        'pop', 'rock', 'hip hop', 'rap', 'jazz', 'classical', 'country',
        'electronic', 'edm', 'house', 'techno', 'folk', 'blues', 'reggae',
        'metal', 'punk', 'indie', 'alternative', 'r&b', 'soul', 'funk',
        'disco', 'ambient', 'chill', 'lofi', 'acoustic', 'latin', 'salsa',
        'reggaeton', 'k-pop', 'j-pop', 'bollywood', 'world', 'experimental'
    ]
    
    return [genre for genre in genres if genre in text_lower]


def sanitize_playlist_name(name: str) -> str:
    """Sanitize playlist name for Spotify."""
    # Remove invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
    sanitized = sanitized.strip()[:100]
    
    return sanitized if sanitized else "AI Generated Playlist"


def format_duration(minutes: int) -> str:
    """Format duration in human-readable format."""
    if minutes < 60:
        return f"{minutes} minutes"
    
    hours = minutes // 60
    remaining = minutes % 60
    
    if remaining == 0:
        return f"{hours} hour{'s' if hours != 1 else ''}"
    else:
        return f"{hours} hour{'s' if hours != 1 else ''} {remaining} minutes"