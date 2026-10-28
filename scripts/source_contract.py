"""Immutable official source contract used by all download methods."""
from pathlib import Path
import re
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def validate_project(project):
    path = Path(project["path"])
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("Unsafe source path")
    if not re.fullmatch(r"[0-9a-f]{40}", project["revision"]):
        raise ValueError("Source revisions must be immutable Git commits")
    url = urlsplit(project["url"])
    if (url.scheme != "https" or url.netloc != "android.googlesource.com"
            or url.query or url.fragment or ".." in Path(url.path).parts):
        raise ValueError("Only official pinned upstreams are allowed")
