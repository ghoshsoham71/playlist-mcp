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


class TekorePlaylistMCP:
    def __init__(self):
        self.server = FastMCP("tekore-playlist-generator")
        self.client: Optional[tk.Spotify] = None
        self.token: Optional[tk.Token] = None
        self.playlist_generator: Optional[PlaylistGenerator] = None
        self.sentiment_analyzer = SentimentAnalyzer()

        # Get port from environment (for Render compatibility)
        self.port = int(os.getenv("PORT", 8086))
        
        # Initialize credentials with dynamic redirect URI
        redirect_uri = os.getenv(
            "SPOTIFY_REDIRECT_URI", 
            f"http://localhost:{self.port}/callback"
        )
        
        self.cred = tk.Credentials(
            client_id=os.getenv("SPOTIFY_CLIENT_ID", ''),
            client_secret=os.getenv("SPOTIFY_CLIENT_SECRET", ''),
            redirect_uri=redirect_uri
        )
        
        self.scope = (
            tk.scope.playlist_modify_public + tk.scope.playlist_modify_private +
            tk.scope.user_read_recently_played + tk.scope.user_top_read +
            tk.scope.user_library_read + tk.scope.user_read_private
        )

        self._setup_tools()

    def _setup_tools(self):
        """Set up all MCP tools with proper error handling."""

        @self.server.tool("health")
        async def health() -> list[TextContent]:
            """Health check endpoint to verify server is running."""
            return [TextContent(
                type="text", 
                text=f"✅ MCP Server is healthy and running on port {self.port}"
            )]

        @self.server.tool("validate")
        async def validate() -> str:
            """Validate server configuration."""
            my_number = os.getenv('MY_NUMBER', '') 
            return my_number

        @self.server.tool("authenticate")
        async def authenticate() -> list[TextContent]:
            """Generate authentication URL for Spotify."""
            try:
                if not self.cred.client_id or not self.cred.client_secret:
                    return [TextContent(
                        type="text",
                        text="❌ Spotify credentials not configured. Please set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables."
                    )]
                
                auth_url = self.cred.user_authorisation_url(scope=self.scope)
                return [TextContent(
                    type="text", 
                    text=f"🔗 Please authenticate with Spotify:\n{auth_url}\n\n"
                         f"After authorization, you'll be redirected to:\n{self.cred.redirect_uri}\n\n"
                         f"Copy the 'code' parameter from the redirect URL and use it with the 'handle_callback' tool."
                )]
            except Exception as e:
                return [TextContent(
                    type="text", 
                    text=f"❌ Error generating authentication URL: {str(e)}"
                )]

        @self.server.tool("handle_callback")
        async def handle_callback(code: str) -> list[TextContent]:
            """Handle Spotify OAuth callback."""
            try:
                if not code:
                    return [TextContent(
                        type="text", 
                        text="❌ No authorization code provided. Please provide the 'code' parameter from the Spotify redirect URL."
                    )]
                
                self.token = self.cred.request_user_token(code)
                if self.token:
                    self.client = tk.Spotify(self.token)
                    self.playlist_generator = PlaylistGenerator(self.client)
                    
                    # Test connection
                    user = self.client.current_user()
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

        @self.server.tool("generate_playlist")
        async def generate_playlist(
            prompt: str,
            duration_minutes: int = 60,
            playlist_name: str = "AI Generated Playlist",
        ) -> list[TextContent]:
            """Generate a Spotify playlist based on text prompt and sentiment analysis."""
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
                
                if not self.client or not self.playlist_generator:
                    return [TextContent(
                        type="text", 
                        text="❌ Please authenticate with Spotify first using the 'authenticate' and 'handle_callback' tools."
                    )]

                # Refresh token if needed
                if self.token and self.token.is_expiring and self.token.refresh_token:
                    try:
                        self.token = self.cred.refresh_user_token(self.token.refresh_token)
                        self.client = tk.Spotify(self.token)
                        self.playlist_generator.client = self.client
                    except Exception as refresh_error:
                        return [TextContent(
                            type="text",
                            text=f"❌ Token refresh failed: {str(refresh_error)}. Please re-authenticate using the 'authenticate' tool."
                        )]

                # Analyze prompt
                analysis_result = await self._analyze_prompt(prompt)

                # Create playlist
                playlist_url = await self.playlist_generator.create_playlist(
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

        @self.server.tool("list_tools")
        async def list_tools() -> list[TextContent]:
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

    async def _analyze_prompt(self, prompt: str) -> Dict[str, Any]:
        """Analyze user prompt for sentiment and context."""
        try:
            sentiment_scores = await self.sentiment_analyzer.analyze_sentiment(prompt)
            language = detect_language(prompt)
            parsed_duration = parse_duration(prompt)
            emoji_sentiment = self.sentiment_analyzer.analyze_emojis(prompt)

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

    async def run(self) -> None:
        """Run the MCP server."""
        try:
            print(f"🚀 Starting Tekore Playlist MCP Server on port {self.port}")
            print(f"🔗 MCP endpoint: http://0.0.0.0:{self.port}/mcp/")
            print(f"🎵 Spotify redirect URI: {self.cred.redirect_uri}")
            
            await self.server.run_async("streamable-http", host="0.0.0.0", port=self.port)
        except Exception as e:
            print(f"❌ Failed to start server: {e}")
            raise


async def main() -> None:
    """Main entry point."""
    try:
        server = TekorePlaylistMCP()
        await server.run()
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"❌ Server error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())