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
port = int(os.getenv("PORT", 10000))


def initialize_credentials():
    """Initialize Spotify credentials and scope."""
    global cred, scope
    
    # Use environment variable or construct based on deployment
    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI")
    if not redirect_uri:
        # For local development
        if os.getenv("RENDER"):
            # Running on Render - use the Render URL
            redirect_uri = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME', 'playlist-mcp.onrender.com')}/callback"
        else:
            # Local development
            redirect_uri = f"http://127.0.0.1:{port}/callback"
    
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
                 f"Look for the 'code' parameter in the redirect URL and copy its value. Then use it with the 'handle_callback' tool."
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
            "sentiment": {"neutral": 1.0, "error": str(e)},
            "language": "en",  # Default to English
            "duration_hint": None,
            "emoji_sentiment": {"neutral": 1.0},
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

        # Create playlist with better error handling
        try:
            playlist_url = await playlist_generator.create_playlist(
                analysis_result=analysis_result,
                duration_minutes=duration_minutes,
                playlist_name=playlist_name,
            )
            
            # Format analysis result for display (remove error details)
            display_analysis = {k: v for k, v in analysis_result.items() if k != 'error'}
            
            return [TextContent(
                type="text",
                text=f"✅ Successfully created playlist: '{playlist_name}'\n"
                     f"🎵 Spotify URL: {playlist_url}\n"
                     f"⏱️ Duration: {duration_minutes} minutes\n"
                     f"🌍 Language: {analysis_result.get('language', 'unknown')}\n"
                     f"📊 Detected sentiment: {max(analysis_result.get('sentiment', {'neutral': 1.0}).items(), key=lambda x: x[1])[0]}\n"
                     f"📈 Analysis details:\n{json.dumps(display_analysis, indent=2)}",
            )]
            
        except tk.HTTPError as http_error:
            return [TextContent(
                type="text",
                text=f"❌ Spotify API error: {http_error}\n"
                     f"💡 This might be due to rate limiting or insufficient permissions. Please try again in a moment."
            )]
        except Exception as playlist_error:
            return [TextContent(
                type="text",
                text=f"❌ Error creating playlist: {str(playlist_error)}\n"
                     f"💡 Please check your Spotify authentication and try again."
            )]
            
    except Exception as e:
        return [TextContent(
            type="text", 
            text=f"❌ Unexpected error: {str(e)}\n"
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
6. **debug_status** - Show detailed server status and configuration
7. **list_tools** - Show this help information

📋 Typical Usage Flow:
1. Run `debug_status` to check server status
2. Run `validate` to check configuration
3. Run `authenticate` to get Spotify auth URL
4. Visit the URL and authorize the app
5. Run `handle_callback` with the code from redirect URL
6. Run `generate_playlist` with your desired prompt

💡 All tools return structured responses and handle errors gracefully.

🔧 Recent Fixes:
- Fixed Spotify API parameter issues (seed_tracks vs seed_track_ids)
- Improved error handling for audio features requests
- Added language-based market filtering
- Better fallback mechanisms for recommendations
- Enhanced null/empty value checking throughout
    """
    return [TextContent(type="text", text=tools_info.strip())]


async def debug_server_status() -> list[TextContent]:
    """Show detailed server status and configuration for debugging."""
    global client, token, playlist_generator, cred, scope
    
    status_info = f"""
🔍 **Server Debug Status**

**Server Info:**
- Port: {port}
- MCP Endpoint: http://0.0.0.0:{port}/mcp/
- Running on Render: {'✅ Yes' if os.getenv('RENDER') else '❌ No'}

**Environment Variables:**
- SPOTIFY_CLIENT_ID: {'✅ Set' if os.getenv('SPOTIFY_CLIENT_ID') else '❌ Not Set'}
- SPOTIFY_CLIENT_SECRET: {'✅ Set' if os.getenv('SPOTIFY_CLIENT_SECRET') else '❌ Not Set'} 
- SPOTIFY_REDIRECT_URI: {os.getenv('SPOTIFY_REDIRECT_URI', 'Auto-detected')}
- MY_NUMBER: {os.getenv('MY_NUMBER', 'Not set')}

**Spotify Connection Status:**
- Credentials Initialized: {'✅ Yes' if cred is not None else '❌ No'}
- Scope Configured: {'✅ Yes' if scope is not None else '❌ No'}
- Token Available: {'✅ Yes' if token is not None else '❌ No'}
- Client Connected: {'✅ Yes' if client is not None else '❌ No'}
- Playlist Generator Ready: {'✅ Yes' if playlist_generator is not None else '❌ No'}

**Redirect URI:** {cred.redirect_uri if cred else 'Not available'}

**Token Status:**
{f'- Expires: {token.expires_at}' if token else '- No token available'}
{f'- Is Expiring: {token.is_expiring}' if token else ''}
{f'- Has Refresh Token: {"Yes" if token and token.refresh_token else "No"}' if token else ''}

**Recent Code Fixes:**
- ✅ Fixed audio features API URL encoding issue
- ✅ Fixed seed_tracks parameter in recommendations API
- ✅ Added better null checking for tracks and features
- ✅ Improved error handling with batched requests
- ✅ Added language-based market selection
    """
    
    return [TextContent(type="text", text=status_info.strip())]


def setup_mcp_server() -> FastMCP:
    """Set up the FastMCP server with all tools."""
    server = FastMCP("tekore-playlist-generator")
    
    # Register tools using the @server.tool decorator syntax
    @server.tool("health")
    async def health_tool() -> list[TextContent]:
        """Health check endpoint to verify server is running."""
        return await health_check()
    
    @server.tool("validate") 
    async def validate_tool() -> str:
        """Validate server configuration."""
        return await validate_config()
    
    @server.tool("authenticate")
    async def authenticate_tool() -> list[TextContent]:
        """Generate authentication URL for Spotify."""
        return await authenticate_spotify()
    
    @server.tool("handle_callback")
    async def callback_tool(code: str) -> list[TextContent]:
        """Handle Spotify OAuth callback with authorization code."""
        return await handle_spotify_callback(code)
    
    @server.tool("generate_playlist") 
    async def playlist_tool(
        prompt: str,
        duration_minutes: int = 60,
        playlist_name: str = "AI Generated Playlist"
    ) -> list[TextContent]:
        """Generate a Spotify playlist based on text prompt and sentiment analysis."""
        return await generate_spotify_playlist(prompt, duration_minutes, playlist_name)
    
    @server.tool("debug_status")
    async def debug_tool() -> list[TextContent]:
        """Show detailed server status and configuration for debugging."""
        return await debug_server_status()
    
    @server.tool("list_tools")
    async def tools_list() -> list[TextContent]:
        """List all available tools and their descriptions.""" 
        return await list_available_tools()
    
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
            print(f"💡 Note: You'll need to manually copy the authorization code from the redirect URL")
        
        # Log registered tools for debugging
        print(f"🛠️ Registered tools: health, validate, authenticate, handle_callback, generate_playlist, debug_status, list_tools")
        
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


async def call_debug_status():
    """Direct call to debug status tool."""
    return await debug_server_status()


async def call_list_tools():
    """Direct call to list tools."""
    return await list_available_tools()


if __name__ == "__main__":
    asyncio.run(main())