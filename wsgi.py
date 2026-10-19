"""WSGI entrypoint for Vercel's Flask runtime."""

from app import create_app


app = create_app()
