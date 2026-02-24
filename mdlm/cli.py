"""mdlm CLI — five commands for interacting with your knowledge base.

Commands
--------
  configure   Save your API key securely (~/.config/mdlm/config, mode 0600)
  clone       Download your knowledge base to ./knowledge/
  pull        Refresh docs from the server (overwrites local changes)
  status      Show new / modified / deleted files vs the server
  push        Upload local changes back to the server

Usage examples
--------------
  mdlm configure
  mdlm clone
  mdlm clone --category architecture
  mdlm status
  mdlm push --message "update auth docs"
  mdlm pull
"""

import argparse
import getpass
import os
import sys
from pathlib import Path
from typing import List, Optional

from mdlm import __version__
from mdlm import manifest as mf
from mdlm.api import ApiClient, ApiError, VALID_CATEGORIES
from mdlm.config import get_api_url, save_api_key

# Where cloned docs live relative to cwd
_KNOWLEDGE_DIR = "knowledge"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_filename(name: str) -> str:
    """Sanitize a title so it's safe to use as a filename."""
    # Replace path separators and null bytes; strip leading dots/spaces
    for ch in ("/", "\\", "\x00"):
        name = name.replace(ch, "_")
    return name.strip(". ") or "_"


def _local_path(category: str, title: str) -> str:
    """Return the relative path for a doc: knowledge/<category>/<title>"""
    return os.path.join(_KNOWLEDGE_DIR, _safe_filename(category), _safe_filename(title))


def _read_local(rel_path: str) -> Optional[str]:
    p = Path(rel_path)
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8")


def _write_local(rel_path: str, content: str) -> None:
    p = Path(rel_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_configure(args: argparse.Namespace) -> None:
    """Prompt for the API key and store it securely."""
    print("Find your API key on the markdownlm dashboard under Settings.")
    print("It will NOT be echoed to the terminal.")
    key = getpass.getpass("API key (mdlm_...): ").strip()
    if not key:
        print("Error: No key entered.", file=sys.stderr)
        sys.exit(1)
    save_api_key(key)
    print("API key saved to ~/.config/mdlm/config (permissions: 0600).")


def cmd_clone(args: argparse.Namespace) -> None:
    """Download knowledge base docs to ./knowledge/."""
    if mf.is_initialized():
        print(
            "Error: This directory already has a .mdlm/manifest.json.\n"
            "Use `mdlm pull` to refresh existing docs.",
            file=sys.stderr,
        )
        sys.exit(1)

    category: Optional[str] = args.category
    if category and category not in VALID_CATEGORIES:
        print(
            f"Error: Unknown category '{category}'.\n"
            f"Valid categories: {', '.join(sorted(VALID_CATEGORIES))}",
            file=sys.stderr,
        )
        sys.exit(1)

    client = ApiClient()
    print(f"Fetching docs from {get_api_url()} …")
    try:
        docs = client.list_docs(category=category)
    except ApiError as e:
        print(f"Error: {e.message}", file=sys.stderr)
        sys.exit(1)

    if not docs:
        print("No docs found. Your knowledge base is empty.")
        return

    import hashlib

    manifest: mf.Manifest = {}
    written = 0
    for doc in docs:
        rel = _local_path(doc["category"], doc["title"])
        content = doc.get("content", "")
        _write_local(rel, content)
        mf.add_entry(
            manifest,
            rel,
            {
                "id": doc["id"],
                "version": doc["version"],
                "category": doc["category"],
                "title": doc["title"],
                "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            },
        )
        written += 1

    mf.save(manifest)
    print(f"Cloned {written} doc(s) → ./{_KNOWLEDGE_DIR}/")
    print("Edit files, then run `mdlm push` to upload changes.")


def cmd_pull(args: argparse.Namespace) -> None:
    """Re-fetch all tracked docs from the server, overwriting local files."""
    if not mf.is_initialized():
        print(
            "Error: No manifest found. Run `mdlm clone` first.",
            file=sys.stderr,
        )
        sys.exit(1)

    manifest = mf.load()
    if not manifest:
        print("Nothing to pull — manifest is empty.")
        return

    import hashlib

    client = ApiClient()
    updated = 0
    errors = 0
    for rel_path, entry in list(manifest.items()):
        try:
            doc = client.get_doc(entry["id"])
        except ApiError as e:
            print(f"  error pulling {rel_path}: {e.message}", file=sys.stderr)
            errors += 1
            continue

        content = doc.get("content", "")
        _write_local(rel_path, content)
        entry["version"] = doc["version"]
        entry["title"] = doc["title"]
        entry["category"] = doc["category"]
        entry["content_hash"] = hashlib.sha256(content.encode("utf-8")).hexdigest()
        updated += 1

    mf.save(manifest)
    print(f"Pulled {updated} doc(s)." + (f" {errors} error(s)." if errors else ""))


def cmd_status(args: argparse.Namespace) -> None:
    """Show local changes vs the manifest (does NOT hit the network)."""
    if not mf.is_initialized():
        print(
            "Error: No manifest found. Run `mdlm clone` first.",
            file=sys.stderr,
        )
        sys.exit(1)

    manifest = mf.load()

    # Collect all local .md files under knowledge/
    knowledge_dir = Path(_KNOWLEDGE_DIR)
    local_files = set()
    if knowledge_dir.exists():
        for p in knowledge_dir.rglob("*.md"):
            local_files.add(str(p))

    tracked = set(manifest.keys())

    new_files: List[str] = []
    modified: List[str] = []
    deleted: List[str] = []

    # Check tracked files for modifications or deletions
    for rel_path in tracked:
        content = _read_local(rel_path)
        if content is None:
            deleted.append(rel_path)
        else:
            # We don't have a local cached copy of the original content,
            # so we compare against the manifest's known content by re-reading.
            # Mark as modified if the file exists — user must have edited it.
            # (After clone/pull, mtime would be a better heuristic, but keeping
            #  it simple: any tracked file present is "possibly modified".)
            # To give accurate output we store a content hash in the manifest.
            entry = manifest[rel_path]
            stored_hash = entry.get("content_hash")
            if stored_hash is not None:
                import hashlib
                current_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                if current_hash != stored_hash:
                    modified.append(rel_path)
            else:
                # Old manifest without hashes — can't tell; mark unknown
                pass

    # Check for new untracked .md files
    for rel_path in local_files:
        if rel_path not in tracked:
            new_files.append(rel_path)

    if not new_files and not modified and not deleted:
        print("Nothing to push — no changes detected.")
        return

    if new_files:
        print("New (will be created on push):")
        for f in sorted(new_files):
            print(f"  + {f}")
    if modified:
        print("Modified (will be updated on push):")
        for f in sorted(modified):
            print(f"  M {f}")
    if deleted:
        print("Deleted locally (will be removed on push with --delete):")
        for f in sorted(deleted):
            print(f"  D {f}")


def cmd_push(args: argparse.Namespace) -> None:
    """Upload local changes to the server."""
    if not mf.is_initialized():
        print(
            "Error: No manifest found. Run `mdlm clone` first.",
            file=sys.stderr,
        )
        sys.exit(1)

    manifest = mf.load()
    knowledge_dir = Path(_KNOWLEDGE_DIR)
    change_reason: Optional[str] = args.message
    category_filter: Optional[str] = args.category

    if category_filter and category_filter not in VALID_CATEGORIES:
        print(
            f"Error: Unknown category '{category_filter}'.\n"
            f"Valid categories: {', '.join(sorted(VALID_CATEGORIES))}",
            file=sys.stderr,
        )
        sys.exit(1)

    client = ApiClient()
    import hashlib

    created = updated = deleted_count = errors = 0

    # 1. Handle tracked files (update or delete)
    for rel_path, entry in list(manifest.items()):
        if category_filter and entry.get("category") != category_filter:
            continue

        content = _read_local(rel_path)

        # --- Deleted locally ---
        if content is None:
            if args.delete:
                try:
                    client.delete_doc(entry["id"])
                    mf.remove_entry(manifest, rel_path)
                    print(f"  deleted  {rel_path}")
                    deleted_count += 1
                except ApiError as e:
                    print(f"  error deleting {rel_path}: {e.message}", file=sys.stderr)
                    errors += 1
            else:
                print(
                    f"  skipped  {rel_path} (deleted locally; re-run with --delete to remove remotely)"
                )
            continue

        # --- Check if content changed (uses stored hash) ---
        stored_hash = entry.get("content_hash")
        current_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if stored_hash == current_hash:
            continue  # unchanged

        # --- Version conflict check ---
        try:
            remote_doc = client.get_doc(entry["id"])
        except ApiError as e:
            print(f"  error checking {rel_path}: {e.message}", file=sys.stderr)
            errors += 1
            continue

        remote_version = remote_doc.get("version", 0)
        local_version = entry.get("version", 0)
        if remote_version != local_version:
            print(
                f"  conflict {rel_path}: "
                f"local version {local_version} != server version {remote_version}.\n"
                f"           Run `mdlm pull` to get the latest, then re-apply your edits.",
                file=sys.stderr,
            )
            errors += 1
            continue

        # --- Push update ---
        try:
            doc = client.update_doc(
                entry["id"],
                entry["title"],
                content,
                entry["category"],
                change_reason=change_reason,
            )
            entry["version"] = doc["version"]
            entry["content_hash"] = current_hash
            mf.save(manifest)
            print(f"  updated  {rel_path} (v{doc['version']})")
            updated += 1
        except ApiError as e:
            print(f"  error updating {rel_path}: {e.message}", file=sys.stderr)
            errors += 1

    # 2. Handle new untracked .md files under knowledge/
    if knowledge_dir.exists():
        for p in sorted(knowledge_dir.rglob("*.md")):
            rel_path = str(p)
            if rel_path in manifest:
                continue  # already handled above

            # Infer category from directory name
            parts = p.relative_to(knowledge_dir).parts
            inferred_category = parts[0] if len(parts) > 1 else "general"
            if inferred_category not in VALID_CATEGORIES:
                inferred_category = "general"

            if category_filter and inferred_category != category_filter:
                continue

            content = p.read_text(encoding="utf-8")
            title = p.name  # already ends in .md

            try:
                doc = client.create_doc(title, content, inferred_category)
                current_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                mf.add_entry(
                    manifest,
                    rel_path,
                    {
                        "id": doc["id"],
                        "version": doc["version"],
                        "category": doc["category"],
                        "title": doc["title"],
                        "content_hash": current_hash,
                    },
                )
                mf.save(manifest)
                print(f"  created  {rel_path}")
                created += 1
            except ApiError as e:
                print(f"  error creating {rel_path}: {e.message}", file=sys.stderr)
                errors += 1

    # Summary
    parts = []
    if created:
        parts.append(f"{created} created")
    if updated:
        parts.append(f"{updated} updated")
    if deleted_count:
        parts.append(f"{deleted_count} deleted")
    if errors:
        parts.append(f"{errors} error(s)")

    if parts:
        print("Push complete: " + ", ".join(parts) + ".")
    else:
        print("Nothing to push — no changes detected.")


def cmd_query(args: argparse.Namespace) -> None:
    """Query the knowledge base for documented rules and patterns."""
    query: str = args.query
    category: str = args.category

    if category not in VALID_CATEGORIES:
        print(
            f"Error: Unknown category '{category}'.\n"
            f"Valid categories: {', '.join(sorted(VALID_CATEGORIES))}",
            file=sys.stderr,
        )
        sys.exit(1)

    client = ApiClient()
    try:
        result = client.query_knowledge_base(query, category)
        print(result.get("answer", "No answer found."))
        if result.get("gap_detected"):
            print("\nNote: A documentation gap was detected for this query.", file=sys.stderr)
    except ApiError as e:
        print(f"Error: {e.message}", file=sys.stderr)
        sys.exit(1)


def cmd_validate(args: argparse.Namespace) -> None:
    """Validate code against documented architectural and style rules."""
    code_input: str = args.code
    task: str = args.task
    category: str = args.category

    # Check if code_input is a file path
    code_path = Path(code_input)
    if code_path.exists() and code_path.is_file():
        code = code_path.read_text(encoding="utf-8")
    else:
        # Treat it as inline code
        code = code_input

    if category not in VALID_CATEGORIES:
        print(
            f"Error: Unknown category '{category}'.\n"
            f"Valid categories: {', '.join(sorted(VALID_CATEGORIES))}",
            file=sys.stderr,
        )
        sys.exit(1)

    client = ApiClient()
    try:
        result = client.validate_code(code, task, category)
        
        # Print status and violations
        status = result.get("status", "unknown")
        print(f"Status: {status.upper()}")
        
        violations = result.get("violations", [])
        if violations:
            print(f"\nViolations found ({len(violations)}):")
            for i, violation in enumerate(violations, 1):
                print(f"  {i}. {violation.get('rule')}")
                print(f"     Message: {violation.get('message')}")
                if violation.get("fix_suggestion"):
                    print(f"     Fix: {violation['fix_suggestion']}")
        else:
            print("No violations found.")
        
        fix_suggestion = result.get("fix_suggestion")
        if fix_suggestion:
            print(f"\nOverall suggestion: {fix_suggestion}")
            
    except ApiError as e:
        print(f"Error: {e.message}", file=sys.stderr)
        sys.exit(1)


def cmd_resolve_gap(args: argparse.Namespace) -> None:
    """Detect and log documentation gaps for architectural decisions."""
    question: str = args.question
    category: str = args.category

    if category not in VALID_CATEGORIES:
        print(
            f"Error: Unknown category '{category}'.\n"
            f"Valid categories: {', '.join(sorted(VALID_CATEGORIES))}",
            file=sys.stderr,
        )
        sys.exit(1)

    client = ApiClient()
    try:
        result = client.resolve_gap(question, category)
        
        gap_detected = result.get("gap_detected", False)
        resolution_mode = result.get("resolution_mode", "none")
        
        print(f"Gap detected: {gap_detected}")
        print(f"Resolution mode: {resolution_mode}")
        
        if result.get("resolution"):
            print(f"\nResolution: {result['resolution']}")
        
        if result.get("gap_id"):
            print(f"Gap ID: {result['gap_id']}")
            
    except ApiError as e:
        print(f"Error: {e.message}", file=sys.stderr)
        sys.exit(1)

    # Exit with error code if gap was detected and mode is ask_user
    if gap_detected and resolution_mode == "ask_user":
        sys.exit(1)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mdlm",
        description="markdownlm knowledge base CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"mdlm {__version__}")

    sub = parser.add_subparsers(dest="command", metavar="<command>")
    sub.required = True

    # configure
    sub.add_parser("configure", help="Save your API key securely")

    # clone
    p_clone = sub.add_parser("clone", help="Download your knowledge base")
    p_clone.add_argument(
        "--category",
        metavar="CATEGORY",
        help=f"Only clone this category ({', '.join(sorted(VALID_CATEGORIES))})",
    )

    # pull
    sub.add_parser("pull", help="Refresh docs from the server (overwrites local)")

    # status
    sub.add_parser("status", help="Show local changes")

    # push
    p_push = sub.add_parser("push", help="Upload local changes to the server")
    p_push.add_argument(
        "--message", "-m",
        metavar="MSG",
        help="Change reason recorded in version history",
    )
    p_push.add_argument(
        "--category",
        metavar="CATEGORY",
        help="Only push files in this category",
    )
    p_push.add_argument(
        "--delete",
        action="store_true",
        help="Also delete docs that have been removed locally",
    )

    # query
    p_query = sub.add_parser("query", help="Query the knowledge base")
    p_query.add_argument(
        "query",
        metavar="QUERY",
        help="Your question about architecture, patterns, or rules",
    )
    p_query.add_argument(
        "--category",
        metavar="CATEGORY",
        default="general",
        help=f"The domain to query ({', '.join(sorted(VALID_CATEGORIES))}; default: general)",
    )

    # validate
    p_validate = sub.add_parser("validate", help="Validate code against rules")
    p_validate.add_argument(
        "code",
        metavar="CODE",
        help="The code snippet to validate (can be a file path or inline code)",
    )
    p_validate.add_argument(
        "--task", "-t",
        metavar="TASK",
        required=True,
        help="One-sentence description of what the code does",
    )
    p_validate.add_argument(
        "--category", "-c",
        metavar="CATEGORY",
        default="general",
        help=f"The domain to validate against ({', '.join(sorted(VALID_CATEGORIES))}; default: general)",
    )

    # resolve-gap
    p_gap = sub.add_parser("resolve-gap", help="Resolve documentation gaps")
    p_gap.add_argument(
        "question",
        metavar="QUESTION",
        help="The undocumented decision or question",
    )
    p_gap.add_argument(
        "--category", "-c",
        metavar="CATEGORY",
        default="general",
        help=f"The domain ({', '.join(sorted(VALID_CATEGORIES))}; default: general)",
    )

    return parser


_COMMANDS = {
    "configure": cmd_configure,
    "clone": cmd_clone,
    "pull": cmd_pull,
    "status": cmd_status,
    "push": cmd_push,
    "query": cmd_query,
    "validate": cmd_validate,
    "resolve-gap": cmd_resolve_gap,
}


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    _COMMANDS[args.command](args)


if __name__ == "__main__":
    main()
