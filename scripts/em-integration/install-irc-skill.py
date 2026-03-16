"""
Karma Kadabra V2 — IRC Skill Installer

Installs the IRC agent skill and per-agent irc-config.json into all
40 KK agent workspaces.

For each workspace:
  1. Copies skills/irc-agent/ to {workspace}/skills/irc-agent/
  2. Generates {workspace}/irc-config.json with unique nick

Usage:
  python install-irc-skill.py                     # Install to all workspaces
  python install-irc-skill.py --agent kk-elboorja # Single workspace
  python install-irc-skill.py --dry-run            # Preview only
  python install-irc-skill.py --server irc.meshrelay.xyz --port 6667
"""

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
SKILLS_SRC = BASE_DIR / "skills" / "irc-agent"
WORKSPACES_DIR = BASE_DIR / "data" / "workspaces"

DEFAULT_SERVER = "irc.meshrelay.xyz"
DEFAULT_PORT = 6667
DEFAULT_TLS_PORT = 6697
DEFAULT_CHANNELS = ["#Agents"]
DEFAULT_REALNAME = "Karma Kadabra Agent - Ultravioleta DAO"


def generate_irc_config(
    agent_name: str,
    server: str = DEFAULT_SERVER,
    port: int = DEFAULT_PORT,
    tls: bool = False,
    channels: list[str] | None = None,
) -> dict:
    """Generate an IRC config for one agent."""
    return {
        "server": server,
        "port": port,
        "tls": tls,
        "tls_port": DEFAULT_TLS_PORT,
        "nick": agent_name,
        "channels": channels or DEFAULT_CHANNELS,
        "realname": DEFAULT_REALNAME,
        "auto_join": True,
    }


def install_to_workspace(
    workspace_dir: Path,
    server: str,
    port: int,
    tls: bool,
    channels: list[str],
    dry_run: bool = False,
) -> bool:
    """Install IRC skill + config to a single workspace.

    Returns True on success.
    """
    agent_name = workspace_dir.name  # e.g., kk-elboorja

    # 1. Copy skill directory
    skill_dest = workspace_dir / "skills" / "irc-agent"
    if dry_run:
        print(f"  [DRY RUN] Would copy {SKILLS_SRC} -> {skill_dest}")
    else:
        skill_dest.parent.mkdir(parents=True, exist_ok=True)
        if skill_dest.exists():
            shutil.rmtree(skill_dest)
        shutil.copytree(SKILLS_SRC, skill_dest)

    # 2. Generate irc-config.json
    config = generate_irc_config(
        agent_name=agent_name,
        server=server,
        port=port,
        tls=tls,
        channels=channels,
    )
    config_path = workspace_dir / "irc-config.json"

    if dry_run:
        print(f"  [DRY RUN] Would write {config_path}")
        print(f"    nick={agent_name}, server={server}:{port}, channels={channels}")
    else:
        config_path.write_text(
            json.dumps(config, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return True


def main():
    parser = argparse.ArgumentParser(description="Install IRC skill to KK workspaces")
    parser.add_argument("--agent", type=str, default=None, help="Single workspace name (e.g., kk-elboorja)")
    parser.add_argument("--workspaces", type=str, default=None, help="Workspaces directory")
    parser.add_argument("--server", type=str, default=DEFAULT_SERVER)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--tls", action="store_true", default=False)
    parser.add_argument("--channels", type=str, default="#Agents", help="Comma-separated channels")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    workspaces_dir = Path(args.workspaces) if args.workspaces else WORKSPACES_DIR
    channels = [c.strip() for c in args.channels.split(",")]

    # Validate skill source exists
    if not SKILLS_SRC.exists():
        print(f"ERROR: IRC skill source not found at {SKILLS_SRC}")
        sys.exit(1)

    # Discover workspaces
    if args.agent:
        ws_dir = workspaces_dir / args.agent
        if not ws_dir.exists():
            ws_dir = workspaces_dir / f"kk-{args.agent}"
        if not ws_dir.exists():
            print(f"ERROR: Workspace not found: {args.agent}")
            sys.exit(1)
        workspace_dirs = [ws_dir]
    else:
        # Use manifest if available
        manifest_file = workspaces_dir / "_manifest.json"
        if manifest_file.exists():
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            workspace_dirs = [
                workspaces_dir / ws["name"]
                for ws in manifest.get("workspaces", [])
            ]
        else:
            workspace_dirs = sorted(
                d for d in workspaces_dir.iterdir()
                if d.is_dir() and not d.name.startswith("_")
            )

    print(f"\n{'=' * 60}")
    print(f"  Karma Kadabra — IRC Skill Installer")
    print(f"  Server: {args.server}:{args.port} (TLS={args.tls})")
    print(f"  Channels: {channels}")
    print(f"  Workspaces: {len(workspace_dirs)}")
    if args.dry_run:
        print(f"  ** DRY RUN **")
    print(f"{'=' * 60}\n")

    installed = 0
    failed = 0

    for ws_dir in workspace_dirs:
        if not ws_dir.exists():
            print(f"  SKIP: {ws_dir.name} (not found)")
            failed += 1
            continue

        try:
            ok = install_to_workspace(
                ws_dir, args.server, args.port, args.tls, channels, args.dry_run
            )
            if ok:
                installed += 1
                tag = "[DRY RUN]" if args.dry_run else "[OK]"
                print(f"  {tag} {ws_dir.name} -> nick={ws_dir.name}")
            else:
                failed += 1
        except Exception as e:
            print(f"  [ERROR] {ws_dir.name}: {e}")
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"  Done! Installed: {installed}, Failed: {failed}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
