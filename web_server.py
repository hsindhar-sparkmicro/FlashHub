#!/usr/bin/env python3
"""
FlashHub Web Server — FastAPI + Uvicorn.

Usage:
    python web_server.py                   # default: localhost:8000
    python web_server.py --host 0.0.0.0   # expose on all interfaces
    python web_server.py --port 9000       # custom port
    python web_server.py --config /path/to/config.json
"""

import argparse
import logging
import os
import sys

# Ensure project root on path when run directly
sys.path.insert(0, os.path.dirname(__file__))

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from src.api.routes import router, init_manager


def build_app(config_path: str = "config.json") -> FastAPI:
    app = FastAPI(
        title="FlashHub",
        description="Remote firmware flashing via pyocd",
        version="1.0.0",
    )

    # Initialise the shared manager with the chosen config
    init_manager(config_path=config_path)

    # API + WebSocket routes
    app.include_router(router)

    # Serve the static SPA
    static_dir = os.path.join(os.path.dirname(__file__), "src", "static")
    if os.path.isdir(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

        @app.get("/", include_in_schema=False)
        async def serve_ui():
            return FileResponse(os.path.join(static_dir, "index.html"))

    return app


def main():
    parser = argparse.ArgumentParser(description="FlashHub Web Server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument("--config", default="config.json", help="Path to config.json")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (dev mode)")
    parser.add_argument("--log-level", default="info", choices=["debug", "info", "warning", "error"])
    args = parser.parse_args()

    logging.basicConfig(level=args.log_level.upper())

    print(f"\n  FlashHub Web UI  →  http://{args.host}:{args.port}")
    print(f"  API docs         →  http://{args.host}:{args.port}/docs")
    print(f"  Config           →  {args.config}\n")

    app = build_app(config_path=args.config)

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
