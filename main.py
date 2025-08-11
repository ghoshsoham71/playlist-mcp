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

        # Initialize credentials
        self.cred = tk.Credentials(
            client_id=os.getenv("SPOTIFY_CLIENT_ID", ''),
            client_secret=os.getenv("SPOTIFY_CLIENT_SECRET", ''),
            redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8080/callback")
        )
        
        self.scope = (
            tk.scope.playlist_modify_public + tk.scope.playlist_modify_private +
            tk.scope.user_read_recently_played + tk.scope.user_top_read +
            tk.scope.user_library_read + tk.scope.user_read_private
        )

        self._setup_tools()

    def _setup_tools(self):
        @self.server.tool("authenticate")
        async def authenticate() -> list[TextContent]:
            """Generate authentication URL for Spotify."""
            auth_url = self.cred.user_authorisation_url(scope=self.scope)
            return [TextContent(
                type="text", 
                text=f"🔗 Please authenticate with Spotify: {auth_url}\n\nAfter authorization, use the 'handle_callback' tool with the code from the redirect URL."
            )]

        @self.server.tool("handle_callback")
        async def handle_callback(code: str) -> list[TextContent]:
            """Handle Spotify OAuth callback."""
            try:
                self.token = self.cred.request_user_token(code)
                if self.token:
                    self.client = tk.Spotify(self.token)
                    self.playlist_generator = PlaylistGenerator(self.client)
                    # Test connection
                    user = self.client.current_user()
                    return [TextContent(type="text", text=f"✅ Successfully authenticated as {user.display_name or user.id}!")]
                else:
                    return [TextContent(type="text", text="❌ Authentication failed: Could not retrieve token.")]
            except Exception as e:
                return [TextContent(type="text", text=f"❌ Authentication failed: {str(e)}")]

        @self.server.tool("generate_playlist")
        async def generate_playlist(
            prompt: str,
            duration_minutes: int = 60,
            playlist_name: str = "AI Generated Playlist",
        ) -> list[TextContent]:
            """Generate a Spotify playlist based on text prompt and sentiment analysis."""
            try:
                if not self.client or not self.playlist_generator:
                    return [TextContent(
                        type="text", 
                        text="❌ Please authenticate with Spotify first. Use the 'authenticate' tool to get started."
                    )]

                # Refresh token if needed
                if self.token and self.token.is_expiring and self.token.refresh_token:
                    self.token = self.cred.refresh_user_token(self.token.refresh_token)
                    self.client = tk.Spotify(self.token)
                    self.playlist_generator.client = self.client

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
                    text=f"✅ Created playlist: {playlist_name}\n🎵 URL: {playlist_url}\n📊 Analysis: {json.dumps(analysis_result, indent=2)}",
                )]
            except Exception as e:
                return [TextContent(type="text", text=f"❌ Error creating playlist: {str(e)}")]

    async def _analyze_prompt(self, prompt: str) -> Dict[str, Any]:
        """Analyze user prompt for sentiment and context."""
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

    async def run(self) -> None:
        await self.server.run_async("streamable-http", host="0.0.0.0", port=8086)


async def main() -> None:
    server = TekorePlaylistMCP()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())