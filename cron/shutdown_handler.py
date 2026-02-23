"""
Karma Kadabra V2 — Phase 11: Graceful Shutdown Handler

Provides a graceful shutdown protocol for KK agent processes:
  1. Registers signal handlers (SIGTERM, SIGINT)
  2. On signal: sets shutdown flag, waits for current cycle to finish
  3. Writes final WORKING.md state
  4. Reports offline status to swarm state
  5. Saves daily note with shutdown reason
  6. Exits with code 0

Can be used standalone or as a wrapper around another process:
  python shutdown_handler.py --workspace /path/to/kk-agent
  python shutdown_handler.py --workspace /path/to/kk-agent -- python heartbeat.py --daemon

Usage:
  python shutdown_handler.py --workspace /path/to/workspace    # Standalone
  python shutdown_handler.py --workspace /path/to/workspace \\
      -- python heartbeat.py --daemon                          # Wrapper mode
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.memory import append_daily_note
from lib.swarm_state import report_heartbeat
from lib.working_state import parse_working_md, update_heartbeat, write_working_md

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("kk.shutdown")


class ShutdownHandler:
    """Manages graceful shutdown for a KK agent process."""

    def __init__(self, workspace_dir: Path):
        self.workspace_dir = workspace_dir
        self.agent_name = workspace_dir.name
        self.memory_dir = workspace_dir / "memory"
        self.working_path = self.memory_dir / "WORKING.md"
        self.shutdown_event = asyncio.Event()
        self.shutdown_reason = "unknown"
        self._child_process: subprocess.Popen | None = None

    def register_signals(self) -> None:
        """Register signal handlers for graceful shutdown."""
        loop = asyncio.get_running_loop()

        def _handle_signal(signum: int, frame: Any) -> None:
            sig_name = signal.Signals(signum).name
            self.shutdown_reason = f"received {sig_name}"
            logger.info(f"[{self.agent_name}] Signal {sig_name} received — initiating shutdown")
            self.shutdown_event.set()

        # On Windows, only SIGINT is reliably available
        signal.signal(signal.SIGINT, _handle_signal)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _handle_signal)

    async def write_final_state(self) -> None:
        """Write final WORKING.md with shutdown notes."""
        try:
            state = parse_working_md(self.working_path)
            update_heartbeat(
                state,
                action="shutdown",
                result=self.shutdown_reason,
            )
            write_working_md(self.working_path, state)
            logger.info(f"[{self.agent_name}] WORKING.md updated with shutdown state")
        except Exception as e:
            logger.warning(f"[{self.agent_name}] Failed to write WORKING.md: {e}")

    async def report_offline(self) -> None:
        """Report offline status to swarm state."""
        try:
            success = await report_heartbeat(
                agent_name=self.agent_name,
                status="offline",
                notes=f"shutdown: {self.shutdown_reason}",
            )
            if success:
                logger.info(f"[{self.agent_name}] Reported offline to swarm state")
            else:
                logger.warning(f"[{self.agent_name}] Failed to report offline (non-fatal)")
        except Exception as e:
            logger.warning(f"[{self.agent_name}] Swarm state report failed: {e}")

    async def save_shutdown_note(self) -> None:
        """Save daily note about the shutdown."""
        try:
            append_daily_note(
                self.memory_dir,
                action="shutdown",
                result=self.shutdown_reason,
            )
            logger.info(f"[{self.agent_name}] Shutdown noted in daily log")
        except Exception as e:
            logger.warning(f"[{self.agent_name}] Failed to save daily note: {e}")

    async def shutdown(self) -> None:
        """Execute full shutdown sequence."""
        logger.info(f"[{self.agent_name}] Starting graceful shutdown...")

        # Terminate child process if running
        if self._child_process and self._child_process.poll() is None:
            logger.info(f"[{self.agent_name}] Terminating child process (PID {self._child_process.pid})")
            self._child_process.terminate()
            try:
                self._child_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                logger.warning(f"[{self.agent_name}] Child did not exit, killing")
                self._child_process.kill()

        await self.write_final_state()
        await self.report_offline()
        await self.save_shutdown_note()

        logger.info(f"[{self.agent_name}] Shutdown complete — exit 0")

    async def run_standalone(self) -> None:
        """Run in standalone mode — wait for shutdown signal."""
        self.register_signals()
        logger.info(f"[{self.agent_name}] Shutdown handler active (standalone mode)")
        logger.info(f"[{self.agent_name}] Send SIGTERM or SIGINT to shut down")

        await self.shutdown_event.wait()
        await self.shutdown()

    async def run_wrapper(self, child_cmd: list[str]) -> int:
        """Run as a wrapper around a child process.

        Starts the child, monitors it, and handles shutdown signals.
        Returns the child's exit code.
        """
        self.register_signals()
        logger.info(f"[{self.agent_name}] Wrapping: {' '.join(child_cmd)}")

        self._child_process = subprocess.Popen(child_cmd)

        # Wait for either child exit or shutdown signal
        while not self.shutdown_event.is_set():
            ret = self._child_process.poll()
            if ret is not None:
                # Child exited on its own
                self.shutdown_reason = f"child exited with code {ret}"
                logger.info(f"[{self.agent_name}] Child process exited (code={ret})")
                await self.shutdown()
                return ret
            await asyncio.sleep(1)

        # Shutdown signal received
        await self.shutdown()
        return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


async def main():
    parser = argparse.ArgumentParser(
        description="KK Graceful Shutdown Handler",
        usage="%(prog)s --workspace /path/to/workspace [-- child_command ...]",
    )
    parser.add_argument(
        "--workspace",
        type=str,
        required=True,
        help="Path to agent workspace directory",
    )

    # Split args at "--" to separate our args from child command
    argv = sys.argv[1:]
    child_cmd: list[str] = []
    if "--" in argv:
        split_idx = argv.index("--")
        our_args = argv[:split_idx]
        child_cmd = argv[split_idx + 1:]
    else:
        our_args = argv

    args = parser.parse_args(our_args)
    workspace_dir = Path(args.workspace)

    if not workspace_dir.exists():
        print(f"ERROR: Workspace not found: {workspace_dir}")
        sys.exit(1)

    handler = ShutdownHandler(workspace_dir)

    if child_cmd:
        exit_code = await handler.run_wrapper(child_cmd)
        sys.exit(exit_code)
    else:
        await handler.run_standalone()
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
