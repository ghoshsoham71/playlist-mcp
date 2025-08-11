import asyncio
import json
import os
from typing import Dict, Any, Optional

import tekore as tk
from fastmcp import FastMCP
from mcp.types import TextContent

from playlist_generator import PlaylistGenerator
from sentiment_analyzer import SentimentAnalyzer
from utils import parse_duration, detect_language


# Global variables to maintain state
client: Optional[tk.Spotify] = None
token: Optional[tk.Token] = None
playlist_generator: Optional[PlaylistGenerator] = None
sentiment_analyzer = SentimentAnalyzer()
cred: Optional[tk.Credentials] = None
scope: Optional[tk.Scope] = None
port = int(os.getenv("PORT", 8086))


def initialize_credentials():
    """Initialize Spotify credentials and scope."""
    global cred, scope
    
    redirect_uri = os.getenv(
        "SPOTIFY_REDIRECT_URI", 
        f"http://localhost:{port}/callback",
    )
    
    cred = tk.Credentials(
        client_id=os.getenv("SPOTIFY_CLIENT_ID", ''),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET", ''),
        redirect_uri=redirect_uri
    )
    
    scope = (
        tk.scope.playlist_modify_public + tk.scope.playlist_modify_private +
        tk.scope.user_read_recently_played + tk.scope.user_top_read +
        tk.scope.user_library_read + tk.scope.user_read_private
    )


async def health_check() -> list[TextContent]:
    """Health check endpoint to verify server is running."""
    return [TextContent(
        type="text", 
        text=f"✅ MCP Server is healthy and running on port {port}"
    )]


async def validate_config() -> str:
    """Validate server configuration."""
    my_number = os.getenv('MY_NUMBER', '') 
    return my_number


async def authenticate_spotify() -> list[TextContent]:
    """Generate authentication URL for Spotify."""
    try:
        if cred is None:
            return [TextContent(
                type="text",
                text="❌ Credentials not initialized. Please restart the server."
            )]
            
        if not cred.client_id or not cred.client_secret:
            return [TextContent(
                type="text",
                text="❌ Spotify credentials not configured. Please set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables."
            )]
        
        if scope is None:
            return [TextContent(
                type="text",
                text="❌ Scope not initialized. Please restart the server."
            )]
        
        auth_url = cred.user_authorisation_url(scope=scope)
        return [TextContent(
            type="text", 
            text=f"🔗 Please authenticate with Spotify:\n{auth_url}\n\n"
                 f"After authorization, you'll be redirected to:\n{cred.redirect_uri}\n\n"
                 f"Copy the 'code' parameter from the redirect URL and use it with the 'handle_callback' tool."
        )]
    except Exception as e:
        return [TextContent(
            type="text", 
            text=f"❌ Error generating authentication URL: {str(e)}"
        )]


async def handle_spotify_callback(code: str) -> list[TextContent]:
    """Handle Spotify OAuth callback."""
    global client, token, playlist_generator
    
    try:
        if not code:
            return [TextContent(
                type="text", 
                text="❌ No authorization code provided. Please provide the 'code' parameter from the Spotify redirect URL."
            )]
        
        if cred is None:
            return [TextContent(
                type="text",
                text="❌ Credentials not initialized. Please restart the server."
            )]
        
        token = cred.request_user_token(code)
        if token:
            client = tk.Spotify(token)
            playlist_generator = PlaylistGenerator(client)
            
            # Test connection
            user = client.current_user()
            return [TextContent(
                type="text", 
                text=f"✅ Successfully authenticated as {user.display_name or user.id}!\n"
                     f"🎵 You can now generate playlists using the 'generate_playlist' tool."
            )]
        else:
            return [TextContent(
                type="text", 
                text="❌ Authentication failed: Could not retrieve token. Please try again with a fresh authorization code."
            )]
    except Exception as e:
        return [TextContent(
            type="text", 
            text=f"❌ Authentication failed: {str(e)}\n"
                 f"💡 Make sure to use a fresh authorization code from Spotify."
        )]


async def analyze_prompt(prompt: str) -> Dict[str, Any]:
    """Analyze user prompt for sentiment and context."""
    try:
        sentiment_scores = await sentiment_analyzer.analyze_sentiment(prompt)
        language = detect_language(prompt)
        parsed_duration = parse_duration(prompt)
        emoji_sentiment = sentiment_analyzer.analyze_emojis(prompt)

        return {
            "sentiment": sentiment_scores,
            "language": language,
            "duration_hint": parsed_duration,
            "emoji_sentiment": emoji_sentiment,
            "raw_prompt": prompt,
        }
    except Exception as e:
        # Return basic analysis if sentiment analyzer fails
        return {
            "sentiment": {"error": str(e)},
            "language": "unknown",
            "duration_hint": None,
            "emoji_sentiment": None,
            "raw_prompt": prompt,
        }


async def generate_spotify_playlist(
    prompt: str,
    duration_minutes: int = 60,
    playlist_name: str = "AI Generated Playlist",
) -> list[TextContent]:
    """Generate a Spotify playlist based on text prompt and sentiment analysis."""
    global client, token, playlist_generator
    
    try:
        # Validate inputs
        if not prompt or not prompt.strip():
            return [TextContent(
                type="text", 
                text="❌ Please provide a prompt to generate the playlist."
            )]
        
        if duration_minutes <= 0 or duration_minutes > 600:  # Max 10 hours
            return [TextContent(
                type="text", 
                text="❌ Duration must be between 1 and 600 minutes."
            )]
        
        if not client or not playlist_generator:
            return [TextContent(
                type="text", 
                text="❌ Please authenticate with Spotify first using the 'authenticate' and 'handle_callback' tools."
            )]

        # Refresh token if needed
        if token and token.is_expiring and token.refresh_token and cred is not None:
            try:
                token = cred.refresh_user_token(token.refresh_token)
                client = tk.Spotify(token)
                playlist_generator.client = client
            except Exception as refresh_error:
                return [TextContent(
                    type="text",
                    text=f"❌ Token refresh failed: {str(refresh_error)}. Please re-authenticate using the 'authenticate' tool."
                )]

        # Analyze prompt
        analysis_result = await analyze_prompt(prompt)

        # Create playlist
        playlist_url = await playlist_generator.create_playlist(
            analysis_result=analysis_result,
            duration_minutes=duration_minutes,
            playlist_name=playlist_name,
        )

        return [TextContent(
            type="text",
            text=f"✅ Successfully created playlist: '{playlist_name}'\n"
                 f"🎵 Spotify URL: {playlist_url}\n"
                 f"⏱️ Duration: {duration_minutes} minutes\n"
                 f"📊 Prompt Analysis:\n{json.dumps(analysis_result, indent=2)}",
        )]
    except Exception as e:
        return [TextContent(
            type="text", 
            text=f"❌ Error creating playlist: {str(e)}\n"
                 f"💡 If this is an authentication error, try re-authenticating with Spotify."
        )]


async def list_available_tools() -> list[TextContent]:
    """List all available tools and their descriptions."""
    tools_info = """
🛠️ Available Tools:

1. **health** - Check if the MCP server is running
2. **validate** - Validate server configuration and credentials
3. **authenticate** - Get Spotify authentication URL
4. **handle_callback** - Process Spotify OAuth callback with authorization code
5. **generate_playlist** - Create playlists based on text prompts (requires authentication)
6. **list_tools** - Show this help information

📋 Typical Usage Flow:
1. Run `validate` to check configuration
2. Run `authenticate` to get Spotify auth URL
3. Visit the URL and authorize the app
4. Run `handle_callback` with the code from redirect URL
5. Run `generate_playlist` with your desired prompt

💡 All tools return structured responses and handle errors gracefully.
    """
    return [TextContent(type="text", text=tools_info.strip())]


def setup_mcp_server() -> FastMCP:
    """Set up the FastMCP server with all tools."""
    server = FastMCP("tekore-playlist-generator")
    
    # Register tools without decorators
    server.tool("health")(health_check)
    server.tool("validate")(validate_config)
    server.tool("authenticate")(authenticate_spotify)
    server.tool("handle_callback")(handle_spotify_callback)
    server.tool("generate_playlist")(generate_spotify_playlist)
    server.tool("list_tools")(list_available_tools)
    
    return server


async def run_server() -> None:
    """Run the MCP server."""
    try:
        # Initialize credentials first
        initialize_credentials()
        
        # Setup server
        server = setup_mcp_server()
        
        print(f"🚀 Starting Tekore Playlist MCP Server on port {port}")
        print(f"🔗 MCP endpoint: http://0.0.0.0:{port}/mcp/")
        
        if cred is not None:
            print(f"🎵 Spotify redirect URI: {cred.redirect_uri}")
        
        await server.run_async("streamable-http", host="0.0.0.0", port=port)
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        raise


async def main() -> None:
    """Main entry point."""
    try:
        await run_server()
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"❌ Server error: {e}")
        raise


# Direct tool access functions for external use
async def call_health_check():
    """Direct call to health check tool."""
    return await health_check()


async def call_validate():
    """Direct call to validate tool."""
    return await validate_config()


async def call_authenticate():
    """Direct call to authenticate tool."""
    initialize_credentials()  # Ensure credentials are initialized
    return await authenticate_spotify()


async def call_handle_callback(code: str):
    """Direct call to handle callback tool."""
    initialize_credentials()  # Ensure credentials are initialized
    return await handle_spotify_callback(code)


async def call_generate_playlist(prompt: str, duration_minutes: int = 60, playlist_name: str = "AI Generated Playlist"):
    """Direct call to generate playlist tool."""
    return await generate_spotify_playlist(prompt, duration_minutes, playlist_name)


async def call_list_tools():
    """Direct call to list tools."""
    return await list_available_tools()


if __name__ == "__main__":
    asyncio.run(main())