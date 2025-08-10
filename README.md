# Mood Playlist MCP Server

A Model Context Protocol (MCP) server that generates mood-based music playlists using AI sentiment analysis and the Last.fm API. The server analyzes user queries with emojis, natural language, and preferences to create personalized playlists.

## Features

- 🎭 **AI-Powered Mood Analysis**: Uses Hugging Face transformers for sentiment and emotion detection
- 🌍 **Multi-language Support**: Supports Hindi, English, Punjabi, Bengali, Tamil, and more
- 😀 **Emoji Understanding**: Analyzes emojis to enhance mood detection
- 🎵 **Smart Playlist Generation**: Creates playlists using Last.fm's extensive music database
- 🔗 **Platform Integration**: Provides links for Spotify, Apple Music, YouTube, and Last.fm
- ⚡ **FastAPI Integration**: Full REST API with Swagger documentation

## Prerequisites

1. **Python 3.8+**
2. **Last.fm API Account**: Get your API key and secret from [Last.fm API](https://www.last.fm/api/account/create)

## Installation

1. **Clone or download the code files**

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Set up environment variables**:
```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your Last.fm credentials
LASTFM_API_KEY=your_actual_api_key
LASTFM_SHARED_SECRET=your_actual_shared_secret
```

## Running the Server

### Option 1: As FastAPI Application (Recommended for testing)

```bash
# Run with uvicorn
uvicorn main:mcp.app --host 127.0.0.1 --port 8086 --reload

# Or run directly
python main.py
```

Then access:
- **Swagger UI**: http://127.0.0.1:8086/docs
- **OpenAPI JSON**: http://127.0.0.1:8086/openapi.json

### Option 2: As MCP Server

The server is compatible with MCP clients. Configure your MCP client to connect to:
- **Host**: 127.0.0.1
- **Port**: 8086

## API Endpoints

### 1. Generate Mood Playlist
**POST** `/tools/generate_mood_playlist`

Generate a playlist based on mood query.

**Request Body**:
```json
{
  "query": "I want a 40 minutes playlist of hindi songs that makes me feel 😎"
}
```

**Response**: Complete playlist with streaming platform links and track list.

### 2. Get Supported Options
**POST** `/tools/get_supported_options`

Get available languages, genres, and mood categories.

### 3. Analyze Mood Only
**POST** `/tools/analyze_mood_only`

Analyze mood and emotions without generating a playlist.

**Request Body**:
```json
{
  "query": "I'm feeling really happy today 😊"
}
```

## Example Queries

- `"I want a 40 minutes playlist of hindi songs that makes me feel 😎"`
- `"Generate a sad english playlist for 1 hour"`
- `"Create an energetic punjabi playlist with 10 songs"`
- `"I need romantic bollywood music for 30 minutes"`
- `"Make me a chill playlist 😌 for studying"`

## Supported Languages

- Hindi (हिंदी)
- English
- Punjabi (ਪੰਜਾਬੀ)
- Bengali (বাংলা)
- Tamil (தமிழ்)
- Telugu (తెలుగు)
- Marathi (मराठी)
- Gujarati (ગુજરાતી)
- Spanish
- French
- Korean
- Japanese

## Mood Categories

- Happy
- Sad
- Angry
- Excited
- Calm
- Romantic
- Nostalgic
- Energetic
- Neutral

## Troubleshooting

### Common Issues

1. **"Missing required environment variables"**
   - Ensure LASTFM_API_KEY and LASTFM_SHARED_SECRET are set in your .env file

2. **Model loading errors**
   - The server has fallback modes if AI models fail to load
   - Check internet connection for initial model downloads

3. **No tracks found**
   - Verify Last.fm API credentials are correct
   - Try simpler queries with common genres

4. **Port already in use**
   - Change the port in main.py or kill existing processes on port 8086

### Testing the API

Use the Swagger UI at http://127.0.0.1:8086/docs to test endpoints interactively, or use curl:

```bash
# Test playlist generation
curl -X POST "http://127.0.0.1:8086/tools/generate_mood_playlist" \
     -H "Content-Type: application/json" \
     -d '{"query": "happy bollywood songs for 30 minutes"}'

# Test supported options
curl -X POST "http://127.0.0.1:8086/tools/get_supported_options" \
     -H "Content-Type: application/json" \
     -d '{}'
```

## Architecture

- **config.py**: Configuration management and settings
- **mood_analyzer.py**: AI-powered mood and sentiment analysis
- **playlist_generator.py**: Last.fm API integration and playlist creation
- **main.py**: FastMCP server setup and tool definitions

## Performance Notes

- First run may take longer due to AI model downloads (~1-2GB)
- Models are cached locally after first download
- The server includes rate limiting and error handling for API calls
- Fallback modes ensure functionality even if AI models fail to load