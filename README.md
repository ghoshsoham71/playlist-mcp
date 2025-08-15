# 🎵 Spotify AI Playlist Generator

An intelligent MCP (Model Context Protocol) server that generates personalized Spotify playlists using AI. This project combines the power of Google's Gemini AI with Spotify's extensive music catalog to create curated playlists based on natural language prompts.

## ✨ Features

- **AI-Powered Curation**: Uses Google Gemini to generate intelligent search queries and curate track selections
- **Spotify Integration**: Full integration with Spotify's API for authentication, search, and playlist creation
- **Personalized Recommendations**: Analyzes user's listening history for better recommendations
- **Natural Language Processing**: Create playlists using simple prompts like "upbeat workout music" or "chill sunday morning vibes"
- **Flexible Duration**: Specify playlist length from 1 to 300 minutes
- **MCP Server**: Runs as a Model Context Protocol server for easy integration with AI assistants
- **Health Monitoring**: Built-in health checks and logging

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Spotify Premium account (recommended)
- Spotify Developer App credentials
- Google Gemini API key

### Installation

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd spotify-playlist-generator
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

4. **Run the server**
   ```bash
   python main.py
   ```

The server will start on `http://127.0.0.1:10000` by default.

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the project root with the following variables:

```env
# Spotify API Credentials
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret

# Google Gemini API Key
GEMINI_API_KEY=your_gemini_api_key

# Server Configuration
PORT=10000

# Optional: Your phone number for validation
MY_NUMBER=+1234567890
```

### Spotify Developer Setup

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create a new app
3. Note your Client ID and Client Secret
4. Add redirect URI: `http://127.0.0.1:10000/callback`
5. Add the required scopes (handled automatically by the app)

### Google Gemini API Setup

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key
3. Add the key to your `.env` file

## 📖 Usage

### 1. Health Check
```bash
curl http://127.0.0.1:10000/health
```

### 2. Authenticate with Spotify
The server will provide an authentication URL. Visit it to authorize the application.

### 3. Fetch User Data
After authentication, fetch your Spotify listening history for personalized recommendations.

### 4. Generate Playlists
Create playlists using natural language prompts:

- "Energetic workout music for 45 minutes"
- "Chill indie songs for studying"
- "90s rock hits for a road trip"
- "Emotional ballads for a rainy day"

## 🛠️ API Endpoints

### MCP Tools

The server exposes the following MCP tools:

- **`health`**: Check server health status
- **`validate`**: Validate configuration
- **`authenticate`**: Get Spotify authentication URL
- **`fetch_data`**: Fetch and store user's Spotify data
- **`generate_playlist`**: Generate AI-curated playlist

### Generate Playlist Parameters

```json
{
  "prompt": "string (required) - Description of desired playlist",
  "duration_minutes": "integer (optional, default: 60) - Playlist length",
  "playlist_name": "string (optional, default: 'AI Generated Playlist') - Playlist name"
}
```

## 🏗️ Architecture

### Components

1. **Main Server (`main.py`)**: FastMCP server handling HTTP requests and routing
2. **Spotify Handler (`spotify_handler.py`)**: Spotify API integration using Tekore
3. **Playlist Generator (`playlist_generator.py`)**: AI-powered playlist curation using Gemini

### Data Flow

1. User provides natural language prompt
2. Gemini AI generates relevant search queries
3. Spotify API searches for matching tracks
4. System fetches additional recommendations based on user history
5. Gemini AI curates the final track selection
6. Spotify playlist is created and populated

### File Structure

```
├── main.py                 # MCP server and main entry point
├── spotify_handler.py      # Spotify API integration
├── playlist_generator.py   # AI playlist generation logic
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables template
└── README.md              # This file
```

## 📊 Data Storage

The application creates local JSON files for:

- **User Data**: `user_data_YYYYMMDD_HHMMSS.json` - Spotify listening history
- **Playlist Data**: `playlist_YYYYMMDD_HHMMSS.json` - Generated playlist metadata

These files are used to improve recommendations and provide playlist history.

## 🔍 Logging

The application provides comprehensive logging:

- **INFO**: General application flow and successful operations
- **WARNING**: Non-critical issues (e.g., fallback to simple mode)
- **ERROR**: Critical errors and failures

Logs are output to console with timestamps and log levels.

## ⚙️ Fallback Modes

### Without Gemini API
If the Gemini API is unavailable, the system falls back to:
- Simple keyword-based search query generation
- Popularity-based track selection with randomization

### Without User Authentication
The system can still:
- Search for tracks using Spotify's public API
- Create playlists based on search results (with limited personalization)

## 🚨 Error Handling

The application includes robust error handling for:

- **Authentication failures**: Clear error messages and retry mechanisms
- **API rate limits**: Graceful degradation and retries
- **Network issues**: Timeout handling and fallback options
- **Invalid inputs**: Input validation and user-friendly error messages

## 🔒 Privacy & Security

- **No persistent storage**: User tokens are only kept in memory during the session
- **Local data**: All user data is stored locally on your machine
- **Minimal scopes**: Only requests necessary Spotify permissions
- **Environment variables**: Sensitive credentials stored in environment variables

## 📋 Requirements

### Python Dependencies

```
fastmcp>=0.1.0
tekore>=4.0.0
google-generativeai>=0.3.0
asyncio
logging
typing
datetime
json
os
random
glob
```

### System Requirements

- **Memory**: 512MB RAM minimum
- **Storage**: 100MB for application and data files
- **Network**: Stable internet connection for API calls

## 🐛 Troubleshooting

### Common Issues

1. **Authentication Error**
   - Check Spotify credentials in `.env`
   - Verify redirect URI in Spotify app settings
   - Ensure all required scopes are enabled

2. **No Tracks Found**
   - Try more specific or different prompts
   - Check internet connection
   - Verify Spotify API access

3. **Gemini API Errors**
   - Verify API key is correct
   - Check API quota limits
   - System will fallback to simple mode if needed

4. **Port Already in Use**
   - Change PORT in `.env` file
   - Kill existing processes on the port

### Debug Mode

Enable debug logging by modifying the logging level in `main.py`:
```python
logging.basicConfig(level=logging.DEBUG)
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Spotify Web API](https://developer.spotify.com/documentation/web-api/) for music data and playlist management
- [Google Gemini](https://ai.google.dev/) for AI-powered curation
- [Tekore](https://tekore.readthedocs.io/) for elegant Spotify API integration
- [FastMCP](https://github.com/jlowin/fastmcp) for MCP server implementation

## 📞 Support

For questions, issues, or feature requests:

1. Check the [Issues](../../issues) page
2. Create a new issue with detailed information
3. Include logs and error messages when reporting bugs

---

**Made with ❤️ for music lovers and AI enthusiasts**