#!/usr/bin/env python3
"""
Mood-based Playlist MCP Server
Generates Spotify/Apple Music playlists based on mood, emojis, and language preferences
"""

import asyncio
from typing import Annotated
import os
import json
import logging
import sys
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth.providers.bearer import BearerAuthProvider, RSAKeyPair
from mcp import ErrorData, McpError
from mcp.server.auth.provider import AccessToken
from mcp.types import TextContent, INVALID_PARAMS, INTERNAL_ERROR
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Load environment variables ---
load_dotenv()

TOKEN = os.environ.get("AUTH_TOKEN")
MY_NUMBER = os.environ.get("MY_NUMBER")
LASTFM_API_KEY = os.environ.get("LASTFM_API_KEY")
LASTFM_SHARED_SECRET = os.environ.get("LASTFM_SHARED_SECRET")

assert TOKEN is not None, "Please set AUTH_TOKEN in your .env file"
assert MY_NUMBER is not None, "Please set MY_NUMBER in your .env file"
assert LASTFM_API_KEY is not None, "Please set LASTFM_API_KEY in your .env file"
assert LASTFM_SHARED_SECRET is not None, "Please set LASTFM_SHARED_SECRET in your .env file"

# --- Auth Provider ---
class SimpleBearerAuthProvider(BearerAuthProvider):
    def __init__(self, token: str):
        k = RSAKeyPair.generate()
        super().__init__(public_key=k.public_key, jwks_uri=None, issuer=None, audience=None)
        self.token = token

    async def load_access_token(self, token: str) -> AccessToken | None:
        if token == self.token:
            return AccessToken(
                token=token,
                client_id="mood-playlist-client",
                scopes=["*"],
                expires_at=None,
            )
        return None

# --- Rich Tool Description model ---
class RichToolDescription(BaseModel):
    description: str
    use_when: str
    side_effects: str | None = None

# --- Import mood analysis components ---
try:
    from mood_analyzer import MoodAnalyzer
    from playlist_generator import PlaylistGenerator
    from config import Config
except ImportError as e:
    logger.error(f"Import error: {e}")
    logger.error("Please install required packages: pip install mcp transformers torch emoji aiohttp python-dotenv")
    sys.exit(1)

# --- Initialize configuration ---
config = Config()

# --- MCP Server Setup ---
mcp = FastMCP(
    "Mood Playlist MCP Server",
    auth=SimpleBearerAuthProvider(TOKEN),
)

# --- Global components (lazy initialization) ---
mood_analyzer: MoodAnalyzer | None = None
playlist_generator: PlaylistGenerator | None = None
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
            
            # Initialize playlist generator
            assert LASTFM_API_KEY is not None, "LASTFM_API_KEY must not be None"
            assert LASTFM_SHARED_SECRET is not None, "LASTFM_SHARED_SECRET must not be None"
            playlist_generator = PlaylistGenerator(
                LASTFM_API_KEY,
                LASTFM_SHARED_SECRET
            )
            
            _initialized = True
            logger.info("✅ All components initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize components: {str(e)}")
            raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"Initialization failed: {e}"))

# --- Tool: validate (required by Puch) ---
@mcp.tool
async def validate() -> str:
    logger.info(f"NUMBER: {os.environ.get("MY_NUMBER")}")
    return os.environ.get("MY_NUMBER") or ""

# --- Tool: generate_mood_playlist ---
GenerateMoodPlaylistDescription = RichToolDescription(
    description="Generate a playlist based on user's mood query with natural language processing.",
    use_when="Use this to create playlists from mood descriptions, emojis, duration, and language preferences.",
    side_effects="Returns JSON with playlist information including tracks, mood analysis, and metadata.",
)

@mcp.tool(description=GenerateMoodPlaylistDescription.model_dump_json())
async def generate_mood_playlist(
    query: Annotated[str, Field(description="Natural language query with mood, emojis, duration, and language preferences")]
) -> str:
    """
    Generate a playlist based on user's mood query.
    
    Example: 'I want a 40 minutes playlist of hindi songs that makes me feel 😎'
    """
    try:
        logger.info(f"Processing query: {query}")
        
        # Ensure components are initialized
        await ensure_initialized()
        if not mood_analyzer or not playlist_generator:
            raise McpError(ErrorData(code=INTERNAL_ERROR, message="Server components not initialized properly"))
        
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
        raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"Playlist generation failed: {e}"))

# --- Tool: get_supported_options ---
GetSupportedOptionsDescription = RichToolDescription(
    description="Get list of supported genres and languages for playlist generation.",
    use_when="Use this to discover available options including languages, genres, and mood categories.",
    side_effects="Returns comprehensive list of supported playlist generation options.",
)

@mcp.tool(description=GetSupportedOptionsDescription.model_dump_json())
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
        raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"Failed to get options: {e}"))

# --- Tool: analyze_mood_only ---
AnalyzeMoodOnlyDescription = RichToolDescription(
    description="Analyze mood and emotions from a query without generating playlist.",
    use_when="Use this to understand mood, sentiment, and emotional content of text queries.",
    side_effects="Returns detailed mood analysis including confidence scores and detected emotions.",
)

@mcp.tool(description=AnalyzeMoodOnlyDescription.model_dump_json())
async def analyze_mood_only(
    query: Annotated[str, Field(description="Text query to analyze for mood and emotions")]
) -> str:
    """
    Analyze mood and emotions from a query without generating playlist.
    """
    try:
        logger.info(f"Analyzing mood for query: {query}")
        
        await ensure_initialized()
        if not mood_analyzer:
            raise McpError(ErrorData(code=INTERNAL_ERROR, message="Mood analyzer not initialized"))
        
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
        raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"Mood analysis failed: {e}"))

# --- Run MCP Server ---
async def main():
    print("🎵 Starting Mood Playlist MCP Server on http://0.0.0.0:8086")
    
    # Check environment variables before starting
    if not LASTFM_API_KEY or not LASTFM_SHARED_SECRET:
        logger.error("❌ Missing Last.fm API credentials!")
        logger.error("Please set LASTFM_API_KEY and LASTFM_SHARED_SECRET environment variables")
        logger.error("You can get these from: https://www.last.fm/api")
        sys.exit(1)

    logger.info("🎵 Mood Playlist MCP Server is ready!")
    logger.info("📝 Available tools:")
    logger.info(" - validate: Server validation (required)")
    logger.info(" - generate_mood_playlist: Create playlists from mood queries")
    logger.info(" - get_supported_options: List available genres and languages")
    logger.info(" - analyze_mood_only: Analyze mood without generating playlist")
    
    try:
        await mcp.run_async("streamable-http", host="0.0.0.0", port=8086)
    except KeyboardInterrupt:
        logger.info("🛑 Server stopped by user")
    except Exception as e:
        logger.error(f"❌ Server error: {str(e)}")
        raise
    finally:
        # Cleanup
        if playlist_generator:
            await playlist_generator.close()

if __name__ == "__main__":
    logger.info("🌟 Starting Mood Playlist MCP Server...")
    asyncio.run(main())
    logger.info("🌟 Server shutdown complete.")
