"""
Rebuild User Agent Marketplace - Idempotent Orchestration Script
Re-runs entire Sprint 3 pipeline: Extract → Generate → Deploy

This script is idempotent and safe to run multiple times.
Use when:
- New chat logs are available
- Additional users join
- Profiles need updating
- Agent cards need regeneration
- Deployment needs refresh

Sprint 3 Pipeline:
1. Extract profiles from chat logs
2. Generate Agent Cards from profiles
3. Deploy user agents from cards

Usage:
    python scripts/rebuild_user_agent_marketplace.py [options]

Options:
    --users N         Process specific number of users (default: all)
    --skip-extract    Skip profile extraction (use existing)
    --skip-cards      Skip agent card generation (use existing)
    --skip-deploy     Skip agent deployment (use existing)
    --force           Force rebuild even if outputs exist
    --dry-run         Show what would be done without doing it
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass


class MarketplaceBuilder:
    """Orchestrates the user agent marketplace build pipeline"""

    def __init__(
        self,
        base_dir: Path,
        num_users: Optional[int] = None,
        force: bool = False,
        dry_run: bool = False
    ):
        self.base_dir = base_dir
        self.num_users = num_users
        self.force = force
        self.dry_run = dry_run

        # Paths
        self.scripts_dir = base_dir / "scripts"
        self.profiles_dir = base_dir / "user-profiles"
        self.cards_dir = base_dir / "agent-cards"
        self.agents_dir = base_dir / "user-agents"
        self.logs_dir = base_dir / "karma-hello-agent" / "logs"

        # Stats
        self.stats = {
            "profiles_extracted": 0,
            "cards_generated": 0,
            "agents_deployed": 0,
            "errors": []
        }

    def print_header(self, title: str):
        """Print section header"""
        print()
        print("=" * 80)
        print(f"{title}")
        print("=" * 80)
        print()

    def print_step(self, step: str, status: str = ""):
        """Print step with status"""
        if status:
            print(f"  {step}... {status}")
        else:
            print(f"  {step}")

    def check_prerequisites(self) -> bool:
        """Check if all prerequisites are met"""
        self.print_header("Checking Prerequisites")

        checks = {
            "Chat logs directory": self.logs_dir.exists(),
            "Scripts directory": self.scripts_dir.exists(),
            "Extract script": (self.scripts_dir / "extract_48_profiles_simple.py").exists(),
            "Card generator": (self.scripts_dir / "generate_agent_cards.py").exists(),
            "Deploy script": (self.scripts_dir / "deploy_user_agents.py").exists(),
        }

        all_good = True
        for check, passed in checks.items():
            status = "✅" if passed else "❌"
            self.print_step(check, status)
            if not passed:
                all_good = False

        if not all_good:
            print()
            print("❌ Prerequisites check failed")
            return False

        print()
        print("✅ All prerequisites met")
        return True

    def get_available_users(self) -> List[str]:
        """Get list of available users from chat logs"""
        try:
            result = subprocess.run(
                'find karma-hello-agent/logs/202510* -name "*.txt" -type f | sed "s|.*/||" | sed "s|\\.txt$||" | sort -u',
                shell=True,
                capture_output=True,
                text=True,
                cwd=self.base_dir
            )

            users = [u.strip() for u in result.stdout.strip().split('\n') if u.strip()]

            if self.num_users:
                users = users[:self.num_users]

            return users

        except Exception as e:
            print(f"❌ Error getting user list: {e}")
            return []

    def step1_extract_profiles(self) -> bool:
        """Step 1: Extract user profiles from chat logs"""
        self.print_header("Step 1: Extract User Profiles")

        # Check if we should skip
        if self.profiles_dir.exists() and not self.force:
            existing = len(list(self.profiles_dir.glob("*.json")))
            if existing > 0:
                self.print_step(f"Found {existing} existing profiles")
                self.print_step("Use --force to re-extract")
                self.stats["profiles_extracted"] = existing
                return True

        # Backup existing profiles if force mode
        if self.force and self.profiles_dir.exists():
            backup_dir = self.base_dir / f"user-profiles.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            if not self.dry_run:
                shutil.copytree(self.profiles_dir, backup_dir)
            self.print_step(f"Backed up existing profiles to {backup_dir.name}")

        # Run extraction
        self.print_step("Running profile extraction...")

        if self.dry_run:
            self.print_step("DRY RUN: Would extract profiles", "⏭️")
            return True

        try:
            result = subprocess.run(
                [sys.executable, str(self.scripts_dir / "extract_48_profiles_simple.py")],
                cwd=self.base_dir,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                # Count profiles
                profiles = list(self.profiles_dir.glob("*.json"))
                self.stats["profiles_extracted"] = len(profiles)
                self.print_step(f"Extracted {len(profiles)} profiles", "✅")
                return True
            else:
                self.print_step("Profile extraction failed", "❌")
                self.stats["errors"].append(f"Profile extraction: {result.stderr[:200]}")
                return False

        except Exception as e:
            self.print_step(f"Error: {e}", "❌")
            self.stats["errors"].append(f"Profile extraction exception: {str(e)}")
            return False

    def step2_generate_agent_cards(self) -> bool:
        """Step 2: Generate Agent Cards from profiles"""
        self.print_header("Step 2: Generate Agent Cards")

        # Check if profiles exist
        if not self.profiles_dir.exists():
            self.print_step("No profiles directory found", "❌")
            return False

        profiles = list(self.profiles_dir.glob("*.json"))
        if not profiles:
            self.print_step("No profiles found to generate cards from", "❌")
            return False

        # Check if we should skip
        if self.cards_dir.exists() and not self.force:
            existing = len(list(self.cards_dir.glob("*.json")))
            if existing > 0:
                self.print_step(f"Found {existing} existing agent cards")
                self.print_step("Use --force to re-generate")
                self.stats["cards_generated"] = existing
                return True

        # Backup existing cards if force mode
        if self.force and self.cards_dir.exists():
            backup_dir = self.base_dir / f"agent-cards.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            if not self.dry_run:
                shutil.copytree(self.cards_dir, backup_dir)
            self.print_step(f"Backed up existing cards to {backup_dir.name}")

        # Run generation
        self.print_step(f"Generating cards from {len(profiles)} profiles...")

        if self.dry_run:
            self.print_step("DRY RUN: Would generate agent cards", "⏭️")
            return True

        try:
            result = subprocess.run(
                [sys.executable, str(self.scripts_dir / "generate_agent_cards.py")],
                cwd=self.base_dir,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                # Count cards
                cards = list(self.cards_dir.glob("*.json"))
                self.stats["cards_generated"] = len(cards)
                self.print_step(f"Generated {len(cards)} agent cards", "✅")
                return True
            else:
                self.print_step("Agent card generation failed", "❌")
                self.stats["errors"].append(f"Card generation: {result.stderr[:200]}")
                return False

        except Exception as e:
            self.print_step(f"Error: {e}", "❌")
            self.stats["errors"].append(f"Card generation exception: {str(e)}")
            return False

    def step3_deploy_agents(self) -> bool:
        """Step 3: Deploy user agents"""
        self.print_header("Step 3: Deploy User Agents")

        # Check if cards exist
        if not self.cards_dir.exists():
            self.print_step("No agent cards directory found", "❌")
            return False

        cards = list(self.cards_dir.glob("*.json"))
        if not cards:
            self.print_step("No agent cards found to deploy", "❌")
            return False

        # Check if we should skip
        if self.agents_dir.exists() and not self.force:
            existing = len([d for d in self.agents_dir.iterdir() if d.is_dir()])
            if existing > 0:
                self.print_step(f"Found {existing} existing agent deployments")
                self.print_step("Use --force to re-deploy")
                self.stats["agents_deployed"] = existing
                return True

        # Backup existing agents if force mode
        if self.force and self.agents_dir.exists():
            backup_dir = self.base_dir / f"user-agents.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            if not self.dry_run:
                # Only backup .env files (preserve private keys)
                backup_dir.mkdir(parents=True)
                for agent_dir in self.agents_dir.iterdir():
                    if agent_dir.is_dir():
                        env_file = agent_dir / ".env"
                        if env_file.exists():
                            dest_dir = backup_dir / agent_dir.name
                            dest_dir.mkdir(parents=True, exist_ok=True)
                            shutil.copy(env_file, dest_dir / ".env")
            self.print_step(f"Backed up .env files to {backup_dir.name}")

        # Run deployment
        self.print_step(f"Deploying {len(cards)} agents...")

        if self.dry_run:
            self.print_step("DRY RUN: Would deploy agents", "⏭️")
            return True

        try:
            result = subprocess.run(
                [sys.executable, str(self.scripts_dir / "deploy_user_agents.py")],
                cwd=self.base_dir,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                # Count deployed agents
                agents = [d for d in self.agents_dir.iterdir() if d.is_dir()]
                self.stats["agents_deployed"] = len(agents)
                self.print_step(f"Deployed {len(agents)} agents", "✅")

                # Restore .env files if we backed them up
                if self.force:
                    backup_dir = self.base_dir / f"user-agents.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    if backup_dir.exists():
                        self.print_step("Restoring .env files...")
                        for backup_agent in backup_dir.iterdir():
                            if backup_agent.is_dir():
                                env_backup = backup_agent / ".env"
                                if env_backup.exists():
                                    dest = self.agents_dir / backup_agent.name / ".env"
                                    shutil.copy(env_backup, dest)
                        self.print_step("Restored .env files", "✅")

                return True
            else:
                self.print_step("Agent deployment failed", "❌")
                self.stats["errors"].append(f"Deployment: {result.stderr[:200]}")
                return False

        except Exception as e:
            self.print_step(f"Error: {e}", "❌")
            self.stats["errors"].append(f"Deployment exception: {str(e)}")
            return False

    def print_summary(self):
        """Print build summary"""
        self.print_header("Build Summary")

        print(f"📊 Profiles extracted:  {self.stats['profiles_extracted']}")
        print(f"📋 Agent cards generated: {self.stats['cards_generated']}")
        print(f"🚀 Agents deployed:     {self.stats['agents_deployed']}")
        print()

        if self.stats["errors"]:
            print("❌ Errors encountered:")
            for error in self.stats["errors"]:
                print(f"  - {error}")
            print()
        else:
            print("✅ No errors")
            print()

        # Print directories
        print("📂 Output directories:")
        print(f"  - Profiles:     {self.profiles_dir}")
        print(f"  - Agent Cards:  {self.cards_dir}")
        print(f"  - Agents:       {self.agents_dir}")
        print()

        # Next steps
        if self.stats["agents_deployed"] > 0:
            print("🎯 Next steps:")
            print("  1. Configure wallets (PRIVATE_KEY in each .env)")
            print("  2. Fund with AVAX (https://faucet.avax.network/)")
            print("  3. Test an agent:")
            print(f"     cd user-agents/{list(self.agents_dir.iterdir())[0].name if self.agents_dir.exists() else 'username'}")
            print("     python main.py")
            print()

    def build(
        self,
        skip_extract: bool = False,
        skip_cards: bool = False,
        skip_deploy: bool = False
    ) -> bool:
        """Run the complete build pipeline"""

        self.print_header("Karmacadabra - User Agent Marketplace Builder")
        print(f"Base directory: {self.base_dir}")
        print(f"Mode: {'DRY RUN' if self.dry_run else 'PRODUCTION'}")
        print(f"Force rebuild: {self.force}")
        print(f"Max users: {self.num_users if self.num_users else 'all'}")

        # Prerequisites check
        if not self.check_prerequisites():
            return False

        # Show available users
        users = self.get_available_users()
        if not users:
            print("❌ No users found in chat logs")
            return False

        print()
        print(f"📋 Found {len(users)} users to process")
        print()

        # Run pipeline
        success = True

        if not skip_extract:
            if not self.step1_extract_profiles():
                success = False
                if not self.force:
                    return False

        if not skip_cards:
            if not self.step2_generate_agent_cards():
                success = False
                if not self.force:
                    return False

        if not skip_deploy:
            if not self.step3_deploy_agents():
                success = False

        # Summary
        self.print_summary()

        return success


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Rebuild user agent marketplace (idempotent)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full rebuild (re-extract everything)
  python rebuild_user_agent_marketplace.py --force

  # Only regenerate cards and redeploy
  python rebuild_user_agent_marketplace.py --skip-extract

  # Process only first 10 users
  python rebuild_user_agent_marketplace.py --users 10

  # Dry run (see what would happen)
  python rebuild_user_agent_marketplace.py --dry-run

  # Just redeploy (use existing profiles/cards)
  python rebuild_user_agent_marketplace.py --skip-extract --skip-cards
        """
    )

    parser.add_argument(
        "--users",
        type=int,
        help="Process only N users (default: all)"
    )
    parser.add_argument(
        "--skip-extract",
        action="store_true",
        help="Skip profile extraction (use existing)"
    )
    parser.add_argument(
        "--skip-cards",
        action="store_true",
        help="Skip agent card generation (use existing)"
    )
    parser.add_argument(
        "--skip-deploy",
        action="store_true",
        help="Skip agent deployment (use existing)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force rebuild even if outputs exist"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without doing it"
    )

    args = parser.parse_args()

    # Get base directory
    base_dir = Path(__file__).parent.parent

    # Create builder
    builder = MarketplaceBuilder(
        base_dir=base_dir,
        num_users=args.users,
        force=args.force,
        dry_run=args.dry_run
    )

    # Run build
    success = builder.build(
        skip_extract=args.skip_extract,
        skip_cards=args.skip_cards,
        skip_deploy=args.skip_deploy
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
