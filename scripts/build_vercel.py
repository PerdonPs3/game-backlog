"""Publish Flask's static assets under the same /static URLs on Vercel."""

from pathlib import Path
from shutil import copytree


def build_static(project_root):
    source = project_root / "app" / "static"
    destination = project_root / "public" / "static"
    copytree(source, destination, dirs_exist_ok=True)
    return destination


if __name__ == "__main__":
    build_static(Path(__file__).resolve().parents[1])
    print("Static assets prepared in public/static.")
