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
    
    # Check if required environment variables are set
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        print("❌ Missing Spotify credentials!")
        print("Required environment variables:")
        print("- SPOTIFY_CLIENT_ID")
        print("- SPOTIFY_CLIENT_SECRET")
        return False
    
    # Use environment variable or construct based on deployment
    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI")
    if not redirect_uri:
        if os.getenv("RENDER"):
            # Running on Render - use the Render URL
            base_url = os.getenv('RENDER_EXTERNAL_HOSTNAME', 'playlist-mcp.onrender.com')
            redirect_uri = f"https://{base_url}/callback"
        else:
            # Local development - use same port as MCP server
            redirect_uri = f"http://127.0.0.1:{port}/callback"
    
    try:
        cred = tk.Credentials(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri
        )
        
        scope = (
            tk.scope.playlist_modify_public + tk.scope.playlist_modify_private +
            tk.scope.user_read_recently_played + tk.scope.user_top_read +
            tk.scope.user_library_read + tk.scope.user_read_private
        )
        
        print(f"✅ Credentials initialized successfully")
        print(f"🔗 Redirect URI: {redirect_uri}")
        return True
        
    except Exception as e:
        print(f"❌ Error initializing credentials: {e}")
        return False


async def health_check() -> list[TextContent]:
    """Health check endpoint to verify server is running."""
    return [TextContent(
        type="text", 
        text=f"✅ MCP Server is healthy and running on port {port}"
    )]


async def validate_config() -> str:
    """Validate server configuration."""
    return os.getenv('MY_NUMBER', '') 

async def authenticate_spotify() -> list[TextContent]:
    """Generate authentication URL for Spotify."""
    try:
        # Ensure credentials are initialized
        if cred is None:
            if not initialize_credentials():
                return [TextContent(
                    type="text",
                    text="❌ Failed to initialize Spotify credentials. Please check your environment variables:\n- SPOTIFY_CLIENT_ID\n- SPOTIFY_CLIENT_SECRET"
                )]
            
        # Check if credentials are properly initialized
        if cred is None or not cred.client_id or not cred.client_secret:
            return [TextContent(
                type="text",
                text="❌ Spotify credentials not configured. Please set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables."
            )]
        
        if scope is None:
            return [TextContent(
                type="text",
                text="❌ Scope not initialized. Please restart the server."
            )]
        
        # Additional safety check
        if cred is None:
            return [TextContent(
                type="text",
                text="❌ Credentials not initialized after setup. Please check environment variables."
            )]
        
        auth_url = cred.user_authorisation_url(scope=scope)
        return [TextContent(
            type="text", 
            text=f"""🔗 **SPOTIFY AUTHENTICATION**

**Step 1:** Click this link to authorize:
{auth_url}

**Step 2:** After authorization, you'll be redirected to:
{cred.redirect_uri}

**Step 3:** Copy the 'code' parameter from the redirect URL and use it with the 'handle_callback' tool.

**Example redirect URL:**
{cred.redirect_uri}?code=YOUR_CODE_HERE&state=...

💡 **Just copy the long code after 'code=' and paste it when using handle_callback!**"""
        )]
    except Exception as e:
        return [TextContent(
            type="text", 
            text=f"❌ Error generating authentication URL: {str(e)}\n💡 Try running 'debug_status' to check configuration"
        )]


async def handle_spotify_callback(code: str) -> list[TextContent]:
    """Handle Spotify OAuth callback."""
    global client, token, playlist_generator
    
    try:
        if not code or not code.strip():
            return [TextContent(
                type="text", 
                text="❌ No authorization code provided. Please provide the authorization code from the Spotify redirect URL."
            )]
        
        # Clean the code (remove any whitespace)
        code = code.strip()
        
        if cred is None:
            if not initialize_credentials():
                return [TextContent(
                    type="text",
                    text="❌ Credentials not initialized. Please check your environment variables."
                )]
        
        # Additional check after initialization attempt
        if cred is None:
            return [TextContent(
                type="text",
                text="❌ Failed to initialize credentials. Please check your Spotify environment variables."
            )]
        
        print(f"🔄 Requesting token with code: {code[:10]}...")
        
        # Request token
        token = cred.request_user_token(code)
        if token:
            client = tk.Spotify(token)
            playlist_generator = PlaylistGenerator(client)
            
            # Test connection
            try:
                user = client.current_user()
                return [TextContent(
                    type="text", 
                    text=f"""✅ **AUTHENTICATION SUCCESSFUL!**

👤 **Logged in as:** {user.display_name or user.id}
🎵 **Spotify Premium:** {'Yes' if user.product == 'premium' else 'No'}
🌍 **Country:** {user.country or 'Unknown'}

🎉 **You're all set!** You can now generate playlists using the 'generate_playlist' tool.

💡 **Try something like:**
• "Generate a happy workout playlist"
• "Create a chill study playlist for 90 minutes"  
• "Make a sad rainy day playlist"
• "Generate an energetic party playlist"
"""
                )]
            except Exception as user_error:
                print(f"❌ User info error: {user_error}")
                return [TextContent(
                    type="text", 
                    text=f"✅ **Authentication successful** but couldn't fetch user info.\n"
                         f"You can still generate playlists!\n"
                         f"Debug info: {str(user_error)}"
                )]
        else:
            return [TextContent(
                type="text", 
                text="❌ Authentication failed: Could not retrieve token. Please try again with a fresh authorization code."
            )]
    except tk.BadRequest as e:
        error_details = str(e)
        print(f"❌ Bad request error: {error_details}")
        return [TextContent(
            type="text", 
            text=f"❌ Authentication failed: Invalid authorization code.\n"
                 f"💡 The code might be expired or already used. Please get a fresh code from the authentication URL.\n"
                 f"Error details: {error_details}"
        )]
    except tk.HTTPError as e:
        error_details = str(e)
        print(f"❌ HTTP error: {error_details}")
        return [TextContent(
            type="text", 
            text=f"❌ Spotify API error during authentication.\n"
                 f"💡 Please try again. If the problem persists, check your Spotify app settings.\n"
                 f"Error details: {error_details}"
        )]
    except Exception as e:
        error_details = str(e)
        print(f"❌ Unexpected error: {error_details}")
        return [TextContent(
            type="text", 
            text=f"❌ Authentication failed: {error_details}\n"
                 f"💡 Make sure to use the complete authorization code from the redirect URL."
        )]


async def analyze_prompt(prompt: str) -> Dict[str, Any]:
    """Analyze user prompt for sentiment and context."""
    try:
        sentiment_scores = await sentiment_analyzer.analyze_sentiment(prompt)
        
        # Safely detect language
        try:
            language = detect_language(prompt)
        except:
            language = "en"
        
        parsed_duration = parse_duration(prompt)
        
        try:
            emoji_sentiment = sentiment_analyzer.analyze_emojis(prompt)
        except:
            emoji_sentiment = {"neutral": 1.0}

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
            "sentiment": {"neutral": 1.0},
            "language": "en",
            "duration_hint": None,
            "emoji_sentiment": {"neutral": 1.0},
            "raw_prompt": prompt,
            "analysis_error": str(e)
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
            # Try to provide authentication instructions
            auth_instructions = await authenticate_spotify()
            return [TextContent(
                type="text", 
                text="❌ Please authenticate with Spotify first.\n\n" + auth_instructions[0].text
            )]

        # Refresh token if needed
        if token and token.is_expiring and token.refresh_token and cred is not None:
            try:
                print("🔄 Refreshing token...")
                token = cred.refresh_user_token(token.refresh_token)
                client = tk.Spotify(token)
                playlist_generator.client = client
            except Exception as refresh_error:
                print(f"❌ Token refresh error: {refresh_error}")
                return [TextContent(
                    type="text",
                    text=f"❌ Token refresh failed: {str(refresh_error)}. Please re-authenticate using the 'authenticate' tool."
                )]

        # Analyze prompt
        analysis_result = await analyze_prompt(prompt)

        # Create playlist with better error handling
        try:
            print(f"🎵 Creating playlist: {playlist_name}")
            playlist_url = await playlist_generator.create_playlist(
                analysis_result=analysis_result,
                duration_minutes=duration_minutes,
                playlist_name=playlist_name,
            )
            
            # Format sentiment for display
            sentiment_data = analysis_result.get('sentiment', {'neutral': 1.0})
            dominant_sentiment = max(sentiment_data.items(), key=lambda x: x[1])[0]
            
            return [TextContent(
                type="text",
                text=f"""✅ **Successfully created playlist: '{playlist_name}'**

🎵 **Spotify URL:** {playlist_url}
⏱️ **Duration:** {duration_minutes} minutes
🌍 **Language:** {analysis_result.get('language', 'unknown')}
📊 **Detected sentiment:** {dominant_sentiment}
🎯 **Prompt:** "{prompt}"

🎉 **Your playlist is ready!** Open the Spotify URL above to listen.

💡 **Tip:** You can create more playlists by changing the prompt or duration!""",
            )]
            
        except tk.HTTPError as http_error:
            error_details = str(http_error)
            print(f"❌ HTTP error creating playlist: {error_details}")
            return [TextContent(
                type="text",
                text=f"❌ Spotify API error: {error_details}\n"
                     f"💡 This might be due to rate limiting or insufficient permissions. Please try again in a moment."
            )]
        except Exception as playlist_error:
            error_details = str(playlist_error)
            print(f"❌ Playlist creation error: {error_details}")
            return [TextContent(
                type="text",
                text=f"❌ Error creating playlist: {error_details}\n"
                     f"💡 Please check your Spotify authentication and try again."
            )]
            
    except Exception as e:
        error_details = str(e)
        print(f"❌ Generate playlist error: {error_details}")
        return [TextContent(
            type="text", 
            text=f"❌ Unexpected error: {error_details}\n"
                 f"💡 If this is an authentication error, try re-authenticating with Spotify."
        )]


async def list_available_tools() -> list[TextContent]:
    """List all available tools and their descriptions."""
    tools_info = """
🛠️ **Available Tools:**

1. **health** - Check if the MCP server is running
2. **validate** - Validate server configuration and credentials  
3. **authenticate** - Get Spotify authentication URL
4. **handle_callback** - Process Spotify OAuth callback with authorization code
5. **generate_playlist** - Create playlists based on text prompts (requires authentication)
6. **debug_status** - Show detailed server status and configuration
7. **list_tools** - Show this help information

📋 **Typical Usage Flow:**
1. Run `debug_status` to check server status
2. Run `validate` to check configuration  
3. Run `authenticate` to get Spotify auth URL
4. Visit the URL and authorize the app
5. Copy the code from the redirect URL (after 'code=')
6. Run `handle_callback` with the authorization code
7. Run `generate_playlist` with your desired prompt

💡 **All tools return structured responses and handle errors gracefully.**

🔧 **Recent Fixes:**
- ✅ Simplified authentication flow (no callback server needed)
- ✅ Fixed Spotify API parameter issues 
- ✅ Improved error handling for audio features requests
- ✅ Added language-based market filtering
- ✅ Better fallback mechanisms for recommendations
- ✅ Enhanced null/empty value checking throughout
    """
    return [TextContent(type="text", text=tools_info.strip())]


async def debug_server_status() -> list[TextContent]:
    """Show detailed server status and configuration for debugging."""
    global client, token, playlist_generator, cred, scope
    
    # Check environment variables
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "Auto-detected")
    
    status_info = f"""
🔍 **Server Debug Status**

**Server Info:**
- MCP Port: {port}
- MCP Endpoint: http://0.0.0.0:{port}/mcp/
- Running on Render: {'✅ Yes' if os.getenv('RENDER') else '❌ No'}

**Environment Variables:**
- SPOTIFY_CLIENT_ID: {'✅ Set (' + str(len(client_id)) + ' chars)' if client_id else '❌ Not Set'}
- SPOTIFY_CLIENT_SECRET: {'✅ Set (' + str(len(client_secret)) + ' chars)' if client_secret else '❌ Not Set'} 
- SPOTIFY_REDIRECT_URI: {redirect_uri}
- MY_NUMBER: {os.getenv('MY_NUMBER', 'Not set')}

**Spotify Connection Status:**
- Credentials Initialized: {'✅ Yes' if cred is not None else '❌ No'}
- Scope Configured: {'✅ Yes' if scope is not None else '❌ No'}
- Token Available: {'✅ Yes' if token is not None else '❌ No'}
- Client Connected: {'✅ Yes' if client is not None else '❌ No'}
- Playlist Generator Ready: {'✅ Yes' if playlist_generator is not None else '❌ No'}

**Redirect URI:** {cred.redirect_uri if cred is not None else 'Not available'}

**Token Status:**
{f'- Expires: {token.expires_at}' if token else '- No token available'}
{f'- Is Expiring: {token.is_expiring}' if token else ''}
{f'- Has Refresh Token: {"Yes" if token and token.refresh_token else "No"}' if token else ''}

**Architecture Notes:**
- ✅ Simplified design - no separate callback server needed
- ✅ User manually copies code from redirect URL
- ✅ Same port for MCP server and redirect URI
- ✅ Works reliably across all deployment environments
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
        print("🔧 Initializing credentials...")
        if not initialize_credentials():
            print("❌ Failed to initialize credentials. Server cannot start properly.")
            print("Please check your environment variables:")
            print("- SPOTIFY_CLIENT_ID")
            print("- SPOTIFY_CLIENT_SECRET")
        
        # Setup MCP server
        server = setup_mcp_server()
        
        print(f"🚀 Starting Tekore Playlist MCP Server on port {port}")
        print(f"🔗 MCP endpoint: http://0.0.0.0:{port}/mcp/")
        
        if cred is not None:
            print(f"🎵 Spotify redirect URI: {cred.redirect_uri}")
            print(f"💡 Users will manually copy authorization codes from redirect URLs")
        
        # Log registered components
        print(f"🛠️ Registered MCP tools: health, validate, authenticate, handle_callback, generate_playlist, debug_status, list_tools")
        print(f"✅ Server ready for connections!")
        
        await server.run_async("streamable-http", host="0.0.0.0", port=port)
        
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        import traceback
        traceback.print_exc()
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