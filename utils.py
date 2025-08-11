import re
from typing import Optional, Dict, Any
from langdetect import detect, DetectorFactory

# Set seed for consistent language detection
DetectorFactory.seed = 0

def parse_duration(text: str) -> Optional[int]:
    """
    Parse duration from text in minutes.
    
    Args:
        text: Input text that might contain duration information
        
    Returns:
        Duration in minutes or None if not found
    """
    text_lower = text.lower()
    
    # Look for explicit duration patterns
    duration_patterns = [
        (r'(\d+)\s*hour[s]?', 60),          # "2 hours" -> 120 minutes
        (r'(\d+)\s*hr[s]?', 60),            # "2 hrs" -> 120 minutes
        (r'(\d+)\s*minute[s]?', 1),         # "30 minutes" -> 30 minutes
        (r'(\d+)\s*min[s]?', 1),            # "30 mins" -> 30 minutes
        (r'(\d+)\s*m(?!\w)', 1),            # "30m" -> 30 minutes
    ]
    
    for pattern, multiplier in duration_patterns:
        match = re.search(pattern, text_lower)
        if match:
            return int(match.group(1)) * multiplier
    
    # Look for contextual duration hints
    duration_hints = {
        "short": 20,
        "quick": 15,
        "brief": 10,
        "long": 90,
        "extended": 120,
        "marathon": 180,
        "workout": 45,
        "commute": 30,
        "study": 60,
        "party": 120,
        "background": 90
    }
    
    for hint, duration in duration_hints.items():
        if hint in text_lower:
            return duration
    
    return None

def detect_language(text: str) -> str:
    """
    Detect the language of the input text.
    
    Args:
        text: Input text
        
    Returns:
        Language code (e.g., 'en', 'es', 'fr') or 'en' as default
    """
    try:
        # Remove emojis and special characters for better detection
        clean_text = re.sub(r'[^\w\s]', ' ', text)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        if len(clean_text) < 3:
            return 'en'  # Default to English for very short texts
        
        detected_lang = detect(clean_text)
        return detected_lang
    
    except Exception:
        return 'en'  # Default to English if detection fails

def extract_genres_from_text(text: str) -> list:
    """
    Extract potential music genres mentioned in the text.
    
    Args:
        text: Input text
        
    Returns:
        List of detected genres
    """
    text_lower = text.lower()
    
    # Common music genres
    genres = [
        'pop', 'rock', 'hip hop', 'rap', 'jazz', 'classical', 'country',
        'electronic', 'edm', 'house', 'techno', 'folk', 'blues', 'reggae',
        'metal', 'punk', 'indie', 'alternative', 'r&b', 'soul', 'funk',
        'disco', 'ambient', 'chill', 'lofi', 'acoustic', 'latin', 'salsa',
        'reggaeton', 'k-pop', 'j-pop', 'bollywood', 'world', 'experimental'
    ]
    
    detected_genres = []
    for genre in genres:
        if genre in text_lower:
            detected_genres.append(genre)
    
    return detected_genres

def extract_artists_from_text(text: str) -> list:
    """
    Extract potential artist names from text using simple patterns.
    
    Args:
        text: Input text
        
    Returns:
        List of potential artist names
    """
    # Look for patterns like "like [artist]", "by [artist]", "similar to [artist]"
    patterns = [
        r'like\s+([A-Z][a-zA-Z\s]+)',
        r'by\s+([A-Z][a-zA-Z\s]+)',
        r'similar\s+to\s+([A-Z][a-zA-Z\s]+)',
        r'style\s+of\s+([A-Z][a-zA-Z\s]+)',
        r'sounds?\s+like\s+([A-Z][a-zA-Z\s]+)'
    ]
    
    artists = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            # Clean up the match
            artist = match.strip()
            if len(artist) > 1 and len(artist) < 50:  # Reasonable artist name length
                artists.append(artist)
    
    return list(set(artists))  # Remove duplicates

def get_time_of_day_context(text: str) -> str:
    """
    Determine time of day context from text.
    
    Args:
        text: Input text
        
    Returns:
        Time context: 'morning', 'afternoon', 'evening', 'night', or 'any'
    """
    text_lower = text.lower()
    
    time_keywords = {
        'morning': ['morning', 'breakfast', 'wake up', 'sunrise', 'am', 'early'],
        'afternoon': ['afternoon', 'lunch', 'midday', 'noon', 'pm', 'work'],
        'evening': ['evening', 'dinner', 'sunset', 'after work', 'wind down'],
        'night': ['night', 'late', 'sleep', 'bedtime', 'midnight', 'party', 'club']
    }
    
    for time_period, keywords in time_keywords.items():
        if any(keyword in text_lower for keyword in keywords):
            return time_period
    
    return 'any'

def extract_activity_context(text: str) -> str:
    """
    Extract activity context from text.
    
    Args:
        text: Input text
        
    Returns:
        Activity context
    """
    text_lower = text.lower()
    
    activities = {
        'workout': ['workout', 'gym', 'exercise', 'running', 'fitness', 'training'],
        'study': ['study', 'focus', 'concentration', 'work', 'reading', 'learning'],
        'party': ['party', 'celebration', 'dance', 'club', 'fun', 'friends'],
        'relax': ['relax', 'chill', 'calm', 'peaceful', 'meditation', 'unwind'],
        'commute': ['drive', 'car', 'commute', 'travel', 'road trip', 'journey'],
        'cooking': ['cooking', 'kitchen', 'meal prep', 'chef', 'recipes'],
        'cleaning': ['cleaning', 'housework', 'chores', 'organizing']
    }
    
    for activity, keywords in activities.items():
        if any(keyword in text_lower for keyword in keywords):
            return activity
    
    return 'general'

def sanitize_playlist_name(name: str) -> str:
    """
    Sanitize playlist name to remove invalid characters.
    
    Args:
        name: Raw playlist name
        
    Returns:
        Sanitized playlist name
    """
    # Remove or replace invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
    
    # Trim whitespace and limit length
    sanitized = sanitized.strip()[:100]
    
    # Ensure it's not empty
    if not sanitized:
        sanitized = "AI Generated Playlist"
    
    return sanitized

def format_duration(minutes: int) -> str:
    """
    Format duration in a human-readable way.
    
    Args:
        minutes: Duration in minutes
        
    Returns:
        Formatted duration string
    """
    if minutes < 60:
        return f"{minutes} minutes"
    else:
        hours = minutes // 60
        remaining_minutes = minutes % 60
        if remaining_minutes == 0:
            return f"{hours} hour{'s' if hours != 1 else ''}"
        else:
            return f"{hours} hour{'s' if hours != 1 else ''} {remaining_minutes} minutes"

def calculate_playlist_stats(tracks: list) -> Dict[str, Any]:
    """
    Calculate statistics for a playlist.
    
    Args:
        tracks: List of track objects
        
    Returns:
        Dictionary with playlist statistics
    """
    if not tracks:
        return {}
    
    total_duration_ms = sum(track.get('duration_ms', 0) for track in tracks)
    total_duration_minutes = total_duration_ms // (1000 * 60)
    
    # Get unique artists
    artists = set()
    for track in tracks:
        if 'artists' in track:
            for artist in track['artists']:
                artists.add(artist.get('name', ''))
    
    # Get popularity stats
    popularities = [track.get('popularity', 0) for track in tracks if 'popularity' in track]
    avg_popularity = sum(popularities) / len(popularities) if popularities else 0
    
    return {
        'total_tracks': len(tracks),
        'total_duration_minutes': total_duration_minutes,
        'total_duration_formatted': format_duration(total_duration_minutes),
        'unique_artists': len(artists),
        'average_popularity': round(avg_popularity, 1),
        'artist_names': list(artists)[:10]  # First 10 artists
    }