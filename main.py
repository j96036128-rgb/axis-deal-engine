"""
Railway entrypoint for Axis Deal Engine.

This is the ONLY Uvicorn entrypoint used in production.
Binds to 0.0.0.0:$PORT as required by Railway.
"""

import os
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    print(f"Starting Axis Deal Engine on port {port}")

    # Import app here to ensure clean module loading
    from web.app import app

    uvicorn.run(app, host="0.0.0.0", port=port)
