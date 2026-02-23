"""Local state tracker (.mdlm/manifest.json).

Tracks the mapping from local file path → remote doc metadata (id, version,
category, title).  This lets `push` detect new / modified / deleted files
and perform version conflict checks before sending updates to the server.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

_MDLM_DIR = ".mdlm"
_MANIFEST_FILE = ".mdlm/manifest.json"

# manifest entry shape:
# {
#   "id": "<uuid>",
#   "version": <int>,
#   "category": "<category>",
#   "title": "<title>.md"
# }
Entry = Dict[str, Any]
Manifest = Dict[str, Entry]   # key = relative path string


def _manifest_path(root: Path) -> Path:
    return root / _MANIFEST_FILE


def load(root: Optional[Path] = None) -> Manifest:
    """Load manifest from disk.  Returns empty dict if not present."""
    root = root or Path.cwd()
    p = _manifest_path(root)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Error reading manifest: {exc}", file=sys.stderr)
        sys.exit(1)


def save(manifest: Manifest, root: Optional[Path] = None) -> None:
    """Persist manifest to disk."""
    root = root or Path.cwd()
    p = _manifest_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def add_entry(manifest: Manifest, rel_path: str, entry: Entry) -> None:
    manifest[rel_path] = entry


def remove_entry(manifest: Manifest, rel_path: str) -> None:
    manifest.pop(rel_path, None)


def get_entry(manifest: Manifest, rel_path: str) -> Optional[Entry]:
    return manifest.get(rel_path)


def is_initialized(root: Optional[Path] = None) -> bool:
    root = root or Path.cwd()
    return _manifest_path(root).exists()
