#!/usr/bin/env python3
"""
Mood-based Playlist MCP Server
Generates Spotify/Apple Music playlists based on mood, emojis, and language preferences
"""

import asyncio
import logging
import os
import sys
import json
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_env_result = load_dotenv()
logger.info(f"Environment loaded: {load_env_result}")

try:
    from mcp.server.fastmcp import FastMCP
    from mood_analyzer import MoodAnalyzer
    from playlist_generator import PlaylistGenerator
    from config import Config
except ImportError as e:
    logger.error(f"Import error: {e}")
    logger.error("Please install required packages: pip install mcp transformers torch emoji aiohttp python-dotenv")
    sys.exit(1)

# Initialize configuration
config = Config()

# Initialize MCP server (remove host and port - FastMCP handles this differently)
mcp = FastMCP("mood-playlist-server")

# Global components (will be lazily initialized)
mood_analyzer: Optional[MoodAnalyzer] = None
playlist_generator: Optional[PlaylistGenerator] = None
_initialization_lock = asyncio.Lock()
_initialized = False

async def ensure_initialized():
    """Ensure components are initialized (lazy initialization)"""
    global mood_analyzer, playlist_generator, _initialized
    
    if _initialized:
        return True
    
    async with _initialization_lock:
        if _initialized:  # Double-check after acquiring lock
            return True
            
        try:
            logger.info("Initializing server components...")
            
            # Validate configuration
            config.validate()
            
            # Initialize mood analyzer
            mood_analyzer = MoodAnalyzer()
            await mood_analyzer.initialize()
            
            # Ensure API credentials are present
            if not config.lastfm_api_key or not config.lastfm_shared_secret:
                raise ValueError("LASTFM_API_KEY and LASTFM_SHARED_SECRET must be set in the environment or config.")

            # Initialize playlist generator
            playlist_generator = PlaylistGenerator(
                config.lastfm_api_key,
                config.lastfm_shared_secret
            )
            
            _initialized = True
            logger.info("✅ All components initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize components: {str(e)}")
            return False

@mcp.tool()
async def generate_mood_playlist(query: str) -> str:
    """
    Generate a playlist based on user's mood query.
    
    Args:
        query: Natural language query with mood, emojis, duration, and language preferences
        
    Returns:
        JSON string with playlist information
        
    Example: 'I want a 40 minutes playlist of hindi songs that makes me feel 😎'
    """
    try:
        logger.info(f"Processing query: {query}")
        
        # Ensure components are initialized
        success = await ensure_initialized()
        if not success or not mood_analyzer or not playlist_generator:
            return json.dumps({"error": "Server components not initialized properly"}, indent=2)
        
        # Parse and analyze the query
        analysis = await mood_analyzer.analyze_query(query)
        
        # Generate playlist
        playlist = await playlist_generator.generate_playlist(
            mood=analysis['mood'],
            genres=analysis['genres'],
            languages=analysis['languages'],
            duration_minutes=analysis['duration_minutes'],
            energy_level=analysis['energy_level'],
            valence=analysis['valence']
        )
        
        return playlist
        
    except Exception as e:
        logger.error(f"Error generating playlist: {str(e)}")
        return json.dumps({"error": str(e)}, indent=2)

@mcp.tool()
async def get_supported_options() -> str:
    """
    Get list of supported genres and languages for playlist generation.
    
    Returns:
        JSON string with available options including languages, genres, and mood categories
    """
    try:
        success = await ensure_initialized()
        
        if not success or not playlist_generator:
            # Return static options if generator not available
            options = {
                "supported_languages": config.supported_languages,
                "mood_categories": list(config.emotion_genre_map.keys()),
                "popular_genres": config.get_all_genres(),
                "duration_formats": [
                    "30 minutes", "1 hour", "45 minutes", "5 songs", "10 tracks"
                ],
                "example_queries": [
                    "I want a 40 minutes playlist of hindi songs that makes me feel 😎",
                    "Generate a sad english playlist for 1 hour",
                    "Create an energetic punjabi playlist with 10 songs",
                    "I need romantic bollywood music for 30 minutes"
                ]
            }
            return json.dumps(options, indent=2, ensure_ascii=False)
        
        options = await playlist_generator.get_supported_options()
        return options
        
    except Exception as e:
        logger.error(f"Error getting supported options: {str(e)}")
        return json.dumps({"error": str(e)}, indent=2)

@mcp.tool()
async def analyze_mood_only(query: str) -> str:
    """
    Analyze mood and emotions from a query without generating playlist.
    
    Args:
        query: Text query to analyze for mood and emotions
        
    Returns:
        JSON string with mood analysis results
    """
    try:
        logger.info(f"Analyzing mood for query: {query}")
        
        success = await ensure_initialized()
        if not success or not mood_analyzer:
            return json.dumps({"error": "Mood analyzer not initialized"}, indent=2)
        
        analysis = await mood_analyzer.analyze_query(query)
        
        # Return just the analysis without playlist generation
        mood_result = {
            "query": query,
            "analysis": {
                "mood": analysis['mood'],
                "emotion": analysis['emotion'],
                "sentiment": analysis['sentiment'],
                "confidence": analysis['confidence'],
                "energy_level": analysis['energy_level'],
                "valence": analysis['valence'],
                "detected_languages": analysis['languages'],
                "emojis_found": analysis['emojis']
            }
        }
        
        return json.dumps(mood_result, indent=2, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"Error analyzing mood: {str(e)}")
        return json.dumps({"error": str(e)}, indent=2)

def main():
    """Main server entry point"""
    try:
        logger.info("🎵 Starting Mood Playlist MCP Server...")
        
        # Check environment variables before starting
        if not os.getenv("LASTFM_API_KEY") or not os.getenv("LASTFM_SHARED_SECRET"):
            logger.error("❌ Missing Last.fm API credentials!")
            logger.error("Please set LASTFM_API_KEY and LASTFM_SHARED_SECRET environment variables")
            logger.error("You can get these from: https://www.last.fm/api")
            sys.exit(1)

        logger.info("🎵 Mood Playlist MCP Server is ready!")
        logger.info("📝 Available tools:")
        logger.info("  - generate_mood_playlist: Create playlists from mood queries")
        logger.info("  - get_supported_options: List available genres and languages")
        logger.info("  - analyze_mood_only: Analyze mood without generating playlist")
        
        # Start the FastMCP server (components will be initialized on first use)
        mcp.run()
        
    except KeyboardInterrupt:
        logger.info("🛑 Server stopped by user")
    except Exception as e:
        logger.error(f"❌ Server error: {str(e)}")
        sys.exit(1)
    finally:
        # Cleanup
        async def cleanup():
            global playlist_generator
            if playlist_generator:
                await playlist_generator.close()
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(cleanup())
        except:
            pass

if __name__ == "__main__":
    main()