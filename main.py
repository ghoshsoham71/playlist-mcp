#!/usr/bin/env python3
"""
Render-Compatible Mood-based Playlist MCP Server
Fixed for proper deployment on Render.com
"""

import asyncio
from typing import Annotated, Optional
import os
import json
import logging
import sys
import urllib.parse
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

# --- Load environment variables with proper fallbacks ---
try:
    from dotenv import load_dotenv
    load_dotenv()
    logger.info("✅ dotenv loaded")
except ImportError:
    logger.info("⚠️ dotenv not available, using system environment variables")

# Get environment variables with proper type handling
PORT = int(os.environ.get("PORT", "8086"))
TOKEN = os.environ.get("AUTH_TOKEN")
MY_NUMBER: Optional[str] = os.environ.get("MY_NUMBER") 
LASTFM_API_KEY: Optional[str] = os.environ.get("LASTFM_API_KEY")
LASTFM_SHARED_SECRET: Optional[str] = os.environ.get("LASTFM_SHARED_SECRET")

# Skip AI model loading in production to avoid timeouts
SKIP_AI_MODELS_ENV = os.getenv("SKIP_AI_MODELS", "true")
SKIP_AI_MODELS = SKIP_AI_MODELS_ENV.lower() in ("true", "1", "yes")

# Validate required environment variables
if not TOKEN:
    logger.error("❌ AUTH_TOKEN environment variable is required")
    sys.exit(1)
if not MY_NUMBER:
    logger.error("❌ MY_NUMBER environment variable is required")
    sys.exit(1)
if not LASTFM_API_KEY:
    logger.error("❌ LASTFM_API_KEY environment variable is required")
    sys.exit(1)
if not LASTFM_SHARED_SECRET:
    logger.error("❌ LASTFM_SHARED_SECRET environment variable is required")
    sys.exit(1)

logger.info(f"🔑 Environment validated successfully")
logger.info(f"🌐 Server will bind to port: {PORT}")

# --- Auth Provider ---
class SimpleBearerAuthProvider(BearerAuthProvider):
    def __init__(self, token: str):
        k = RSAKeyPair.generate()
        super().__init__(public_key=k.public_key, jwks_uri=None, issuer=None, audience=None)
        self.token = token
        logger.info(f"🔐 Auth provider initialized")

    async def load_access_token(self, token: str) -> Optional[AccessToken]:
        logger.info(f"🔍 Token verification attempt")
        if token == self.token:
            logger.info("✅ Token validation successful")
            return AccessToken(
                token=token,
                client_id="mood-playlist-client",
                scopes=["*"],
                expires_at=None,
            )
        logger.warning("❌ Token validation failed")
        return None

# --- Import components with error handling ---
try:
    from mood_analyzer import MoodAnalyzer
    from playlist_generator import PlaylistGenerator
    from config import Config
    logger.info("✅ All components imported successfully")
except ImportError as e:
    logger.error(f"❌ Failed to import components: {e}")
    sys.exit(1)
    
# --- MCP Server Setup ---
logger.info("🚀 Creating FastMCP server instance...")
mcp = FastMCP(
    "Mood Playlist MCP Server",
    auth=SimpleBearerAuthProvider(TOKEN),
)

# --- Global components ---
mood_analyzer: Optional[MoodAnalyzer] = None
playlist_generator: Optional[PlaylistGenerator] = None
config: Optional[Config] = None
_initialization_lock = asyncio.Lock()
_initialized = False

async def ensure_initialized():
    """Ensure components are initialized"""
    global mood_analyzer, playlist_generator, config, _initialized
    
    if _initialized:
        return True
    
    async with _initialization_lock:
        if _initialized:
            return True
            
        try:
            logger.info("🎵 Initializing server components...")
            
            # Initialize configuration
            config = Config()
            
            # Initialize mood analyzer
            mood_analyzer = MoodAnalyzer()
            
            # Skip AI models for faster startup
            if SKIP_AI_MODELS:
                logger.info("⚠️ Skipping AI model initialization for faster startup")
                mood_analyzer.initialized = False
            else:
                try:
                    await asyncio.wait_for(mood_analyzer.initialize(), timeout=30.0)
                    logger.info("✅ AI models loaded" if mood_analyzer.initialized else "⚠️ Using rule-based analysis")
                except asyncio.TimeoutError:
                    logger.info("⚠️ AI model loading timed out, using rule-based analysis")
                    mood_analyzer.initialized = False
                except Exception as e:
                    logger.info(f"⚠️ AI model loading failed: {e}, using rule-based analysis")
                    mood_analyzer.initialized = False
            
            # Initialize playlist generator
            playlist_generator = PlaylistGenerator(LASTFM_API_KEY, LASTFM_SHARED_SECRET)
            
            _initialized = True
            logger.info("✅ All components initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Initialization failed: {e}")
            return False

# --- Helper functions ---
def create_individual_song_links(artist: str, track: str) -> dict:
    """Create individual song search links for each platform"""
    search_query = f"{artist} {track}".strip()
    encoded_query = urllib.parse.quote(search_query)
    
    return {
        "spotify": f"https://open.spotify.com/search/{encoded_query}",
        "apple_music": f"https://music.apple.com/search?term={encoded_query}",
        "youtube": f"https://www.youtube.com/results?search_query={encoded_query}"
    }

# --- Tools ---

@mcp.tool(
    name="ping",
    description="Simple connectivity test"
)
async def ping() -> str:
    """Test server connectivity"""
    logger.info("🏓 Ping received")
    return "pong - server is running!"

@mcp.tool(
    name="validate", 
    description="Server validation endpoint (required)"
)
async def validate() -> str:
    """Validate server and return number"""
    logger.info(f"📱 Validation requested")
    return MY_NUMBER or "No number configured"

@mcp.tool(
    name="server_health",
    description="Check server health and component status"
)
async def server_health() -> str:
    """Check server health"""
    logger.info("🏥 Health check requested")
    
    health_status = {
        "server_status": "healthy",
        "port": PORT,
        "components": {
            "mood_analyzer": mood_analyzer is not None,
            "playlist_generator": playlist_generator is not None,
            "config": config is not None,
        },
        "environment": {
            "skip_ai_models": SKIP_AI_MODELS,
            "auth_configured": bool(TOKEN),
            "lastfm_configured": bool(LASTFM_API_KEY and LASTFM_SHARED_SECRET)
        },
        "endpoints": [
            f"POST https://playlist-mcp.onrender.com/ (with proper headers)",
            "Authorization: Bearer YOUR_TOKEN_HERE",
            "Content-Type: application/json"
        ]
    }
    
    return json.dumps(health_status, indent=2)

@mcp.tool(
    name="generate_playlist",
    description="Generate a mood-based playlist with individual song links"
)
async def generate_playlist(
    query: Annotated[str, Field(description="Mood query like 'happy hindi songs for 30 minutes' or 'sad english playlist 😢'")]
) -> str:
    """Generate a playlist based on mood query"""
    logger.info(f"🎵 Playlist requested: {query}")
    
    try:
        # Ensure initialization before each request
        init_success = await ensure_initialized()
        if not init_success:
            return json.dumps({
                "error": "Server components failed to initialize",
                "query": query,
                "status": "failed"
            }, indent=2)
        
        if not mood_analyzer or not playlist_generator:
            return json.dumps({
                "error": "Server components not available",
                "query": query,
                "status": "failed"
            }, indent=2)
        
        # Analyze the query
        analysis = await mood_analyzer.analyze_query(query)
        logger.info(f"📊 Analysis: mood={analysis['mood']}, languages={analysis['languages']}")
        
        # Ensure session is available for playlist generator
        if not playlist_generator.session or playlist_generator.session.closed:
            playlist_generator.session = None  # Will be recreated in _make_request
        
        # Generate playlist data with timeout
        playlist_data = await asyncio.wait_for(
            playlist_generator.generate_playlist_data(
                mood=analysis['mood'],
                genres=analysis['genres'],
                languages=analysis['languages'],
                duration_minutes=analysis['duration_minutes'],
                energy_level=analysis['energy_level'],
                valence=analysis['valence']
            ),
            timeout=60.0  # 60 second timeout for playlist generation
        )
        
        if not playlist_data.get('tracks'):
            return f"❌ Sorry, couldn't find any {analysis['mood']} {' & '.join(analysis['languages'])} songs. Try a different mood or language."
        
        # Format response
        lang_str = " & ".join(lang.title() for lang in analysis['languages'])
        output = f"🎵 {analysis['mood'].title()} {lang_str} Playlist ({len(playlist_data['tracks'])} songs)\n\n"
        
        for i, track in enumerate(playlist_data['tracks'], 1):
            artist = track['artist']
            song = track['track']
            links = create_individual_song_links(artist, song)
            
            output += f"{i}. {artist} - {song}\n"
            output += f"   🎧 Spotify: {links['spotify']}\n"
            output += f"   🍎 Apple Music: {links['apple_music']}\n"
            output += f"   📺 YouTube: {links['youtube']}\n\n"
        
        output += f"📊 Analysis: Mood={analysis['mood']}, Energy={analysis['energy_level']:.1f}, Languages={', '.join(analysis['languages'])}"
        
        logger.info(f"✅ Playlist generated successfully")
        return output
        
    except asyncio.TimeoutError:
        logger.error("❌ Playlist generation timed out")
        return json.dumps({
            "error": "Playlist generation timed out. Please try again.",
            "query": query,
            "status": "timeout"
        }, indent=2)
    except Exception as e:
        logger.error(f"❌ Playlist generation failed: {e}")
        return json.dumps({
            "error": str(e),
            "query": query,
            "status": "failed"
        }, indent=2)

@mcp.tool(
    name="get_supported_options",
    description="Get available languages, moods, and example queries"
)
async def get_supported_options() -> str:
    """Get supported options and examples"""
    logger.info("📋 Options requested")
    
    # Initialize config if not already done
    if not config:
        await ensure_initialized()
    
    # Use fallback values if config is still not available
    supported_languages = getattr(config, 'supported_languages', [
        "hindi", "english", "punjabi", "bengali", "tamil", "telugu", 
        "marathi", "gujarati", "kannada", "malayalam", "spanish", 
        "french", "german", "italian", "japanese", "korean"
    ])
    
    emotion_genre_map = getattr(config, 'emotion_genre_map', {
        "happy": ["pop", "dance", "bollywood", "reggae", "funk"],
        "sad": ["ballad", "blues", "indie", "melancholic", "ghazal"],
        "angry": ["rock", "metal", "punk", "rap", "aggressive"],
        "excited": ["electronic", "dance", "pop", "party", "energetic"],
        "calm": ["ambient", "classical", "instrumental", "chill", "meditation"],
        "romantic": ["romantic", "love songs", "r&b", "slow", "ballad"],
        "nostalgic": ["retro", "oldies", "vintage", "classic", "throwback"],
        "energetic": ["workout", "high energy", "dance", "electronic", "upbeat"],
        "neutral": ["pop", "alternative", "indie"]
    })
    
    options = {
        "supported_languages": supported_languages,
        "mood_categories": list(emotion_genre_map.keys()),
        "example_queries": [
            "I want happy hindi songs for 30 minutes 😊",
            "Generate sad english playlist for 1 hour",
            "Create energetic punjabi songs",
            "Romantic bollywood music 💕",
            "Calm meditation music for 20 minutes"
        ],
        "usage_tips": [
            "Include emojis to express mood better",
            "Specify duration (minutes/hours) or number of songs",
            "Mention language preferences (hindi, english, etc.)",
            "Use descriptive mood words (happy, sad, energetic, romantic, calm)"
        ]
    }
    
    return json.dumps(options, indent=2, ensure_ascii=False)

# --- Server startup ---
async def main():
    """Main server function"""
    logger.info("🎵 Starting Mood Playlist MCP Server...")
    logger.info(f"🌐 Server will run on 0.0.0.0:{PORT}")
    logger.info(f"🚀 Public URL: https://playlist-mcp.onrender.com")
    logger.info(f"🤖 AI Models: {'Disabled' if SKIP_AI_MODELS else 'Enabled'}")
    
    # Pre-initialize components
    try:
        await ensure_initialized()
        logger.info("✅ Pre-initialization completed")
    except Exception as e:
        logger.warning(f"⚠️ Pre-initialization failed: {e}")
    
    logger.info("📝 Available tools: ping, validate, server_health, generate_playlist, get_supported_options")
    logger.info("🔗 Test with: curl -X POST https://playlist-mcp.onrender.com/ -H 'Content-Type: application/json' -H 'Authorization: Bearer YOUR_TOKEN' -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\"}'")
    
    try:
        # Use 0.0.0.0 to bind to all interfaces (required for Render)
        await mcp.run_async("streamable-http", host="0.0.0.0", port=PORT)
    except Exception as e:
        logger.error(f"❌ Server failed to start: {e}")
        raise

# --- Cleanup handlers ---
async def cleanup():
    """Cleanup resources on shutdown"""
    global playlist_generator
    if playlist_generator:
        try:
            await playlist_generator.close()
            logger.info("✅ Playlist generator cleaned up")
        except Exception as e:
            logger.warning(f"⚠️ Cleanup warning: {e}")

def signal_handler():
    """Handle shutdown signals"""
    logger.info("🛑 Shutdown signal received")
    asyncio.create_task(cleanup())

if __name__ == "__main__":
    logger.info("🌟 Starting Mood Playlist MCP Server...")
    try:
        # Register cleanup for proper shutdown
        import signal
        
        signal.signal(signal.SIGTERM, lambda s, f: signal_handler())
        signal.signal(signal.SIGINT, lambda s, f: signal_handler())
        
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Server shutdown by user")
        asyncio.run(cleanup())
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        asyncio.run(cleanup())
        sys.exit(1)