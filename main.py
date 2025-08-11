import asyncio
import json
import os
import base64
from typing import Dict, Any, Optional
from urllib.parse import quote

import requests
import tekore as tk

from fastmcp import FastMCP
from mcp.types import TextContent
from playlist_generator import PlaylistGenerator
from sentiment_analyzer import SentimentAnalyzer
from utils import parse_duration, detect_language


class SpotifyFastMCP:
    def __init__(self):
        self.server = FastMCP("spotify-playlist-generator")
        self.spotify_client: Optional[tk.Spotify] = None
        self.playlist_generator: Optional[PlaylistGenerator] = None
        self.sentiment_analyzer = SentimentAnalyzer()

        self.client_id = os.getenv("SPOTIFY_CLIENT_ID", '')
        self.client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        self.redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8080/callback")
        self.scope = tk.scope.playlist_modify_public + tk.scope.playlist_modify_private + \
                    tk.scope.user_read_recently_played + tk.scope.user_top_read + \
                    tk.scope.user_library_read

        # Initialize credentials
        self.cred = tk.Credentials(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri
        )

        self._setup_tools()

    def _get_authorize_url(self) -> str:
        """Generate Spotify authorization URL."""
        return self.cred.user_authorisation_url(scope=self.scope)

    def _exchange_code_for_token(self, code: str) -> Optional[tk.Token]:
        """Exchange authorization code for access token."""
        try:
            token = self.cred.request_user_token(code)
            if token:
                self.spotify_client = tk.Spotify(token)
                return token
            return None
        except Exception as e:
            print(f"Token exchange error: {e}")
            return None

    def _setup_tools(self):
        @self.server.tool("validate")
        async def validate() -> str:
            return os.getenv("MY_NUMBER", "")

        @self.server.tool("authenticate")
        async def authenticate() -> list[TextContent]:
            """Generate authentication URL for Spotify."""
            auth_url = self._get_authorize_url()
            return [TextContent(
                type="text", 
                text=f"🔗 Please authenticate with Spotify: {auth_url}\n\nAfter authorization, use the 'handle_callback' tool with the code from the redirect URL."
            )]

        @self.server.tool("handle_callback")
        async def handle_callback(code: str) -> list[TextContent]:
            """Handle Spotify OAuth callback."""
            try:
                token = self._exchange_code_for_token(code)
                if token and self.spotify_client:
                    self.playlist_generator = PlaylistGenerator(self.spotify_client)
                    return [TextContent(type="text", text="✅ Successfully authenticated with Spotify!")]
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
            try:
                if not self.spotify_client:
                    return [TextContent(
                        type="text", 
                        text="❌ Please authenticate with Spotify first. Use the 'authenticate' tool to get started."
                    )]

                # Analyze prompt
                analysis_result = await self._analyze_prompt(prompt)

                if not self.playlist_generator:
                    return [TextContent(type="text", text="❌ Playlist generator not initialized")]

                playlist_url = await self.playlist_generator.create_playlist(
                    analysis_result=analysis_result,
                    duration_minutes=duration_minutes,
                    playlist_name=playlist_name,
                )

                return [
                    TextContent(
                        type="text",
                        text=f"✅ Created playlist: {playlist_name}\n🎵 URL: {playlist_url}\n📊 Analysis: {json.dumps(analysis_result, indent=2)}",
                    )
                ]
            except Exception as e:
                return [TextContent(type="text", text=f"❌ Error creating playlist: {str(e)}")]

        @self.server.tool("refresh_token")
        async def refresh_token() -> list[TextContent]:
            """Refresh the Spotify access token."""
            try:
                if self.spotify_client and hasattr(self.spotify_client, 'token') and self.spotify_client.token:
                    refreshed_token = self.cred.refresh_user_token(self.spotify_client.token.refresh_token)
                    self.spotify_client.token = refreshed_token
                    return [TextContent(type="text", text="✅ Token refreshed successfully!")]
                else:
                    return [TextContent(type="text", text="❌ No active session to refresh. Please authenticate first.")]
            except Exception as e:
                return [TextContent(type="text", text=f"❌ Token refresh failed: {str(e)}")]

    async def _analyze_prompt(self, prompt: str) -> Dict[str, Any]:
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
    server = SpotifyFastMCP()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())