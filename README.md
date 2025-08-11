# Spotify MCP Playlist Generator

A Model Context Protocol (MCP) server that generates Spotify playlists based on sentiment analysis of user prompts. Designed to work with WhatsApp bots and other messaging platforms.

## Features

- 🎵 **Smart Playlist Generation**: Creates playlists using 30% user history + 70% Spotify recommendations
- 🧠 **Sentiment Analysis**: Uses HuggingFace models to analyze text and emoji sentiment
- 🌍 **Multi-language Support**: Detects language and adapts recommendations
- ⏱️ **Duration Control**: Parses duration from natural language ("45 minutes", "2 hours")
- 🔐 **OAuth Integration**: Secure Spotify authentication
- 📱 **WhatsApp Ready**: Designed for messaging bot integration

## Installation

1. **Clone the repository**
```bash
git clone <your-repo>
cd spotify-mcp
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Set up Spotify App**
   - Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
   - Create a new app
   - Note your Client ID and Client Secret
   - Set redirect URI to `http://localhost:8080/callback`

4. **Configure environment variables**
```bash
export SPOTIFY_CLIENT_ID="your_client_id"
export SPOTIFY_CLIENT_SECRET="your_client_secret"
export SPOTIFY_REDIRECT_URI="http://localhost:8080/callback"
```

## Usage

### Basic MCP Server

```python
from main import SpotifyMCPServer
import asyncio

async def main():
    server = SpotifyMCPServer()
    await server.run()

asyncio.run(main())
```

### Tool Usage

The server exposes one main tool: `generate_playlist`

```python
# Example tool call
result = await mcp_client.call_tool(
    "generate_playlist",
    {
        "prompt": "Happy workout music with some rock 🎸💪",
        "duration_minutes": 45,
        "playlist_name": "Gym Motivation"
    }
)
```

### WhatsApp Integration Example

```
User: "Create me a chill playlist for studying 📚"
Bot: "Let me analyze your request..."
Bot: "✅ Created playlist: Study Focus
      🎵 URL: https://open.spotify.com/playlist/xyz
      📊 30% from your history, 70% new recommendations"
```

## How It Works

### 1. Sentiment Analysis
- Analyzes text using lightweight HuggingFace models
- Processes emojis separately for emotional context
- Maps emotions to Spotify audio features (valence, energy, danceability)

### 2. Playlist Generation
- **30% User History**: Pulls from user's top tracks and recent listening
- **70% Recommendations**: Uses Spotify's recommendation API with sentiment-based parameters
- Filters and combines tracks to create one consolidated playlist

### 3. Audio Features Mapping
```python
sentiment_mapping = {
    "joy": {"valence": 0.8, "energy": 0.7, "danceability": 0.8},
    "sadness": {"valence": 0.2, "energy": 0.3, "danceability": 0.4},
    "anger": {"valence": 0.3, "energy": 0.9, "danceability": 0.6},
    # ... more mappings
}
```

## API Reference

### generate_playlist

**Parameters:**
- `prompt` (str): User's description of desired music
- `duration_minutes` (int, default=60): Target playlist length
- `playlist_name` (str, default="AI Generated Playlist"): Playlist name

**Returns:**
- Spotify playlist URL
- Analysis breakdown
- Success/error status

## File Structure

```
spotify-mcp/
├── main.py                 # Main MCP server
├── spotify_handler.py      # Spotify OAuth & API wrapper
├── playlist_generator.py   # Core playlist creation logic
├── sentiment_analyzer.py   # HuggingFace sentiment analysis
├── utils.py               # Helper functions
├── example_usage.py       # Usage examples
├── requirements.txt       # Dependencies
└── README.md             # This file
```

## Authentication Flow

1. User requests playlist creation
2. If not authenticated, bot provides Spotify OAuth URL
3. User authorizes and is redirected with code
4. Server exchanges code for access token
5. Token is cached for future requests
6. User can now create playlists

## Example Prompts

- `"Happy workout music for 45 minutes 🏋️‍♂️"`
- `"Sad songs for rainy day mood 😢🌧️"`
- `"Party music, something energetic for tonight 🎉"`
- `"Focus music for studying, instrumental preferred"`
- `"Road trip classics, rock vibes for 2 hours"`

## Supported Emotions

- **Joy**: Upbeat, positive, energetic music
- **Sadness**: Melancholic, slow, emotional tracks
- **Anger**: Intense, aggressive, powerful music
- **Fear**: Dark, mysterious, atmospheric sounds
- **Surprise**: Experimental, unique, eclectic tracks
- **Neutral**: Balanced, mainstream music

## Error Handling

- Graceful fallbacks when Spotify API fails
- Alternative search methods for recommendations
- Comprehensive logging for debugging
- User-friendly error messages

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if needed
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Troubleshooting

**Common Issues:**

1. **Authentication Errors**: Check Spotify app credentials and redirect URI
2. **Model Loading**: Ensure HuggingFace models download correctly
3. **API Limits**: Spotify has rate limits - implement backoff if needed
4. **Token Expiry**: Implement token refresh logic for production use

**Debug Mode:**
Set environment variable `DEBUG=1` for verbose logging.