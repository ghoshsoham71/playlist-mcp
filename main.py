import asyncio
import json
import os
from typing import Dict, Any, Optional
from fastmcp import FastMCP
from mcp.types import Tool, TextContent
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from playlist_generator import PlaylistGenerator
from sentiment_analyzer import SentimentAnalyzer
from utils import parse_duration, detect_language

class SpotifyFastMCP:
    def __init__(self):
        self.server = FastMCP("spotify-playlist-generator")
        self.spotify_client: Optional[spotipy.Spotify] = None
        self.playlist_generator: Optional[PlaylistGenerator] = None
        self.sentiment_analyzer = SentimentAnalyzer()
        
        # Spotify OAuth configuration
        self.spotify_oauth = SpotifyOAuth(
            client_id=os.getenv("SPOTIFY_CLIENT_ID"),
            client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
            redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8080/callback"),
            scope="playlist-modify-public playlist-modify-private user-read-recently-played user-top-read user-library-read"
        )
        
        self._setup_tools()
    
    def _setup_tools(self):
        """Setup MCP tools - these functions will be called externally by MCP clients."""
        
        @self.server.tool("validate")
        async def validate() -> str:
            """Validate server configuration by returning environment variable."""
            return os.getenv('MY_NUMBER', '')
    
        @self.server.tool("generate_playlist")
        async def generate_playlist(
            prompt: str,
            duration_minutes: int = 60,
            playlist_name: str = "AI Generated Playlist"
        ) -> list[TextContent]:
            """
            Generate a Spotify playlist based on user prompt with sentiment analysis.
            
            Args:
                prompt: User's text prompt describing desired mood/theme
                duration_minutes: Target playlist duration in minutes
                playlist_name: Name for the created playlist
            """
            try:
                # Initialize Spotify client if not already done
                if not self.spotify_client:
                    token_info = self.spotify_oauth.get_cached_token()
                    if not token_info:
                        auth_url = self.spotify_oauth.get_authorize_url()
                        return [TextContent(
                            type="text",
                            text=f"Please authenticate with Spotify first: {auth_url}"
                        )]
                    
                    self.spotify_client = spotipy.Spotify(auth=token_info['access_token'])
                    self.playlist_generator = PlaylistGenerator(self.spotify_client)
                
                # Analyze user prompt
                analysis_result = await self._analyze_prompt(prompt)

                if not self.playlist_generator:
                    return [TextContent(type="text", text="❌ Playlist generator not initialized")]
                
                # Generate playlist
                playlist_url = await self.playlist_generator.create_playlist(
                    analysis_result=analysis_result,
                    duration_minutes=duration_minutes,
                    playlist_name=playlist_name
                )
                
                return [TextContent(
                    type="text",
                    text=f"✅ Created playlist: {playlist_name}\n🎵 URL: {playlist_url}\n📊 Analysis: {json.dumps(analysis_result, indent=2)}"
                )]
                
            except Exception as e:
                return [TextContent(
                    type="text",
                    text=f"❌ Error creating playlist: {str(e)}"
                )]
    
    async def _analyze_prompt(self, prompt: str) -> Dict[str, Any]:
        """Analyze user prompt for sentiment, language, and other parameters."""
        # Sentiment analysis
        sentiment_scores = await self.sentiment_analyzer.analyze_sentiment(prompt)
        
        # Language detection
        language = detect_language(prompt)
        
        # Duration parsing (if mentioned in prompt)
        parsed_duration = parse_duration(prompt)
        
        # Emoji analysis
        emoji_sentiment = self.sentiment_analyzer.analyze_emojis(prompt)
        
        return {
            "sentiment": sentiment_scores,
            "language": language,
            "duration_hint": parsed_duration,
            "emoji_sentiment": emoji_sentiment,
            "raw_prompt": prompt
        }
    
    async def handle_spotify_callback(self, code: str):
        """Handle Spotify OAuth callback."""
        try:
            token_info = self.spotify_oauth.get_access_token(code)
            self.spotify_client = spotipy.Spotify(auth=token_info['access_token'])
            self.playlist_generator = PlaylistGenerator(self.spotify_client)
            return "✅ Successfully authenticated with Spotify!"
        except Exception as e:
            return f"❌ Authentication failed: {str(e)}"
    
    async def run(self):
        """Run the MCP server."""
        await self.server.run_async("streamable-http", host="0.0.0.0", port=8086)

async def main():
    server = SpotifyFastMCP()
    await server.run()

if __name__ == "__main__":
    asyncio.run(main())