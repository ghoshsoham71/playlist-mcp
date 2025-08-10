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
import urllib.parse
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

# Skip AI model loading in production to avoid timeouts
SKIP_AI_MODELS = os.getenv("SKIP_AI_MODELS", "false").lower() == "true"

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
    """Ensure components are initialized with timeout protection"""
    global mood_analyzer, playlist_generator, _initialized
    
    if _initialized:
        return True
    
    async with _initialization_lock:
        if _initialized:  # Double-check after acquiring lock
            return True
            
        try:
            logger.info("🎵 Initializing server components...")
            
            # Validate configuration
            config.validate()
            
            # Initialize mood analyzer with timeout protection
            mood_analyzer = MoodAnalyzer()
            
            # Skip AI model loading in production to prevent timeouts
            if SKIP_AI_MODELS:
                logger.info("⚠️ Skipping AI model initialization (SKIP_AI_MODELS=true)")
                logger.info("✅ Using rule-based mood analysis for faster performance")
                mood_analyzer.initialized = False
            else:
                logger.info("🤖 Attempting to load AI models...")
                try:
                    # Add overall timeout for initialization
                    await asyncio.wait_for(mood_analyzer.initialize(), timeout=45.0)
                    if mood_analyzer.initialized:
                        logger.info("✅ AI models loaded successfully")
                    else:
                        logger.info("⚠️ AI models failed to load, using rule-based analysis")
                except asyncio.TimeoutError:
                    logger.warning("⚠️ AI model loading timed out after 45 seconds")
                    logger.info("✅ Falling back to rule-based mood analysis")
                    mood_analyzer.initialized = False
                except Exception as e:
                    logger.warning(f"⚠️ AI model initialization failed: {e}")
                    logger.info("✅ Using rule-based mood analysis")
                    mood_analyzer.initialized = False
            
            # Initialize playlist generator
            assert LASTFM_API_KEY is not None, "LASTFM_API_KEY must not be None"
            assert LASTFM_SHARED_SECRET is not None, "LASTFM_SHARED_SECRET must not be None"
            playlist_generator = PlaylistGenerator(
                LASTFM_API_KEY,
                LASTFM_SHARED_SECRET
            )
            
            _initialized = True
            
            # Log final status
            analysis_type = "AI-enhanced" if (mood_analyzer and mood_analyzer.initialized) else "Rule-based"
            logger.info(f"✅ All components initialized successfully using {analysis_type} analysis")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize components: {str(e)}")
            raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"Initialization failed: {e}"))

# --- Helper function to create individual song links ---
def create_individual_song_links(artist: str, track: str) -> dict:
    """Create individual song search links for each platform"""
    # Clean and encode the search query
    search_query = f"{artist} {track}".strip()
    encoded_query = urllib.parse.quote(search_query)
    
    return {
        "spotify": f"https://open.spotify.com/search/{encoded_query}",
        "apple_music": f"https://music.apple.com/search?term={encoded_query}",
        "youtube": f"https://www.youtube.com/results?search_query={encoded_query}"
    }

# --- Tool: validate (required by Puch) ---
@mcp.tool
async def validate() -> str:
    logger.info(f"📱 Validation check - NUMBER: {os.environ.get('MY_NUMBER')}")
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
        logger.info(f"🎵 Processing query: {query}")
        
        # Ensure components are initialized
        await ensure_initialized()
        if not mood_analyzer or not playlist_generator:
            raise McpError(ErrorData(code=INTERNAL_ERROR, message="Server components not initialized properly"))
        
        # Parse and analyze the query
        analysis = await mood_analyzer.analyze_query(query)
        logger.info(f"📊 Analysis complete: mood={analysis['mood']}, languages={analysis['languages']}")
        
        # Generate playlist
        playlist = await playlist_generator.generate_playlist(
            mood=analysis['mood'],
            genres=analysis['genres'],
            languages=analysis['languages'],
            duration_minutes=analysis['duration_minutes'],
            energy_level=analysis['energy_level'],
            valence=analysis['valence']
        )
        
        logger.info(f"✅ Playlist generated successfully")
        return playlist
        
    except Exception as e:
        logger.error(f"❌ Error generating playlist: {str(e)}")
        raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"Playlist generation failed: {e}"))

# --- Tool: generate_playlist_with_individual_links ---
GeneratePlaylistWithLinksDescription = RichToolDescription(
    description="Generate a playlist with individual clickable links for each song on Spotify, Apple Music, and YouTube.",
    use_when="Use this when users want direct links to each song rather than generic playlist search links.",
    side_effects="Returns formatted playlist with individual song links for each streaming platform.",
)

@mcp.tool(description=GeneratePlaylistWithLinksDescription.model_dump_json())
async def generate_playlist_with_individual_links(
    query: Annotated[str, Field(description="Natural language query with mood, emojis, duration, and language preferences")]
) -> str:
    """
    Generate a playlist with individual links for each song on multiple platforms.
    
    Example: 'I want a 40 minutes playlist of hindi songs that makes me feel 😎'
    """
    try:
        logger.info(f"🔗 Processing query with individual links: {query}")
        
        # Ensure components are initialized
        await ensure_initialized()
        if not mood_analyzer or not playlist_generator:
            raise McpError(ErrorData(code=INTERNAL_ERROR, message="Server components not initialized properly"))
        
        # Parse and analyze the query
        analysis = await mood_analyzer.analyze_query(query)
        logger.info(f"📊 Analysis complete: mood={analysis['mood']}, languages={analysis['languages']}")
        
        # Generate base playlist data
        playlist_data = await playlist_generator.generate_playlist_data(
            mood=analysis['mood'],
            genres=analysis['genres'],
            languages=analysis['languages'],
            duration_minutes=analysis['duration_minutes'],
            energy_level=analysis['energy_level'],
            valence=analysis['valence']
        )
        
        logger.info(f"🎼 Playlist data generated: {len(playlist_data['tracks'])} tracks")
        
        # Check if we have tracks
        if not playlist_data.get('tracks'):
            return f"❌ Sorry, couldn't find any {analysis['mood']} {' & '.join(analysis['languages'])} songs. Try a different mood or language combination."
        
        # Format with individual links - FORCE PLAIN TEXT OUTPUT
        lang_str = " & ".join(lang.title() for lang in analysis['languages'])
        
        # Create a very simple, direct output that can't be misinterpreted
        output = f"🎵 PLAYLIST: {analysis['mood'].title()} {lang_str} ({len(playlist_data['tracks'])} songs)\n\n"
        
        for i, track in enumerate(playlist_data['tracks'], 1):
            artist = track['artist']
            song = track['track']
            
            # Create individual links
            links = create_individual_song_links(artist, song)
            
            output += f"{i}. {artist} - {song}\n"
            output += f"🎧 Spotify: {links['spotify']}\n"
            output += f"🍎 Apple Music: {links['apple_music']}\n"
            output += f"📺 YouTube: {links['youtube']}\n\n"
        
        # Add analysis at the end
        output += f"📊 ANALYSIS: Mood={analysis['mood']}, Energy={analysis['energy_level']:.1f}, Languages={', '.join(analysis['languages'])}"
        
        logger.info(f"✅ Response generated: {len(output)} characters")
        return output
        
    except Exception as e:
        logger.error(f"❌ Error generating playlist with links: {str(e)}")
        logger.error(f"Exception type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"Playlist with links generation failed: {e}"))
    
# --- Tool: create_song_links ---
CreateSongLinksDescription = RichToolDescription(
    description="Create individual streaming platform links for a specific artist and song.",
    use_when="Use this to generate clickable links for a single song across Spotify, Apple Music, and YouTube.",
    side_effects="Returns formatted links for the specified song on multiple platforms.",
)

@mcp.tool(description=CreateSongLinksDescription.model_dump_json())
async def create_song_links(
    artist: Annotated[str, Field(description="Artist name")],
    song: Annotated[str, Field(description="Song title")]
) -> str:
    """
    Create individual streaming platform links for a specific song.
    
    Args:
        artist: Name of the artist
        song: Title of the song
        
    Returns:
        Formatted string with clickable links for Spotify, Apple Music, and YouTube
    """
    try:
        logger.info(f"🔗 Creating links for: {artist} - {song}")
        links = create_individual_song_links(artist, song)
        
        output = f"🎵 **{artist} - {song}**\n\n"
        output += f"🔗 **Listen on:**\n"
        output += f"• [Spotify]({links['spotify']})\n"
        output += f"• [Apple Music]({links['apple_music']})\n"
        output += f"• [YouTube]({links['youtube']})\n"
        
        return output
        
    except Exception as e:
        logger.error(f"❌ Error creating song links: {str(e)}")
        raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"Song link creation failed: {e}"))

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
        await ensure_initialized()
        
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
                "I need romantic bollywood music for 30 minutes",
                "Make me a happy tamil playlist 😊",
                "Give me some calm meditation music for 20 minutes"
            ],
            "features": {
                "emoji_support": "✅ Detects mood from emojis",
                "multilingual": "✅ Supports 16+ languages",
                "smart_duration": "✅ Parse time/song count automatically",
                "individual_links": "✅ Direct links to each song",
                "mood_analysis": "🤖 AI + Rule-based detection"
            }
        }
        return json.dumps(options, indent=2, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"❌ Error getting supported options: {str(e)}")
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
        logger.info(f"📊 Analyzing mood for query: {query}")
        
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
                "duration_minutes": analysis['duration_minutes'],
                "recommended_genres": analysis['genres'],
                "emojis_found": analysis['emojis']
            },
            "analysis_method": "AI-enhanced" if (mood_analyzer and mood_analyzer.initialized) else "Rule-based"
        }
        
        return json.dumps(mood_result, indent=2, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"❌ Error analyzing mood: {str(e)}")
        raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"Mood analysis failed: {e}"))

# --- Tool: server_health ---
ServerHealthDescription = RichToolDescription(
    description="Check server health and initialization status.",
    use_when="Use this to verify server components are working properly.",
    side_effects="Returns server status and component health information.",
)

@mcp.tool(description=ServerHealthDescription.model_dump_json())
async def server_health() -> str:
    """
    Check server health and component status.
    """
    try:
        health_status = {
            "server_status": "healthy",
            "components": {
                "mood_analyzer": {
                    "initialized": mood_analyzer is not None,
                    "ai_models": mood_analyzer.initialized if mood_analyzer else False,
                    "analysis_type": "AI-enhanced" if (mood_analyzer and mood_analyzer.initialized) else "Rule-based"
                },
                "playlist_generator": {
                    "initialized": playlist_generator is not None,
                    "lastfm_configured": bool(LASTFM_API_KEY and LASTFM_SHARED_SECRET)
                }
            },
            "configuration": {
                "skip_ai_models": SKIP_AI_MODELS,
                "supported_languages": len(config.supported_languages),
                "mood_categories": len(config.emotion_genre_map)
            },
            "environment": {
                "auth_configured": bool(TOKEN),
                "lastfm_configured": bool(LASTFM_API_KEY and LASTFM_SHARED_SECRET)
            }
        }
        
        return json.dumps(health_status, indent=2)
        
    except Exception as e:
        logger.error(f"❌ Error checking server health: {str(e)}")
        return json.dumps({
            "server_status": "error",
            "error": str(e)
        }, indent=2)

# --- Run MCP Server ---
async def main():
    """Main server startup function"""
    print("🎵 Starting Mood Playlist MCP Server...")
    print(f"🌐 Server will run on http://0.0.0.0:8086")
    print(f"🤖 AI Models: {'Disabled' if SKIP_AI_MODELS else 'Enabled'}")
    
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
    logger.info(" - generate_playlist_with_individual_links: Create playlists with individual song links")
    logger.info(" - create_song_links: Generate links for a specific song")
    logger.info(" - get_supported_options: List available genres and languages")
    logger.info(" - analyze_mood_only: Analyze mood without generating playlist")
    logger.info(" - server_health: Check server component status")
    
    try:
        await mcp.run_async("streamable-http", host="0.0.0.0", port=8086)
    except KeyboardInterrupt:
        logger.info("🛑 Server stopped by user")
    except Exception as e:
        logger.error(f"❌ Server error: {str(e)}")
        raise
    finally:
        # Cleanup
        logger.info("🧹 Cleaning up...")
        if playlist_generator:
            try:
                await playlist_generator.close()
                logger.info("✅ Playlist generator closed")
            except Exception as e:
                logger.warning(f"⚠️ Error closing playlist generator: {e}")

if __name__ == "__main__":
    logger.info("🌟 Starting Mood Playlist MCP Server...")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Server shutdown complete.")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        sys.exit(1)
    else:
        logger.info("👋 Server shutdown complete.")