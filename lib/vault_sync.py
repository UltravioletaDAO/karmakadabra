"""
Obsidian Vault sync library for KK agents.

Each agent reads/writes markdown files with YAML frontmatter to a shared
vault directory. State is synced via git (pull/commit/push) on each heartbeat.

Usage:
    from lib.vault_sync import VaultSync

    vault = VaultSync("/app/vault", "kk-karma-hello")
    vault.pull()
    vault.write_state({"status": "active", "current_task": "publishing logs"}, body="## Processing batch #5")
    vault.append_log("Published 5 bundles on EM")
    vault.commit_and_push("published data bundles")
"""

import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import frontmatter
except ImportError:
    frontmatter = None
    logger.warning("python-frontmatter not installed; vault_sync will use raw markdown")


class VaultSync:
    """Read/write agent state to Obsidian vault markdown files."""

    def __init__(self, vault_path: str, agent_name: str):
        self.vault = Path(vault_path)
        self.agent_name = agent_name
        self.agent_dir = self.vault / "agents" / agent_name
        self.shared_dir = self.vault / "shared"
        self.agent_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Git operations
    # ------------------------------------------------------------------

    def pull(self) -> bool:
        """Pull latest from remote. Returns True on success."""
        if not (self.vault / ".git").exists():
            logger.debug("Vault is not a git repo, skipping pull")
            return False
        try:
            subprocess.run(
                ["git", "pull", "--rebase", "--autostash", "--quiet"],
                cwd=str(self.vault),
                check=True,
                capture_output=True,
                timeout=30,
            )
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.warning(f"Vault pull failed: {e}")
            return False

    def commit_and_push(self, message: str) -> bool:
        """Stage agent dir + shared, commit if changes, push. Returns True on success."""
        if not (self.vault / ".git").exists():
            logger.debug("Vault is not a git repo, skipping commit")
            return False
        try:
            # Stage own files + shared
            subprocess.run(
                ["git", "add", f"agents/{self.agent_name}/", "shared/"],
                cwd=str(self.vault),
                check=True,
                capture_output=True,
                timeout=15,
            )
            # Check if anything staged
            result = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=str(self.vault),
                capture_output=True,
            )
            if result.returncode == 0:
                return True  # Nothing to commit

            # Commit
            subprocess.run(
                ["git", "commit", "-m", f"{self.agent_name}: {message}"],
                cwd=str(self.vault),
                check=True,
                capture_output=True,
                timeout=15,
            )
            # Push (non-fatal if fails)
            subprocess.run(
                ["git", "push", "--quiet"],
                cwd=str(self.vault),
                capture_output=True,
                timeout=30,
            )
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.warning(f"Vault commit/push failed: {e}")
            return False

    # ------------------------------------------------------------------
    # State read/write (own agent)
    # ------------------------------------------------------------------

    def write_state(self, metadata: dict, body: str = None):
        """Update this agent's state.md with frontmatter metadata and optional body."""
        state_path = self.agent_dir / "state.md"

        metadata["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
        metadata.setdefault("agent_id", self.agent_name)

        if frontmatter:
            if state_path.exists():
                post = frontmatter.load(str(state_path))
                post.metadata.update(metadata)
                if body is not None:
                    post.content = body
            else:
                post = frontmatter.Post(body or "", **metadata)

            with open(state_path, "w", encoding="utf-8") as f:
                frontmatter.dump(post, f)
        else:
            self._write_raw_state(state_path, metadata, body)

    def read_state(self) -> dict:
        """Read this agent's state.md frontmatter as dict."""
        return self._read_frontmatter(self.agent_dir / "state.md")

    def read_peer_state(self, agent_name: str) -> dict:
        """Read another agent's state.md frontmatter."""
        return self._read_frontmatter(self.vault / "agents" / agent_name / "state.md")

    def list_peer_states(self) -> dict:
        """Read state of all agents. Returns {agent_name: metadata_dict}."""
        agents_dir = self.vault / "agents"
        states = {}
        if not agents_dir.exists():
            return states
        for agent_dir in sorted(agents_dir.iterdir()):
            if agent_dir.is_dir():
                state = self._read_frontmatter(agent_dir / "state.md")
                if state:
                    states[agent_dir.name] = state
        return states

    # ------------------------------------------------------------------
    # Log operations
    # ------------------------------------------------------------------

    def append_log(self, message: str):
        """Append a timestamped line to today's log file."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_path = self.agent_dir / f"log-{today}.md"

        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")

        if not log_path.exists():
            log_path.write_text(
                f"---\nagent_id: {self.agent_name}\ndate: {today}\ntags:\n  - log\n---\n\n## Activity Log - {today}\n\n",
                encoding="utf-8",
            )

        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"- {timestamp} - {message}\n")

    # ------------------------------------------------------------------
    # Offerings (seller publishes what's available)
    # ------------------------------------------------------------------

    def write_offerings(self, tasks: list[dict]):
        """Write this agent's offerings.md with current EM task listings.

        Args:
            tasks: List of dicts with {task_id, title, bounty, category, status}.
        """
        offerings_path = self.agent_dir / "offerings.md"

        now = datetime.now(timezone.utc).isoformat()
        metadata = {
            "agent_id": self.agent_name,
            "updated": now,
            "total_offerings": len(tasks),
            "tags": ["offerings", "seller"],
        }

        lines = []
        lines.append(f"## Active Offerings ({len(tasks)} products)\n")
        for t in tasks:
            tid = t.get("task_id", t.get("id", "?"))
            title = t.get("title", "?")
            bounty = t.get("bounty", t.get("bounty_usd", 0))
            lines.append(f"- **{title}** — ${bounty} (task: `{tid}`)")
        lines.append(f"\nLast updated: {now}")

        body = "\n".join(lines)

        if frontmatter:
            post = frontmatter.Post(body, **metadata)
            with open(offerings_path, "w", encoding="utf-8") as f:
                frontmatter.dump(post, f)
        else:
            self._write_raw_state(offerings_path, metadata, body)

    def read_peer_offerings(self, agent_name: str) -> list[dict]:
        """Read another agent's offerings.md and extract task info.

        Returns list of dicts with available offerings metadata.
        """
        path = self.vault / "agents" / agent_name / "offerings.md"
        meta = self._read_frontmatter(path)
        if not meta:
            return []

        # Parse body for task IDs (simple extraction)
        offerings = []
        if path.exists():
            try:
                text = path.read_text(encoding="utf-8")
                for line in text.splitlines():
                    if line.startswith("- **") and "task:" in line:
                        # Extract task_id from "task: `uuid`"
                        tid = ""
                        if "`" in line:
                            parts = line.split("`")
                            if len(parts) >= 2:
                                tid = parts[1]
                        # Extract bounty from "$X.XX"
                        bounty = 0.0
                        if "$" in line:
                            try:
                                bounty_str = line.split("$")[1].split(" ")[0].split(")")[0]
                                bounty = float(bounty_str)
                            except (ValueError, IndexError):
                                pass
                        # Extract title from "**title**"
                        title = ""
                        if "**" in line:
                            title_parts = line.split("**")
                            if len(title_parts) >= 2:
                                title = title_parts[1]
                        if tid:
                            offerings.append({"task_id": tid, "title": title, "bounty": bounty})
            except Exception:
                pass

        return offerings

    # ------------------------------------------------------------------
    # Supply chain status (coordinator writes, others read)
    # ------------------------------------------------------------------

    def write_supply_chain_status(self, agent_statuses: dict[str, str]):
        """Update shared/supply-chain.md with live agent statuses.

        Args:
            agent_statuses: Dict of {agent_name: status_string}.
                            e.g. {"kk-karma-hello": "publishing (5 tasks)"}
        """
        path = self.shared_dir / "supply-chain.md"
        if not path.exists():
            return

        # Read existing file
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            return

        # Update the frontmatter timestamp
        now = datetime.now(timezone.utc).isoformat()

        # Build live status section
        status_lines = ["\n## Live Agent Status\n"]
        for agent_name in sorted(agent_statuses.keys()):
            status = agent_statuses[agent_name]
            status_lines.append(f"- **[[{agent_name}]]**: {status}")
        status_lines.append(f"\n*Updated: {now}*")
        status_block = "\n".join(status_lines)

        # Replace or append live status section
        if "## Live Agent Status" in text:
            # Replace existing section (from header to next ## or end)
            before = text[:text.index("## Live Agent Status")]
            # Find next section after Live Agent Status
            after_start = text.index("## Live Agent Status") + len("## Live Agent Status")
            remaining = text[after_start:]
            next_section = remaining.find("\n## ")
            if next_section >= 0:
                after = remaining[next_section:]
            else:
                after = ""
            text = before + status_block + after
        else:
            text = text.rstrip() + "\n" + status_block

        # Update frontmatter timestamp
        if "updated:" in text:
            import re
            text = re.sub(r"updated:.*", f"updated: {now}", text, count=1)

        path.write_text(text, encoding="utf-8")

    def read_supply_chain_status(self) -> dict[str, str]:
        """Read live agent statuses from shared/supply-chain.md.

        Returns dict of {agent_name: status_string}.
        """
        path = self.shared_dir / "supply-chain.md"
        statuses = {}
        if not path.exists():
            return statuses
        try:
            text = path.read_text(encoding="utf-8")
            in_status = False
            for line in text.splitlines():
                if "## Live Agent Status" in line:
                    in_status = True
                    continue
                if in_status and line.startswith("## "):
                    break
                if in_status and line.startswith("- **"):
                    # Parse "- **[[agent-name]]**: status text"
                    try:
                        name_part = line.split("[[")[1].split("]]")[0]
                        status_part = line.split("]]**: ")[1] if "]]**: " in line else ""
                        statuses[name_part] = status_part
                    except (IndexError, ValueError):
                        pass
        except Exception:
            pass
        return statuses

    # ------------------------------------------------------------------
    # Shared files
    # ------------------------------------------------------------------

    def read_shared(self, filename: str) -> dict:
        """Read a shared file's frontmatter."""
        return self._read_frontmatter(self.shared_dir / filename)

    def append_to_shared(self, filename: str, line: str):
        """Append a line to a shared file (ledger, announcements, etc.)."""
        filepath = self.shared_dir / filename
        if filepath.exists():
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(f"{line}\n")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_frontmatter(self, path: Path) -> dict:
        """Read YAML frontmatter from a markdown file."""
        if not path.exists():
            return {}
        if frontmatter:
            try:
                post = frontmatter.load(str(path))
                return dict(post.metadata)
            except Exception as e:
                logger.warning(f"Failed to parse frontmatter from {path}: {e}")
                return {}
        else:
            return self._read_raw_frontmatter(path)

    def _write_raw_state(self, path: Path, metadata: dict, body: str = None):
        """Write state.md without python-frontmatter (fallback)."""
        existing_meta = self._read_raw_frontmatter(path)
        existing_meta.update(metadata)

        lines = ["---"]
        for k, v in sorted(existing_meta.items()):
            if isinstance(v, list):
                lines.append(f"{k}:")
                for item in v:
                    lines.append(f"  - {item}")
            elif isinstance(v, str) and ('"' in v or "'" in v or ":" in v):
                lines.append(f'{k}: "{v}"')
            else:
                lines.append(f"{k}: {v}")
        lines.append("---")
        lines.append("")
        if body:
            lines.append(body)
        path.write_text("\n".join(lines), encoding="utf-8")

    def _read_raw_frontmatter(self, path: Path) -> dict:
        """Parse YAML frontmatter without python-frontmatter (fallback)."""
        if not path.exists():
            return {}
        try:
            text = path.read_text(encoding="utf-8")
            if not text.startswith("---"):
                return {}
            end = text.index("---", 3)
            yaml_text = text[3:end].strip()
            # Simple YAML parser for flat key-value
            result = {}
            for line in yaml_text.split("\n"):
                line = line.strip()
                if ":" in line and not line.startswith("-"):
                    key, _, value = line.partition(":")
                    value = value.strip().strip('"').strip("'")
                    result[key.strip()] = value
            return result
        except (ValueError, Exception):
            return {}
