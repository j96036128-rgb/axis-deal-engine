#!/usr/bin/env python3
"""
Run the Axis Deal Engine web server.
"""

import uvicorn

from utils.config import Config


def main():
    """Start the web server."""
    config = Config.load()

    print(f"Starting Axis Deal Engine on http://{config.host}:{config.port}")
    print("Press Ctrl+C to stop")

    uvicorn.run(
        "web.app:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
    )


if __name__ == "__main__":
    main()
