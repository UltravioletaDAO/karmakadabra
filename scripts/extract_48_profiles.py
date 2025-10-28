"""
Batch Profile Extraction Script
Extracts skill profiles for 48 users using Skill-Extractor Agent

Sprint 3, Task 1: Automated profile extraction
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

# Fix Windows console encoding FIRST
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import os

# Load environment
load_dotenv()


async def extract_profiles_batch():
    """
    Extract profiles for 48 users from chat logs
    """

    # Read list of 48 users
    user_list_file = "/tmp/user_list_48.txt"

    if not Path(user_list_file).exists():
        print(f"❌ User list file not found: {user_list_file}")
        print("Creating user list from logs...")

        # Find all unique users
        import subprocess
        result = subprocess.run(
            'find karma-hello-agent/logs/202510* -name "*.txt" -type f | sed "s|.*/||" | sed "s|\\.txt$||" | sort -u | head -48',
            shell=True,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        users = result.stdout.strip().split('\n')
    else:
        with open(user_list_file, 'r') as f:
            users = [line.strip() for line in f if line.strip()]

    print(f"📋 Found {len(users)} users to process")

    # Create output directory
    output_dir = Path(__file__).parent.parent / "user-profiles"
    output_dir.mkdir(exist_ok=True)

    print(f"📂 Output directory: {output_dir}")

    # Import Skill-Extractor Agent
    sys.path.append(str(Path(__file__).parent.parent / "skill-extractor-agent"))
    from main import SkillExtractorAgent

    # Initialize agent with local file mode
    config = {
        "agent_domain": "skill-extractor.karmacadabra.ultravioletadao.xyz",
        "rpc_url_fuji": os.getenv("RPC_URL_FUJI", "https://avalanche-fuji-c-chain-rpc.publicnode.com"),
        "chain_id": 43113,
        "identity_registry": os.getenv("IDENTITY_REGISTRY"),
        "reputation_registry": os.getenv("REPUTATION_REGISTRY"),
        "validation_registry": os.getenv("VALIDATION_REGISTRY"),
        "glue_token_address": os.getenv("GLUE_TOKEN_ADDRESS"),
        "facilitator_url": os.getenv("FACILITATOR_URL", "http://localhost:8080"),
        "private_key": os.getenv("PRIVATE_KEY"),
        "karma_hello_url": "http://localhost:8081",  # Not used in local mode
        "use_local_files": True,  # KEY: Use local files instead of buying from Karma-Hello
        "local_logs_dir": str(Path(__file__).parent.parent / "karma-hello-agent" / "logs")
    }

    agent = SkillExtractorAgent(config)

    print("✅ Skill-Extractor Agent initialized (local file mode)")
    print()

    # Process each user
    successful = 0
    failed = 0

    for i, username in enumerate(users, 1):
        print(f"[{i}/{len(users)}] Processing {username}...")

        try:
            # Extract profile
            profile = await agent.extract_skill_profile(
                username=username,
                profile_level="complete",  # Full profile for all users
                include_monetization=True
            )

            # Save profile to JSON
            profile_file = output_dir / f"{username}.json"
            with open(profile_file, 'w', encoding='utf-8') as f:
                json.dump(profile.model_dump(), f, indent=2, ensure_ascii=False)

            print(f"   ✅ Saved profile: {profile_file.name}")
            successful += 1

        except Exception as e:
            print(f"   ❌ Failed to extract profile for {username}: {e}")
            failed += 1

        # Small delay to avoid overwhelming the system
        if i < len(users):
            await asyncio.sleep(0.5)

    print()
    print("="*80)
    print(f"📊 Profile Extraction Summary")
    print(f"="*80)
    print(f"Total users: {len(users)}")
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {failed}")
    print(f"📂 Output directory: {output_dir}")
    print()

    return successful, failed


if __name__ == "__main__":
    print("="*80)
    print("Karmacadabra - Sprint 3: Automated Profile Extraction")
    print("="*80)
    print()

    successful, failed = asyncio.run(extract_profiles_batch())

    if failed == 0:
        print("🎉 All profiles extracted successfully!")
        sys.exit(0)
    else:
        print(f"⚠️  {failed} profiles failed to extract")
        sys.exit(1)
