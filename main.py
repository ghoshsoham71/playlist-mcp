import asyncio
import json
import os
from typing import Dict, Any, Optional
from urllib.parse import parse_qs, urlparse
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

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
callback_port = port + 1  # Use next port for callback server
callback_server = None


class CallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Spotify OAuth callback."""
    
    def do_GET(self):
        """Handle GET request for OAuth callback."""
        try:
            # Parse URL and query parameters
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)
            
            code = query_params.get('code', [None])[0]
            error = query_params.get('error', [None])[0]
            
            # Set response headers
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            if error:
                html_content = self._generate_error_page(error)
            elif code:
                html_content = self._generate_success_page(code)
            else:
                html_content = self._generate_no_code_page()
            
            # Send response
            self.wfile.write(html_content.encode('utf-8'))
            
        except Exception as e:
            print(f"Callback handler error: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            error_html = f"<html><body><h1>Server Error</h1><p>{str(e)}</p></body></html>"
            self.wfile.write(error_html.encode('utf-8'))
    
    def _generate_error_page(self, error: str) -> str:
        """Generate error page HTML."""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Spotify Auth - Error</title>
            <style>
                body {{ 
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    margin: 0;
                    padding: 40px;
                    background: linear-gradient(135deg, #1DB954 0%, #191414 100%);
                    color: white;
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }}
                .container {{
                    background: rgba(255, 255, 255, 0.1);
                    padding: 40px;
                    border-radius: 20px;
                    backdrop-filter: blur(10px);
                    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
                    text-align: center;
                    max-width: 600px;
                }}
                .error {{
                    color: #ff4444;
                    font-size: 24px;
                    margin-bottom: 20px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>❌ Authentication Error</h1>
                <div class="error">Error: {error}</div>
                <p>Please try the authentication process again.</p>
            </div>
        </body>
        </html>
        """
    
    def _generate_success_page(self, code: str) -> str:
        """Generate success page HTML with prominent code display."""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Spotify Auth - Success</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ 
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background: linear-gradient(135deg, #1DB954 0%, #191414 100%);
                    color: white;
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }}
                .container {{
                    background: rgba(255, 255, 255, 0.1);
                    padding: 30px;
                    border-radius: 20px;
                    backdrop-filter: blur(10px);
                    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
                    text-align: center;
                    max-width: 90%;
                    width: 800px;
                }}
                .code-box {{
                    background: rgba(0, 0, 0, 0.4);
                    border: 3px solid #1DB954;
                    border-radius: 15px;
                    padding: 25px;
                    margin: 25px 0;
                    word-break: break-all;
                    cursor: pointer;
                    transition: all 0.3s ease;
                    position: relative;
                }}
                .code-box:hover {{
                    background: rgba(0, 0, 0, 0.6);
                    transform: scale(1.01);
                    border-color: #1ed760;
                }}
                .auth-code {{
                    font-family: 'Courier New', monospace;
                    font-size: clamp(18px, 4vw, 28px);
                    font-weight: bold;
                    color: #1DB954;
                    text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.7);
                    line-height: 1.3;
                    margin: 0;
                    padding: 10px;
                    background: rgba(29, 185, 84, 0.1);
                    border-radius: 10px;
                }}
                .copy-instruction {{
                    font-size: 16px;
                    color: #b3b3b3;
                    margin-top: 15px;
                    font-weight: 500;
                }}
                .success-icon {{
                    font-size: 48px;
                    margin-bottom: 15px;
                    animation: pulse 2s infinite;
                }}
                @keyframes pulse {{
                    0%, 100% {{ transform: scale(1); }}
                    50% {{ transform: scale(1.1); }}
                }}
                .next-steps {{
                    background: rgba(29, 185, 84, 0.2);
                    border-radius: 10px;
                    padding: 20px;
                    margin-top: 25px;
                    text-align: left;
                    border-left: 4px solid #1DB954;
                }}
                .step {{
                    margin-bottom: 8px;
                    font-size: 15px;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }}
                .copy-status {{
                    margin: 15px 0;
                    padding: 10px;
                    border-radius: 8px;
                    font-weight: bold;
                    display: none;
                }}
                .copy-success {{
                    background: rgba(29, 185, 84, 0.3);
                    color: #1ed760;
                    border: 1px solid #1DB954;
                }}
                .copy-error {{
                    background: rgba(255, 68, 68, 0.3);
                    color: #ff6b6b;
                    border: 1px solid #ff4444;
                }}
                @media (max-width: 600px) {{
                    .container {{ padding: 20px; margin: 10px; }}
                    .code-box {{ padding: 15px; margin: 15px 0; }}
                    .auth-code {{ font-size: 16px; }}
                }}
            </style>
            <script>
                let copyCount = 0;
                
                function copyCode() {{
                    const code = document.getElementById('authCode').textContent;
                    const successDiv = document.getElementById('copySuccess');
                    const errorDiv = document.getElementById('copyError');
                    
                    // Hide previous status
                    successDiv.style.display = 'none';
                    errorDiv.style.display = 'none';
                    
                    if (navigator.clipboard) {{
                        navigator.clipboard.writeText(code).then(function() {{
                            copyCount++;
                            successDiv.textContent = `✅ Code copied to clipboard! (Copy #${{copyCount}})`;
                            successDiv.style.display = 'block';
                            setTimeout(() => {{
                                successDiv.style.display = 'none';
                            }}, 3000);
                        }}).catch(function() {{
                            showFallbackCopy(code);
                        }});
                    }} else {{
                        showFallbackCopy(code);
                    }}
                }}
                
                function showFallbackCopy(code) {{
                    const errorDiv = document.getElementById('copyError');
                    errorDiv.innerHTML = `
                        ⚠️ Auto-copy not supported. Please manually select and copy the code above.
                        <br><small>Tip: Triple-click the code to select all of it quickly!</small>
                    `;
                    errorDiv.style.display = 'block';
                    
                    // Auto-select the code text
                    const codeElement = document.getElementById('authCode');
                    if (window.getSelection && document.createRange) {{
                        const selection = window.getSelection();
                        const range = document.createRange();
                        range.selectNodeContents(codeElement);
                        selection.removeAllRanges();
                        selection.addRange(range);
                    }}
                }}
                
                // Try auto-copy on page load
                window.onload = function() {{
                    setTimeout(() => {{
                        copyCode();
                    }}, 500);
                }}
            </script>
        </head>
        <body>
            <div class="container">
                <div class="success-icon">✅</div>
                <h1>Spotify Authentication Successful!</h1>
                
                <div id="copySuccess" class="copy-status copy-success"></div>
                <div id="copyError" class="copy-status copy-error"></div>
                
                <h2 style="margin-bottom: 10px;">Your Authorization Code:</h2>
                <div class="code-box" onclick="copyCode()">
                    <div class="auth-code" id="authCode">{code}</div>
                    <div class="copy-instruction">👆 Click anywhere in this box to copy the code</div>
                </div>
                
                <div class="next-steps">
                    <h3 style="margin-top: 0; color: #1DB954;">📋 Next Steps:</h3>
                    <div class="step">
                        <span>1.</span>
                        <span>✅ Code should be auto-copied to your clipboard</span>
                    </div>
                    <div class="step">
                        <span>2.</span>
                        <span>🔄 Return to your AI assistant chat</span>
                    </div>
                    <div class="step">
                        <span>3.</span>
                        <span>📝 Paste the code when prompted for the callback</span>
                    </div>
                    <div class="step">
                        <span>4.</span>
                        <span>🎵 Start generating amazing playlists!</span>
                    </div>
                </div>
                
                <p style="margin-top: 25px; color: #b3b3b3; font-size: 14px;">
                    You can now close this tab and return to your AI assistant.
                </p>
            </div>
        </body>
        </html>
        """
    
    def _generate_no_code_page(self) -> str:
        """Generate page when no code is found."""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Spotify Auth - No Code</title>
            <style>
                body { 
                    font-family: 'Segoe UI', sans-serif;
                    padding: 40px;
                    background: linear-gradient(135deg, #1DB954 0%, #191414 100%);
                    color: white;
                    text-align: center;
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }
                .container {
                    background: rgba(255, 255, 255, 0.1);
                    padding: 40px;
                    border-radius: 20px;
                    backdrop-filter: blur(10px);
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>⚠️ No Authorization Code</h1>
                <p>No authorization code was found in the URL.</p>
                <p>Please try the authentication process again.</p>
            </div>
        </body>
        </html>
        """
    
    def log_message(self, format, *args):
        """Override to reduce log spam."""
        pass


def start_callback_server():
    """Start the callback HTTP server in a separate thread."""
    global callback_server
    
    try:
        server_address = ('', callback_port)
        callback_server = HTTPServer(server_address, CallbackHandler)
        
        print(f"🌐 Starting callback server on port {callback_port}")
        callback_server.serve_forever()
    except Exception as e:
        print(f"❌ Callback server error: {e}")


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
        # For deployment
        if os.getenv("RENDER"):
            # Running on Render - Render doesn't support custom ports in URLs
            base_url = os.getenv('RENDER_EXTERNAL_HOSTNAME', 'playlist-mcp.onrender.com')
            redirect_uri = f"https://{base_url}/callback"
        else:
            # Local development - use callback server port
            redirect_uri = f"http://127.0.0.1:{callback_port}/callback"
    
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
        text=f"✅ MCP Server is healthy and running on port {port}\n🌐 Callback server on port {callback_port}"
    )]


async def validate_config() -> str:
    """Validate server configuration."""
    my_number = os.getenv('MY_NUMBER', '') 
    client_id_status = "✅ Set" if os.getenv("SPOTIFY_CLIENT_ID") else "❌ Missing"
    client_secret_status = "✅ Set" if os.getenv("SPOTIFY_CLIENT_SECRET") else "❌ Missing"
    
    return f"""Configuration Status:
- MY_NUMBER: {my_number}
- SPOTIFY_CLIENT_ID: {client_id_status}
- SPOTIFY_CLIENT_SECRET: {client_secret_status}
- Credentials initialized: {'✅ Yes' if cred else '❌ No'}
"""


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
        
        auth_url = cred.user_authorisation_url(scope=scope)
        return [TextContent(
            type="text", 
            text=f"""🔗 **SPOTIFY AUTHENTICATION**

**Step 1:** Click this link to authorize:
{auth_url}

**Step 2:** After authorization, you'll be redirected to a beautiful page that will:
• ✅ **Automatically copy the authorization code to your clipboard**
• 📋 **Display the code in LARGE, prominent text**
• 🎨 **Provide a mobile-friendly interface**
• 🔄 **Show clear next steps**

**Step 3:** Return here and use the 'handle_callback' tool with the code

**Redirect URL:** {cred.redirect_uri}

💡 **The authorization code will be displayed prominently with auto-copy functionality!**
🎯 **No more squinting at tiny URL parameters!**"""
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
                text="❌ No authorization code provided. Please provide the authorization code from the Spotify redirect page."
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
                 f"💡 Make sure to use the complete authorization code from the callback page."
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
5. Copy the code from the beautiful callback page (auto-copied!)
6. Run `handle_callback` with the authorization code
7. Run `generate_playlist` with your desired prompt

💡 **All tools return structured responses and handle errors gracefully.**

🆕 **New Features:**
- ✅ Dedicated callback server with beautiful UI
- 📋 Auto-copy authorization code to clipboard
- 🎨 Large, mobile-friendly code display  
- 📱 Responsive design for all devices
- 🔄 Better error handling throughout
- 🎯 Enhanced playlist generation with sentiment analysis
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
- Callback Port: {callback_port} 
- MCP Endpoint: http://0.0.0.0:{port}/mcp/
- Callback Endpoint: http://0.0.0.0:{callback_port}/callback ✅
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

**Redirect URI:** {cred.redirect_uri if cred else 'Not available'}

**Token Status:**
{f'- Expires: {token.expires_at}' if token else '- No token available'}
{f'- Is Expiring: {token.is_expiring}' if token else ''}
{f'- Has Refresh Token: {"Yes" if token and token.refresh_token else "No"}' if token else ''}

**Callback Server Status:**
- Server Running: {'✅ Yes' if callback_server else '❌ No'}
- Port Available: {callback_port}
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
    """Run the MCP server and callback server."""
    try:
        # Initialize credentials first
        print("🔧 Initializing credentials...")
        if not initialize_credentials():
            print("❌ Failed to initialize credentials. Server cannot start properly.")
            print("Please check your environment variables:")
            print("- SPOTIFY_CLIENT_ID")
            print("- SPOTIFY_CLIENT_SECRET")
        
        # Start callback server in background thread  
        print("🌐 Starting callback server...")
        callback_thread = threading.Thread(target=start_callback_server, daemon=True)
        callback_thread.start()
        
        # Small delay to let callback server start
        await asyncio.sleep(2)
        
        # Setup MCP server
        server = setup_mcp_server()
        
        print(f"🚀 Starting Tekore Playlist MCP Server on port {port}")
        print(f"🔗 MCP endpoint: http://0.0.0.0:{port}/mcp/")
        print(f"🌐 Callback endpoint: http://0.0.0.0:{callback_port}/callback")
        
        if cred is not None:
            print(f"🎵 Spotify redirect URI: {cred.redirect_uri}")
            print(f"💡 Callback page will auto-copy authorization codes!")
        
        # Log registered components
        print(f"🛠️ Registered MCP tools: health, validate, authenticate, handle_callback, generate_playlist, debug_status, list_tools")
        print(f"🌐 Callback server running on separate thread")
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
        if callback_server:
            callback_server.shutdown()
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