"""
Karma Kadabra V2 — Phase 9.3: Karma Hello Background Scheduler

Pure asyncio scheduler that runs Karma Hello service cycles on a timer:

  - Collection:   every 30 minutes  (aggregate new IRC logs)
  - Publishing:   every 2 hours     (publish data offerings on EM)
  - Fulfillment:  every 15 minutes  (auto-approve data deliveries)

No external dependencies beyond the standard library and karma_hello_service.

Usage:
  python karma_hello_scheduler.py --daemon              # Run all cycles on schedule
  python karma_hello_scheduler.py --once                # Run all cycles once, then exit
  python karma_hello_scheduler.py --dry-run             # Preview without side effects
  python karma_hello_scheduler.py --daemon --dry-run    # Schedule loop in dry-run mode
"""

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

# Ensure parent packages are importable
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from karma_hello_service import collect_irc_logs, fulfill_purchases, publish_offerings
from em_client import AgentContext, EMClient, load_agent_context
from lib.swarm_state import report_heartbeat

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("kk.karma-hello-scheduler")

# Schedule intervals (seconds)
COLLECT_INTERVAL = 30 * 60   # 30 minutes
PUBLISH_INTERVAL = 2 * 3600  # 2 hours
FULFILL_INTERVAL = 15 * 60   # 15 minutes


class KarmaHelloScheduler:
    """Background scheduler for Karma Hello service cycles."""

    def __init__(
        self,
        data_dir: Path,
        workspace_dir: Path,
        dry_run: bool = False,
    ):
        self.data_dir = data_dir
        self.workspace_dir = workspace_dir
        self.dry_run = dry_run
        self._running = True
        self._tasks: list[asyncio.Task] = []

    def _load_client(self) -> tuple[AgentContext, EMClient]:
        """Load agent context and create EM client."""
        if self.workspace_dir.exists():
            agent = load_agent_context(self.workspace_dir)
        else:
            agent = AgentContext(
                name="kk-karma-hello",
                wallet_address="",
                workspace_dir=self.workspace_dir,
            )
        return agent, EMClient(agent)

    async def _run_collect(self) -> None:
        """Collect cycle loop."""
        while self._running:
            logger.info("[scheduler] Running collect cycle")
            try:
                result = collect_irc_logs(self.data_dir, dry_run=self.dry_run)
                logger.info(
                    f"[scheduler] Collect done: "
                    f"{result['new_messages']} new messages"
                )
            except Exception as e:
                logger.error(f"[scheduler] Collect error: {e}")

            await self._sleep(COLLECT_INTERVAL)

    async def _run_publish(self) -> None:
        """Publish cycle loop."""
        while self._running:
            logger.info("[scheduler] Running publish cycle")
            agent, client = self._load_client()
            try:
                result = await publish_offerings(
                    client, self.data_dir, dry_run=self.dry_run,
                )
                logger.info(
                    f"[scheduler] Publish done: "
                    f"{result['published']} published, {result['skipped']} skipped"
                )
            except Exception as e:
                logger.error(f"[scheduler] Publish error: {e}")
            finally:
                await client.close()

            await self._sleep(PUBLISH_INTERVAL)

    async def _run_fulfill(self) -> None:
        """Fulfill cycle loop."""
        while self._running:
            logger.info("[scheduler] Running fulfill cycle")
            agent, client = self._load_client()
            try:
                result = await fulfill_purchases(client, dry_run=self.dry_run)
                logger.info(
                    f"[scheduler] Fulfill done: "
                    f"{result['approved']} approved, {result['reviewed']} reviewed"
                )
            except Exception as e:
                logger.error(f"[scheduler] Fulfill error: {e}")
            finally:
                await client.close()

            await self._sleep(FULFILL_INTERVAL)

    async def _sleep(self, seconds: int) -> None:
        """Interruptible sleep."""
        try:
            await asyncio.sleep(seconds)
        except asyncio.CancelledError:
            pass

    async def _heartbeat_loop(self) -> None:
        """Report heartbeat to coordinator every 5 minutes."""
        while self._running:
            try:
                await report_heartbeat(
                    agent_name="kk-karma-hello",
                    status="idle",
                    notes="scheduler running",
                )
            except Exception:
                pass
            await self._sleep(300)

    async def run_once(self) -> None:
        """Run all three cycles once, then return."""
        logger.info("[scheduler] Running all cycles once")

        # Collect (sync)
        try:
            collect_result = collect_irc_logs(self.data_dir, dry_run=self.dry_run)
            logger.info(f"Collect: {collect_result['new_messages']} new messages")
        except Exception as e:
            logger.error(f"Collect error: {e}")

        # Publish + Fulfill (async, need client)
        agent, client = self._load_client()
        try:
            publish_result = await publish_offerings(
                client, self.data_dir, dry_run=self.dry_run,
            )
            logger.info(
                f"Publish: {publish_result['published']} published, "
                f"{publish_result['skipped']} skipped"
            )

            fulfill_result = await fulfill_purchases(client, dry_run=self.dry_run)
            logger.info(
                f"Fulfill: {fulfill_result['approved']} approved, "
                f"{fulfill_result['reviewed']} reviewed"
            )
        except Exception as e:
            logger.error(f"Service error: {e}")
        finally:
            await client.close()

    async def run_daemon(self) -> None:
        """Run all cycles on their respective schedules."""
        logger.info(
            f"[scheduler] Starting daemon — "
            f"collect={COLLECT_INTERVAL}s, publish={PUBLISH_INTERVAL}s, "
            f"fulfill={FULFILL_INTERVAL}s"
        )

        # Set up signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, self.stop)
            except NotImplementedError:
                # Windows doesn't support add_signal_handler
                pass

        # Launch all cycle loops concurrently
        self._tasks = [
            asyncio.create_task(self._run_collect()),
            asyncio.create_task(self._run_publish()),
            asyncio.create_task(self._run_fulfill()),
            asyncio.create_task(self._heartbeat_loop()),
        ]

        try:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        except asyncio.CancelledError:
            pass

        logger.info("[scheduler] Daemon stopped")

    def stop(self) -> None:
        """Signal all loops to stop."""
        logger.info("[scheduler] Shutdown requested")
        self._running = False
        for task in self._tasks:
            task.cancel()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


async def main() -> None:
    parser = argparse.ArgumentParser(description="Karma Hello Background Scheduler")
    parser.add_argument(
        "--daemon", action="store_true",
        help="Run continuously on schedule",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Run all cycles once and exit",
    )
    parser.add_argument("--workspace", type=str, default=None, help="Workspace dir")
    parser.add_argument("--data-dir", type=str, default=None, help="Data directory")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview without side effects",
    )
    args = parser.parse_args()

    base = Path(__file__).parent.parent
    workspace_dir = (
        Path(args.workspace) if args.workspace
        else base / "data" / "workspaces" / "kk-karma-hello"
    )
    data_dir = Path(args.data_dir) if args.data_dir else base / "data"

    if not args.daemon and not args.once:
        parser.print_help()
        print("\nSpecify --daemon or --once")
        return

    mode = "daemon" if args.daemon else "once"
    print(f"\n{'=' * 60}")
    print(f"  Karma Hello Scheduler")
    print(f"  Mode: {mode}")
    print(f"  Data dir: {data_dir}")
    if args.dry_run:
        print(f"  ** DRY RUN **")
    print(f"{'=' * 60}\n")

    scheduler = KarmaHelloScheduler(
        data_dir=data_dir,
        workspace_dir=workspace_dir,
        dry_run=args.dry_run,
    )

    if args.once:
        await scheduler.run_once()
    else:
        await scheduler.run_daemon()


if __name__ == "__main__":
    asyncio.run(main())
