#!/usr/bin/env python3
"""
Alternative server runner for development and testing
"""

import uvicorn
import logging
from main import mcp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("🚀 Starting Mood Playlist Server with uvicorn...")
    logger.info("📊 Swagger UI will be available at: http://127.0.0.1:8090/docs")
    
    # Run with uvicorn for better development experience
    uvicorn.run(
        "main",
        host="127.0.0.1",
        port=8090,
        reload=True,
        log_level="info"
    )