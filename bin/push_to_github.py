import os
import sys
import json
import base64
import hashlib
import urllib.request
from pathlib import Path

GITHUB_REPO = "constantingrandidier-prog/study-life-orchester"
BRANCH = "main"


def _load_github_token() -> str:
    env_tok = os.environ.get("GITHUB_TOKEN", "").strip()
    if env_tok:
        return env_tok
    token_file = Path(__file__).resolve().parent.parent / ".token"
    if token_file.exists():
        try:
            return token_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return ""


GITHUB_TOKEN = _load_github_token()

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "AntigravitySync"
}


IGNORED_DIRS = {".venv", ".git", "git", "__pycache__", ".pytest_cache", "scratch", ".system_generated"}
IGNORED_EXTENSIONS = {".pyc", ".log", ".lock", ".db", ".anki2", ".exe", ".dll", ".zip", ".tar", ".gz", ".iso"}
IGNORED_FILES = {"study_life.db", "studylife.db", "cloudflared.exe", ".token"}
MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB

def gh_request(url, data=None, method="GET"):
    req = urllib.request.Request(url, headers=HEADERS, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(data).encode("utf-8")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def git_blob_sha(content: bytes) -> str:
    header = f"blob {len(content)}\0".encode("utf-8")
    return hashlib.sha1(header + content).hexdigest()

VOLATILE_SNAPSHOT_KEYS = {
    "generated_at",
    "synced_at",
    "cached_at",
    "timestamp",
    "last_synced",
    "last_updated",
    "scanned_at",
    "computed_at",
    "updated_at",
    "snapshot_timestamp",
    "generated_for_date",
}


def _strip_volatile_json(obj):
    if isinstance(obj, dict):
        return {
            k: _strip_volatile_json(v)
            for k, v in obj.items()
            if k not in VOLATILE_SNAPSHOT_KEYS
        }
    if isinstance(obj, list):
        return [_strip_volatile_json(x) for x in obj]
    return obj


def _is_cached_snapshot_json(rel_path: str) -> bool:
    name = Path(rel_path).name.lower()
    return rel_path.startswith("app/data/") and name.endswith(".json") and (
        name.startswith("cached_") or name.endswith("_snapshot.json")
    )


def _snapshot_semantically_equal(local_bytes: bytes, remote_sha: str) -> bool:
    try:
        local_obj = json.loads(local_bytes.decode("utf-8"))
        blob = gh_request(f"https://api.github.com/repos/{GITHUB_REPO}/git/blobs/{remote_sha}")
        remote_raw = base64.b64decode(blob["content"]).decode("utf-8")
        remote_obj = json.loads(remote_raw)
        return _strip_volatile_json(local_obj) == _strip_volatile_json(remote_obj)
    except Exception:
        return False


def find_changed_files(root_dir: Path, remote_tree: dict):
    changed_or_new = []
    
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Prune ignored directories in-place so os.walk doesn't even enter them
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS and not d.startswith(".")]

        rel_dir = Path(dirpath).relative_to(root_dir)
        if any(ig in rel_dir.parts for ig in IGNORED_DIRS):
            continue

        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext in IGNORED_EXTENSIONS or fname in IGNORED_FILES:
                continue

            full_path = Path(dirpath) / fname
            try:
                st = full_path.stat()
                if st.st_size > MAX_FILE_BYTES or st.st_size == 0:
                    continue
                content = full_path.read_bytes()
            except Exception:
                continue

            rel_path = full_path.relative_to(root_dir).as_posix()
            local_sha = git_blob_sha(content)
            remote_sha = remote_tree.get(rel_path)

            if remote_sha != local_sha:
                if remote_sha and _is_cached_snapshot_json(rel_path) and _snapshot_semantically_equal(content, remote_sha):
                    print(f"   = [Snapshot semantically unchanged, skipped] {rel_path}")
                    continue
                changed_or_new.append((rel_path, content, local_sha))

    return changed_or_new

def refresh_local_snapshots(root_dir: Path):
    """Refreshes all JSON snapshots from the local Anki collection so Render is 100% up to date."""
    print("0. Refreshing local Anki snapshots for Render...")
    try:
        sys.path.insert(0, str(root_dir))
        from app.services.anki_desktop_sync import read_live_anki_desktop_state
        read_live_anki_desktop_state()
        print("   + anki desktop live state snapshot refreshed")
    except Exception as e:
        print(f"   [Snapshot warning] anki_desktop_sync: {e}")

    try:
        sys.path.insert(0, str(root_dir))
        from app.services.workload_forecast import get_workload_forecast
        get_workload_forecast()
        print("   + workload forecast snapshot refreshed")
    except Exception as e:
        print(f"   [Snapshot warning] workload_forecast: {e}")

    try:
        from app.services.anki_deck_stats import get_detailed_deck_stats
        get_detailed_deck_stats()
        print("   + deck stats snapshot refreshed")
    except Exception as e:
        print(f"   [Snapshot warning] anki_deck_stats: {e}")

    try:
        from app.services.curriculum_roadmap_service import generate_curriculum_roadmap
        generate_curriculum_roadmap()
        print("   + curriculum roadmap snapshot refreshed")
    except Exception as e:
        print(f"   [Snapshot warning] curriculum_roadmap: {e}")

    try:
        from app.services.card_yield_engine import scan_all_cards_in_collection
        scan_all_cards_in_collection()
        print("   + card yield & kprim traps snapshot refreshed")
    except Exception as e:
        print(f"   [Snapshot warning] card_yield_engine: {e}")

    try:
        from app.services.slide_cross_matcher import build_slide_cross_match_index
        build_slide_cross_match_index()
        print("   + slide cross-match snapshot refreshed")
    except Exception as e:
        print(f"   [Snapshot warning] slide_cross_matcher: {e}")

    try:
        from app.services.actionable_yield_service import get_ranked_actionable_yield_list
        get_ranked_actionable_yield_list()
        print("   + actionable yield ROI snapshot refreshed")
    except Exception as e:
        print(f"   [Snapshot warning] actionable_yield_service: {e}")

    try:
        from app.services.exam_score_simulator import get_full_exam_simulation
        get_full_exam_simulation()
        print("   + exam simulation snapshot refreshed")
    except Exception as e:
        print(f"   [Snapshot warning] exam_score_simulator: {e}")

    try:
        from app.services.anki_backlog_triage import calculate_backlog_triage
        calculate_backlog_triage()
        print("   + backlog triage snapshot refreshed")
    except Exception as e:
        print(f"   [Snapshot warning] backlog_triage: {e}")

def push_auto(commit_message: str):
    root_dir = Path(__file__).resolve().parent.parent
    refresh_local_snapshots(root_dir)

    try:
        print("1. Fetching current branch ref...")
        ref_data = gh_request(f"https://api.github.com/repos/{GITHUB_REPO}/git/ref/heads/{BRANCH}")
        latest_commit_sha = ref_data["object"]["sha"]
        print(f"   Latest commit: {latest_commit_sha}")

        print("2. Fetching remote tree...")
        commit_data = gh_request(f"https://api.github.com/repos/{GITHUB_REPO}/git/commits/{latest_commit_sha}")
        base_tree_sha = commit_data["tree"]["sha"]
        tree_data = gh_request(f"https://api.github.com/repos/{GITHUB_REPO}/git/trees/{base_tree_sha}?recursive=1")
        remote_tree = {item["path"]: item["sha"] for item in tree_data.get("tree", []) if item.get("type") == "blob"}

        changed_files = find_changed_files(root_dir, remote_tree)

        if not changed_files:
            print("   No modified or new files detected. Remote is completely up to date.")
        else:
            print(f"3. Uploading {len(changed_files)} changed or new files to GitHub:")
            tree_items = []
            for rel_path, content, _ in changed_files:
                blob_data = gh_request(
                    f"https://api.github.com/repos/{GITHUB_REPO}/git/blobs",
                    data={"content": base64.b64encode(content).decode("utf-8"), "encoding": "base64"},
                    method="POST"
                )
                blob_sha = blob_data["sha"]
                print(f"   + {rel_path} -> {blob_sha[:10]}")
                tree_items.append({
                    "path": rel_path,
                    "mode": "100644",
                    "type": "blob",
                    "sha": blob_sha
                })

            print("4. Creating new tree...")
            new_tree = gh_request(
                f"https://api.github.com/repos/{GITHUB_REPO}/git/trees",
                data={"base_tree": base_tree_sha, "tree": tree_items},
                method="POST"
            )
            new_tree_sha = new_tree["sha"]

            print("5. Creating commit...")
            new_commit = gh_request(
                f"https://api.github.com/repos/{GITHUB_REPO}/git/commits",
                data={
                    "message": commit_message,
                    "tree": new_tree_sha,
                    "parents": [latest_commit_sha]
                },
                method="POST"
            )
            new_commit_sha = new_commit["sha"]
            print(f"   New commit SHA: {new_commit_sha}")

            print("6. Updating branch ref...")
            gh_request(
                f"https://api.github.com/repos/{GITHUB_REPO}/git/refs/heads/{BRANCH}",
                data={"sha": new_commit_sha, "force": False},
                method="PATCH"
            )
            print(f"   Successfully pushed to {BRANCH} ({new_commit_sha})!")
            latest_commit_sha = new_commit_sha
    except Exception as e:
        print(f"   [GitHub Push Warning]: {e} (Token may need renewal). Proceeding to Render deploy...")
        latest_commit_sha = "local-sync"

    print("7. Automatically triggering Render deployment...")
    try:
        from deploy_render import trigger_deploy
        trigger_deploy()
    except Exception as e:
        print("   Note on render trigger:", e)

    return latest_commit_sha

if __name__ == "__main__":
    msg = sys.argv[1] if len(sys.argv) > 1 else "chore: automatic sync"
    push_auto(msg)
