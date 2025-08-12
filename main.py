import asyncio
import json
import os
from typing import Dict, Any, Optional

import tekore as tk
from fastmcp import FastMCP
from mcp.types import TextContent
from urllib.parse import urlparse, parse_qs

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
last_auth_code = None  # Store the last received auth code


def initialize_credentials():
    """Initialize Spotify credentials and scope."""
    global cred, scope
    
    print("🔧 Initializing credentials...")
    
    # Check if required environment variables are set
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    
    print(f"   - Client ID: {'✅ Set' if client_id else '❌ Missing'}")
    print(f"   - Client Secret: {'✅ Set' if client_secret else '❌ Missing'}")
    
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
    
    print(f"   - Redirect URI: {redirect_uri}")
    
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
    """Generate authentication URL for Spotify - FIXED VERSION."""
    try:
        print("🔄 Starting authentication process...")
        
        # Force re-initialization of credentials
        if cred is None:
            print("   - Credentials not found, initializing...")
            if not initialize_credentials():
                error_msg = "❌ Failed to initialize Spotify credentials. Please check your environment variables:\n- SPOTIFY_CLIENT_ID\n- SPOTIFY_CLIENT_SECRET"
                print(f"   - {error_msg}")
                return [TextContent(type="text", text=error_msg)]
        
        # Double-check after initialization
        if cred is None:
            error_msg = "❌ Credentials still None after initialization"
            print(f"   - {error_msg}")
            return [TextContent(type="text", text=error_msg)]
            
        if not cred.client_id or not cred.client_secret:
            error_msg = "❌ Spotify credentials not properly configured"
            print(f"   - {error_msg}")
            return [TextContent(type="text", text=error_msg)]
        
        if scope is None:
            error_msg = "❌ Scope not initialized"
            print(f"   - {error_msg}")
            return [TextContent(type="text", text=error_msg)]
        
        # Generate the auth URL
        print("   - Generating authentication URL...")
        auth_url = cred.user_authorisation_url(scope=scope)
        print(f"   - URL generated: {auth_url[:50]}...")
        
        # Create the response text
        response_text = f"""🔗 **SPOTIFY AUTHENTICATION**

**Step 1:** Click this link to authorize:
{auth_url}

**Step 2:** After authorization, you'll be redirected to:
{cred.redirect_uri}

**Step 3:** Copy the 'code' parameter from the redirect URL and use it with the 'handle_callback' tool.

**Example redirect URL:**
{cred.redirect_uri}?code=YOUR_CODE_HERE&state=...

💡 **Just copy the long code after 'code=' and paste it when using handle_callback!**"""
        
        print("✅ Authentication response prepared")
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_msg = f"❌ Error generating authentication URL: {str(e)}\n💡 Try running 'debug_status' to check configuration"
        print(f"❌ Authentication error: {e}")
        import traceback
        traceback.print_exc()
        return [TextContent(type="text", text=error_msg)]


async def handle_spotify_callback(code: str) -> list[TextContent]:
    """Handle Spotify OAuth callback."""
    global client, token, playlist_generator
    
    try:
        print(f"🔄 Processing callback with code: {code[:10]}...")
        
        if not code or not code.strip():
            return [TextContent(
                type="text", 
                text="❌ No authorization code provided. Please provide the authorization code from the Spotify redirect URL."
            )]
        
        # Clean the code (remove any whitespace)
        code = code.strip()
        
        if cred is None:
            print("   - Credentials not found, initializing...")
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
        
        print(f"   - Requesting token with code: {code[:10]}...")
        
        # Request token
        token = cred.request_user_token(code)
        if token and token.access_token:
            print(f"   - Token received: {token.access_token[:20]}...")
            client = tk.Spotify(token)
            playlist_generator = PlaylistGenerator(client)
            
            # Test connection
            try:
                print("   - Testing API connection...")
                user = client.current_user()
                print(f"   - Connected as: {user.id}")
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
                print(f"   - User info error: {user_error}")
                # Check if it's the 401 error we've been seeing
                if "401" in str(user_error) or "No token provided" in str(user_error):
                    return [TextContent(
                        type="text", 
                        text=f"⚠️ **Authentication completed but API test failed**\n"
                             f"Error: {str(user_error)}\n\n"
                             f"**Token status:** {token.access_token[:20] if token and token.access_token else 'None'}...\n"
                             f"**Try generating a playlist anyway - it might still work!**"
                    )]
                else:
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
        import traceback
        traceback.print_exc()
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
        print(f"🎵 Starting playlist generation: {playlist_name}")
        
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
        
        # Check authentication state
        print(f"   - Token exists: {token is not None}")
        print(f"   - Token has access_token: {token and token.access_token is not None}")
        print(f"   - Client exists: {client is not None}")
        print(f"   - Playlist generator exists: {playlist_generator is not None}")
        
        if not token or not token.access_token:
            # Try to provide authentication instructions
            auth_instructions = await authenticate_spotify()
            return [TextContent(
                type="text", 
                text="❌ No valid authentication token. Please authenticate with Spotify first.\n\n" + auth_instructions[0].text
            )]
        
        if not client or not playlist_generator:
            return [TextContent(
                type="text", 
                text="❌ Client or playlist generator not initialized. Please re-authenticate."
            )]

        # Refresh token if needed
        if token and token.is_expiring and token.refresh_token and cred is not None:
            try:
                print("🔄 Refreshing token...")
                old_token = token.access_token[:20] if token.access_token else "None"
                token = cred.refresh_user_token(token.refresh_token)
                new_token = token.access_token[:20] if token.access_token else "None"
                print(f"   - Token refreshed: {old_token}... → {new_token}...")
                client = tk.Spotify(token)
                playlist_generator.client = client
            except Exception as refresh_error:
                print(f"❌ Token refresh error: {refresh_error}")
                return [TextContent(
                    type="text",
                    text=f"❌ Token refresh failed: {str(refresh_error)}. Please re-authenticate using the 'authenticate' tool."
                )]

        # Analyze prompt
        print("   - Analyzing prompt...")
        analysis_result = await analyze_prompt(prompt)

        # Create playlist with better error handling
        try:
            print(f"   - Creating playlist with {duration_minutes} min target...")
            playlist_url = await playlist_generator.create_playlist(
                analysis_result=analysis_result,
                duration_minutes=duration_minutes,
                playlist_name=playlist_name,
            )
            
            # Format sentiment for display
            sentiment_data = analysis_result.get('sentiment', {'neutral': 1.0})
            dominant_sentiment = max(sentiment_data.items(), key=lambda x: x[1])[0]
            
            print(f"✅ Playlist created successfully: {playlist_url}")
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
            
            # Check for specific 401 error
            if "401" in error_details or "No token provided" in error_details:
                return [TextContent(
                    type="text",
                    text=f"""❌ **TOKEN ERROR: {error_details}**
                    
🔑 **Token status:** {token.access_token[:20] if token and token.access_token else 'None'}...

**This suggests the token is not being sent with API requests.**

**Solutions:**
1. Re-authenticate completely (get fresh token)
2. Check if token expired
3. Verify client has token attached

**Try re-authenticating and then generating the playlist again.**"""
                )]
            else:
                return [TextContent(
                    type="text",
                    text=f"❌ Spotify API error: {error_details}\n"
                         f"💡 This might be due to rate limiting or insufficient permissions. Please try again in a moment."
                )]
        except Exception as playlist_error:
            error_details = str(playlist_error)
            print(f"❌ Playlist creation error: {error_details}")
            import traceback
            traceback.print_exc()
            return [TextContent(
                type="text",
                text=f"❌ Error creating playlist: {error_details}\n"
                     f"💡 Please check your Spotify authentication and try again."
            )]
            
    except Exception as e:
        error_details = str(e)
        print(f"❌ Generate playlist error: {error_details}")
        import traceback
        traceback.print_exc()
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
8. **test_auth_url** - Test authentication URL generation with debug info
9. **debug_token** - Debug current token state

📋 **Typical Usage Flow:**
1. Run `debug_status` to check server status
2. Run `validate` to check configuration  
3. Run `authenticate` to get Spotify auth URL
4. Visit the URL and authorize the app
5. Copy the code from the redirect URL (after 'code=')
6. Run `handle_callback` with the authorization code
7. Run `generate_playlist` with your desired prompt

💡 **All tools return structured responses and handle errors gracefully.**

🔧 **Debug Tools:**
- Use `test_auth_url` if authenticate isn't showing the URL
- Use `debug_token` to check token state
- Use `debug_status` for full system status
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
{f'- Access Token Preview: {token.access_token[:20] if token and token.access_token else "None"}...' if token else ''}

**Architecture Notes:**
- ✅ Simplified design - no separate callback server needed
- ✅ User manually copies code from redirect URL
- ✅ Same port for MCP server and redirect URI
- ✅ Works reliably across all deployment environments
"""
    
    return [TextContent(type="text", text=status_info.strip())]


async def debug_token_state() -> list[TextContent]:
    """Debug current token state."""
    global token, client, playlist_generator
    
    debug_info = []
    debug_info.append("🔍 **TOKEN DEBUG INFO**\n")
    
    # Check token existence
    if token is None:
        debug_info.append("❌ **Token is None** - Need to authenticate")
    else:
        debug_info.append(f"✅ **Token exists**")
        debug_info.append(f"   - Type: {type(token)}")
        debug_info.append(f"   - Expires at: {token.expires_at}")
        debug_info.append(f"   - Is expiring: {token.is_expiring}")
        debug_info.append(f"   - Has refresh token: {token.refresh_token is not None}")
        debug_info.append(f"   - Access token preview: {str(token.access_token)[:20]}..." if token.access_token else "   - ❌ No access token!")
    
    # Check client
    if client is None:
        debug_info.append("❌ **Client is None**")
    else:
        debug_info.append(f"✅ **Client exists**: {type(client)}")
        debug_info.append(f"   - Client token: {hasattr(client, 'token') and client.token is not None}")
    
    # Check playlist generator
    if playlist_generator is None:
        debug_info.append("❌ **Playlist generator is None**")
    else:
        debug_info.append(f"✅ **Playlist generator exists**")
        debug_info.append(f"   - Has client: {playlist_generator.client is not None}")
    
    return [TextContent(type="text", text="\n".join(debug_info))]


async def test_auth_url() -> list[TextContent]:
    """Test authentication URL generation with detailed logging."""
    try:
        print("🧪 Testing authentication URL generation...")
        
        # Force initialize credentials
        result = initialize_credentials()
        
        if not result:
            return [TextContent(type="text", text="❌ Failed to initialize credentials")]
        
        if cred is None:
            return [TextContent(type="text", text="❌ Credentials still None after initialization")]
        
        print(f"✅ Credentials exist:")
        print(f"   - Client ID: {cred.client_id[:10]}..." if cred.client_id else "   - No Client ID")
        print(f"   - Client Secret: {'Set' if cred.client_secret else 'Not set'}")
        print(f"   - Redirect URI: {cred.redirect_uri}")
        
        # Check scope
        if scope is None:
            return [TextContent(type="text", text="❌ Scope not initialized")]
        
        print(f"✅ Scope configured: {len(str(scope))} characters")
        
        # Generate URL
        auth_url = cred.user_authorisation_url(scope=scope)
        print(f"✅ Generated URL: {auth_url}")
        
        return [TextContent(
            type="text", 
            text=f"""🧪 **AUTH URL TEST RESULTS**

**Status:** ✅ Success

**Generated URL:**
{auth_url}

**Components:**
- Client ID: {cred.client_id[:10]}...
- Redirect URI: {cred.redirect_uri}
- Scope Length: {len(str(scope))} chars

**👆 Click the URL above to authenticate!**"""
        )]
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return [TextContent(
            type="text", 
            text=f"❌ Auth URL test failed: {str(e)}\n\nCheck server logs for detailed error."
        )]


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
        print("🔄 Authenticate tool called")
        result = await authenticate_spotify()
        print(f"📤 Authenticate tool returning: {len(result)} items")
        if result:
            print(f"   First item preview: {result[0].text[:100]}...")
        return result
    
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
    
    @server.tool("test_auth_url")
    async def test_auth_url_tool() -> list[TextContent]:
        """Test authentication URL generation with detailed logging."""
        return await test_auth_url()
    
    @server.tool("debug_token")
    async def debug_token_tool() -> list[TextContent]:
        """Debug current token state."""
        return await debug_token_state()
    
    @server.tool("get_auth_url")
    async def get_auth_url_tool() -> list[TextContent]:
        """Simple backup auth URL generator."""
        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        
        if not client_id:
            return [TextContent(type="text", text="❌ SPOTIFY_CLIENT_ID not set")]
        
        redirect_uri = f"http://127.0.0.1:{port}/callback"
        scopes = "playlist-modify-public playlist-modify-private user-read-recently-played user-top-read user-library-read user-read-private"
        
        url = f"https://accounts.spotify.com/authorize?client_id={client_id}&response_type=code&redirect_uri={redirect_uri}&scope={scopes.replace(' ', '%20')}"
        
        return [TextContent(
            type="text",
            text=f"""🎵 **SPOTIFY AUTHENTICATION URL**

{url}

**Instructions:**
1. Click the URL above
2. Authorize the app
3. Copy the 'code' from the redirect URL
4. Use handle_callback with that code"""
        )]
    
    @server.tool("show_url")
    async def show_url_tool() -> list[TextContent]:
        """Show raw authentication URL."""
        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        if not client_id:
            return [TextContent(type="text", text="❌ No client ID")]
        
        url = f"https://accounts.spotify.com/authorize?client_id={client_id}&response_type=code&redirect_uri=http://127.0.0.1:{port}/callback&scope=playlist-modify-public%20playlist-modify-private%20user-read-recently-played%20user-top-read%20user-library-read%20user-read-private"
        
        return [TextContent(type="text", text=url)]
    
    @server.tool("auto_auth")
    async def auto_auth_tool() -> list[TextContent]:
        """Complete authentication flow automatically."""
        global last_auth_code
        
        # Step 1: Generate auth URL
        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        if not client_id:
            return [TextContent(type="text", text="❌ No client ID")]
        
        url = f"https://accounts.spotify.com/authorize?client_id={client_id}&response_type=code&redirect_uri=http://127.0.0.1:{port}/callback&scope=playlist-modify-public%20playlist-modify-private%20user-read-recently-played%20user-top-read%20user-library-read%20user-read-private"
        
        return [TextContent(
            type="text",
            text=f"""🔄 **AUTOMATIC AUTHENTICATION**

**Step 1:** Click this URL to authorize:
{url}

**Step 2:** After authorizing, you'll see an error page
**Step 3:** Copy the ENTIRE URL from your browser and use 'process_callback_url' tool

**Or manually copy just the code part and use 'handle_callback'**

**The URL will look like:**
http://127.0.0.1:{port}/callback?code=LONG_CODE_HERE&state=...

**Just copy everything after 'code=' and before '&' (or end of URL)**"""
        )]
    
    @server.tool("process_callback_url")
    async def process_callback_url_tool(full_url: str) -> list[TextContent]:
        """Process the full callback URL to extract and use the code."""
        try:
            # Parse the URL
            parsed = urlparse(full_url)
            query_params = parse_qs(parsed.query)
            
            if 'code' not in query_params:
                return [TextContent(
                    type="text",
                    text="❌ No 'code' parameter found in URL. Please copy the complete redirect URL."
                )]
            
            code = query_params['code'][0]
            
            # Automatically handle the callback
            result = await handle_spotify_callback(code)
            
            return [TextContent(
                type="text",
                text=f"✅ **Extracted code and processed automatically!**\n\n{result[0].text}"
            )]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"❌ Error processing URL: {str(e)}\n\nPlease copy just the code part manually and use 'handle_callback'"
            )]
    
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
        print(f"🛠️ Registered MCP tools: health, validate, authenticate, handle_callback, generate_playlist, debug_status, list_tools, test_auth_url, debug_token")
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