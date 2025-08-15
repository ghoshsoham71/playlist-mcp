import asyncio
import os
import logging
from typing import List
from fastmcp import FastMCP
from typing import Optional
from dotenv import load_dotenv
from mcp.types import TextContent
from spotify_handler import SpotifyHandler
from playlist_generator import PlaylistGenerator

# Configure logging
SERVICE_NAME = "SpotifyPlaylistMCP"
logging.basicConfig(
    level=logging.INFO,
    format=f"[%(asctime)s] [{SERVICE_NAME}.%(name)s:%(lineno)d] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logging.getLogger("tekore").setLevel(logging.DEBUG)
logging.getLogger().setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)
load_dotenv()

# Global variables
spotify_handler = None
playlist_generator = None
port = int(os.getenv("PORT", 10000))

def initialize_services():
    """Initialize Spotify handler and playlist generator."""
    global spotify_handler, playlist_generator
    
    try:
        spotify_handler = SpotifyHandler()
        playlist_generator = PlaylistGenerator(spotify_handler)
        logger.info("Services initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        return False

async def health_check() -> List[TextContent]:
    """Health check endpoint."""
    return [TextContent(
        type="text", 
        text=f"MCP Server is healthy and running on port {port}"
    )]

async def validate_config() -> str:
    """Return phone number from environment."""
    return os.getenv('MY_NUMBER', '')

async def authenticate_spotify() -> List[TextContent]:
    """Get Spotify authentication URL."""
    try:
        if not spotify_handler:
            if not initialize_services():
                return [TextContent(
                    type="text",
                    text="Failed to initialize Spotify. Check environment variables."
                )]
        
        if spotify_handler:
            auth_url = spotify_handler.get_auth_url()
            return [TextContent(
                type="text", 
                text=f"""**SPOTIFY AUTHENTICATION REQUIRED**

Click this link to authorize the app:
{auth_url}

After authorization, you'll be redirected back. Then use the 'complete_auth' tool with the authorization code from the URL.

The authorization code will be in the URL after 'code='. For example:
http://127.0.0.1:10000/spotify/callback?code=YOUR_CODE_HERE

Copy the YOUR_CODE_HERE part and use it with the 'complete_auth' tool."""
            )]
        else:
            return [TextContent(
                type="text",
                text="Spotify handler not available"
            )]
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return [TextContent(
            type="text", 
            text=f"Authentication error: {str(e)}"
        )]

async def complete_authentication(auth_code: str) -> List[TextContent]:
    """Complete Spotify authentication with the provided code."""
    try:
        if not spotify_handler:
            return [TextContent(
                type="text",
                text="Spotify handler not initialized. Please try again."
            )]
        
        if spotify_handler.authenticate_with_code(auth_code):
            return [TextContent(
                type="text",
                text="✅ **Authentication successful!** You can now generate playlists."
            )]
        else:
            return [TextContent(
                type="text",
                text="❌ Authentication failed. Please try again with a valid authorization code."
            )]
    except Exception as e:
        logger.error(f"Authentication completion error: {e}")
        return [TextContent(
            type="text",
            text=f"Authentication error: {str(e)}"
        )]

async def fetch_user_data() -> List[TextContent]:
    """Fetch and store user's Spotify data."""
    try:
        if not spotify_handler or not spotify_handler.is_authenticated():
            return [TextContent(
                type="text",
                text="Please authenticate with Spotify first using the 'authenticate' tool."
            )]

        user_data = await spotify_handler.fetch_all_user_data()
        
        summary = f"""**Spotify Data Fetched Successfully!**

**Data Summary:**
- User: {user_data.get('user_profile', {}).get('display_name', 'Unknown')}
- Top Tracks: {len(user_data.get('top_tracks', []))}
- Recent Tracks: {len(user_data.get('recent_tracks', []))}
- Playlists: {len(user_data.get('playlists', []))}

**You can now generate playlists using the 'generate_playlist' tool!**"""

        return [TextContent(type="text", text=summary)]

    except Exception as e:
        logger.error(f"Error fetching user data: {e}")
        return [TextContent(
            type="text",
            text=f"Error fetching user data: {str(e)}"
        )]

async def generate_spotify_playlist(
    prompt: str,
    duration_minutes: int = 60,
    playlist_name: str = "AI Generated Playlist"
) -> List[TextContent]:
    """Generate a Spotify playlist based on prompt."""
    try:
        if not spotify_handler:
            if not initialize_services():
                return [TextContent(
                    type="text",
                    text="Failed to initialize services. Check environment variables."
                )]
        
        if spotify_handler is None or not spotify_handler.is_authenticated():
            return [TextContent(
                type="text",
                text="❌ **Not authenticated with Spotify!**\n\nPlease use the 'authenticate' tool first to connect your Spotify account."
            )]

        if not prompt.strip():
            return [TextContent(
                type="text", 
                text="Please provide a prompt for the playlist."
            )]

        if duration_minutes <= 0 or duration_minutes > 300:
            return [TextContent(
                type="text", 
                text="Duration must be between 1 and 300 minutes."
            )]

        if not playlist_generator:
            return [TextContent(
                type="text",
                text="Playlist generator not available."
            )]

        # Fetch user data if not already done
        try:
            await spotify_handler.fetch_all_user_data()
        except Exception as e:
            logger.warning(f"Could not fetch user data: {e}")

        playlist_url = await playlist_generator.create_playlist(
            prompt=prompt,
            duration_minutes=duration_minutes,
            playlist_name=playlist_name
        )

        return [TextContent(
            type="text",
            text=f"""✅ **Successfully created playlist: '{playlist_name}'**

🎵 **Spotify URL:** {playlist_url}
⏱️ **Duration:** {duration_minutes} minutes
💭 **Prompt:** "{prompt}"

🎉 **Your playlist is ready!** Click the Spotify URL to listen."""
        )]

    except Exception as e:
        logger.error(f"Playlist generation error: {e}")
        return [TextContent(
            type="text", 
            text=f"❌ Error creating playlist: {str(e)}"
        )]

def setup_mcp_server() -> FastMCP:
    """Set up the MCP server with tools."""
    server = FastMCP("spotify-playlist-mcp")
    
    @server.tool("health")
    async def health_tool() -> List[TextContent]:
        """Check if the server is running properly."""
        return await health_check()
    
    @server.tool("validate") 
    async def validate_tool() -> str:
        """Validate configuration."""
        return await validate_config()
    
    @server.tool("authenticate")
    async def authenticate_tool() -> List[TextContent]:
        """Start Spotify authentication process."""
        return await authenticate_spotify()
    
    @server.tool("complete_auth")
    async def complete_auth_tool(auth_code: str) -> List[TextContent]:
        """Complete Spotify authentication with authorization code."""
        return await complete_authentication(auth_code)
    
    @server.tool("fetch_data")
    async def fetch_data_tool() -> List[TextContent]:
        """Fetch user's Spotify data for better recommendations."""
        return await fetch_user_data()
    
    @server.tool("generate_playlist") 
    async def playlist_tool(
        prompt: str,
        duration_minutes: int = 60,
        playlist_name: str = "AI Generated Playlist"
    ) -> List[TextContent]:
        """Generate a Spotify playlist based on a prompt."""
        return await generate_spotify_playlist(prompt, duration_minutes, playlist_name)
    
    return server

async def main():
    """Main entry point."""
    try:
        logger.info(f"Starting Spotify MCP Server on port {port}")
        
        if not initialize_services():
            logger.warning("Service initialization failed - check environment variables")
        
        server = setup_mcp_server()
        await server.run_async("streamable-http", host="0.0.0.0", port=port)
        
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())