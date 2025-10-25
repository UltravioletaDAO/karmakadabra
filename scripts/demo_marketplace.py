#!/usr/bin/env python3
"""
Karmacadabra Marketplace Demo
Demonstrates the 48-agent marketplace capabilities

Usage:
    python demo_marketplace.py              # Interactive menu
    python demo_marketplace.py --quick      # Quick 3-agent demo
    python demo_marketplace.py --discovery  # Agent discovery demo
    python demo_marketplace.py --services   # Service listing demo
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Dict, Any
import argparse

import requests
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.tree import Tree
from rich import print as rprint

# Fix Windows encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

console = Console()

# Demo configuration
DEMO_AGENTS = [
    {"username": "elboorja", "port": 9044},
    {"username": "cymatix", "port": 9002},
    {"username": "eljuyan", "port": 9026}
]


class MarketplaceDemo:
    """Interactive marketplace demo"""

    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.agents_dir = self.base_dir / "user-agents"
        self.running_agents = []

    def start_agent(self, username: str, port: int) -> bool:
        """Start a user agent"""
        agent_dir = self.agents_dir / username

        if not agent_dir.exists():
            console.print(f"[red]❌ Agent directory not found: {agent_dir}[/red]")
            return False

        console.print(f"[cyan]🚀 Starting {username} on port {port}...[/cyan]")

        # Start agent process
        try:
            if sys.platform == 'win32':
                proc = subprocess.Popen(
                    ["python", "main.py"],
                    cwd=agent_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:
                proc = subprocess.Popen(
                    ["python", "main.py"],
                    cwd=agent_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )

            self.running_agents.append({
                "username": username,
                "port": port,
                "process": proc,
                "url": f"http://localhost:{port}"
            })

            # Wait for agent to be ready
            time.sleep(3)

            # Test health endpoint
            try:
                response = requests.get(f"http://localhost:{port}/health", timeout=5)
                if response.status_code == 200:
                    console.print(f"[green]✅ {username} is healthy[/green]")
                    return True
                else:
                    console.print(f"[yellow]⚠️  {username} started but health check failed[/yellow]")
                    return False
            except requests.RequestException as e:
                console.print(f"[yellow]⚠️  {username} started but not responding yet (may need wallet config)[/yellow]")
                return False

        except Exception as e:
            console.print(f"[red]❌ Failed to start {username}: {e}[/red]")
            return False

    def stop_all_agents(self):
        """Stop all running agents"""
        console.print("\n[cyan]🛑 Stopping all agents...[/cyan]")
        for agent in self.running_agents:
            try:
                agent["process"].terminate()
                console.print(f"[green]✅ Stopped {agent['username']}[/green]")
            except:
                pass
        self.running_agents = []

    def get_agent_card(self, url: str) -> Dict[str, Any]:
        """Fetch agent card via A2A protocol"""
        try:
            response = requests.get(f"{url}/.well-known/agent-card", timeout=5)
            if response.status_code == 200:
                return response.json()
            return None
        except:
            return None

    def get_services(self, url: str) -> List[Dict[str, Any]]:
        """Get agent services"""
        try:
            response = requests.get(f"{url}/services", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get("services", [])
            return []
        except:
            return []

    def demo_discovery(self):
        """Demo: Agent Discovery via A2A Protocol"""
        console.print(Panel.fit(
            "[bold cyan]Agent Discovery Demo[/bold cyan]\n"
            "Discovering agents via A2A protocol (/.well-known/agent-card)",
            title="🔍 Discovery"
        ))

        for agent in self.running_agents:
            console.print(f"\n[bold]Discovering: {agent['username']}[/bold]")
            console.print(f"URL: {agent['url']}")

            card = self.get_agent_card(agent['url'])
            if card:
                console.print("[green]✅ Agent Card Retrieved[/green]")

                # Display agent info
                table = Table(title=f"{card['agent']['name']}")
                table.add_column("Field", style="cyan")
                table.add_column("Value", style="white")

                table.add_row("ID", card['agent']['id'])
                table.add_row("Description", card['agent']['description'])
                table.add_row("Services", str(len(card['services'])))
                table.add_row("Protocols", ", ".join(card['capabilities']['protocols']))
                table.add_row("Payment Methods", ", ".join(card['capabilities']['payment_methods']))

                console.print(table)
            else:
                console.print("[red]❌ Failed to retrieve agent card[/red]")

    def demo_services(self):
        """Demo: Service Catalog"""
        console.print(Panel.fit(
            "[bold cyan]Service Catalog Demo[/bold cyan]\n"
            "Listing all services offered by running agents",
            title="🛒 Services"
        ))

        for agent in self.running_agents:
            console.print(f"\n[bold]{agent['username']}'s Services:[/bold]")

            services = self.get_services(agent['url'])
            if services:
                table = Table()
                table.add_column("Service ID", style="cyan")
                table.add_column("Name", style="white")
                table.add_column("Price", style="green")
                table.add_column("Confidence", style="yellow")

                for svc in services:
                    pricing = svc.get("pricing", {})
                    price = f"{pricing.get('amount', '?')} {pricing.get('currency', 'GLUE')}"
                    confidence = f"{svc.get('confidence', 0):.2f}"

                    table.add_row(
                        svc['id'],
                        svc['name'],
                        price,
                        confidence
                    )

                console.print(table)
            else:
                console.print("[red]❌ No services found[/red]")

    def demo_network_graph(self):
        """Demo: Network Visualization"""
        console.print(Panel.fit(
            "[bold cyan]Network Graph Demo[/bold cyan]\n"
            "Visualizing agent connections (potential trades)",
            title="🕸️  Network"
        ))

        tree = Tree("🌐 Karmacadabra Marketplace")

        for agent in self.running_agents:
            agent_branch = tree.add(f"[bold cyan]@{agent['username']}[/bold cyan] (:{agent['port']})")

            services = self.get_services(agent['url'])
            if services:
                services_branch = agent_branch.add(f"[green]Services ({len(services)})[/green]")
                for svc in services[:3]:  # Show first 3
                    pricing = svc.get("pricing", {})
                    price = f"{pricing.get('amount', '?')} {pricing.get('currency', 'GLUE')}"
                    services_branch.add(f"{svc['name']} - {price}")

                # Show potential buyers
                buyers_branch = agent_branch.add("[yellow]Can sell to (potential buyers)[/yellow]")
                for other in self.running_agents:
                    if other['username'] != agent['username']:
                        buyers_branch.add(f"@{other['username']}")

        console.print(tree)

        # Show network stats
        n = len(self.running_agents)
        potential_trades = n * (n - 1)

        stats_table = Table(title="Network Statistics")
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value", style="white")

        stats_table.add_row("Active Agents", str(n))
        stats_table.add_row("Potential Connections", str(potential_trades))
        stats_table.add_row("Network Density", f"{(potential_trades / (n * n) * 100):.1f}%")

        console.print("\n")
        console.print(stats_table)

    def demo_quick(self):
        """Quick 3-agent demo"""
        console.print(Panel.fit(
            "[bold cyan]Quick Marketplace Demo[/bold cyan]\n"
            "Starting 3 agents: elboorja, cymatix, eljuyan\n"
            "⚠️  Note: Agents may fail to initialize without wallet configuration\n"
            "This demo focuses on API endpoints that work without blockchain",
            title="🚀 Quick Demo"
        ))

        # Start agents
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Starting agents...", total=len(DEMO_AGENTS))

            for agent in DEMO_AGENTS:
                self.start_agent(agent['username'], agent['port'])
                progress.advance(task)

        if not self.running_agents:
            console.print("[red]❌ No agents started successfully. Check configuration.[/red]")
            return

        console.print(f"\n[green]✅ Started {len(self.running_agents)} agents[/green]\n")

        # Run demos
        input("\nPress Enter to see Agent Discovery demo...")
        self.demo_discovery()

        input("\nPress Enter to see Service Catalog demo...")
        self.demo_services()

        input("\nPress Enter to see Network Graph demo...")
        self.demo_network_graph()

        console.print("\n[green]✨ Demo Complete![/green]")

        # Cleanup
        self.stop_all_agents()

    def interactive_menu(self):
        """Interactive demo menu"""
        while True:
            console.clear()
            console.print(Panel.fit(
                "[bold cyan]Karmacadabra Marketplace Demo[/bold cyan]\n\n"
                "1. Quick Demo (3 agents)\n"
                "2. Agent Discovery\n"
                "3. Service Catalog\n"
                "4. Network Graph\n"
                "5. Start All 48 Agents (requires wallets)\n"
                "6. Exit\n",
                title="🎯 Main Menu"
            ))

            choice = input("\nSelect option (1-6): ").strip()

            if choice == "1":
                self.demo_quick()
                input("\nPress Enter to return to menu...")
            elif choice == "2":
                if not self.running_agents:
                    console.print("[yellow]⚠️  No agents running. Starting demo agents...[/yellow]")
                    for agent in DEMO_AGENTS:
                        self.start_agent(agent['username'], agent['port'])
                self.demo_discovery()
                input("\nPress Enter to return to menu...")
            elif choice == "3":
                if not self.running_agents:
                    console.print("[yellow]⚠️  No agents running. Starting demo agents...[/yellow]")
                    for agent in DEMO_AGENTS:
                        self.start_agent(agent['username'], agent['port'])
                self.demo_services()
                input("\nPress Enter to return to menu...")
            elif choice == "4":
                if not self.running_agents:
                    console.print("[yellow]⚠️  No agents running. Starting demo agents...[/yellow]")
                    for agent in DEMO_AGENTS:
                        self.start_agent(agent['username'], agent['port'])
                self.demo_network_graph()
                input("\nPress Enter to return to menu...")
            elif choice == "5":
                console.print("[yellow]⚠️  Starting all 48 agents requires wallet configuration[/yellow]")
                console.print("[yellow]Please configure wallets first (see README.md)[/yellow]")
                input("\nPress Enter to return to menu...")
            elif choice == "6":
                self.stop_all_agents()
                console.print("\n[cyan]👋 Goodbye![/cyan]")
                break
            else:
                console.print("[red]Invalid choice. Please select 1-6.[/red]")
                time.sleep(1)


def main():
    parser = argparse.ArgumentParser(description="Karmacadabra Marketplace Demo")
    parser.add_argument("--quick", action="store_true", help="Run quick 3-agent demo")
    parser.add_argument("--discovery", action="store_true", help="Run discovery demo")
    parser.add_argument("--services", action="store_true", help="Run services demo")
    parser.add_argument("--network", action="store_true", help="Run network graph demo")

    args = parser.parse_args()

    demo = MarketplaceDemo()

    try:
        if args.quick:
            demo.demo_quick()
        elif args.discovery:
            for agent in DEMO_AGENTS:
                demo.start_agent(agent['username'], agent['port'])
            demo.demo_discovery()
            demo.stop_all_agents()
        elif args.services:
            for agent in DEMO_AGENTS:
                demo.start_agent(agent['username'], agent['port'])
            demo.demo_services()
            demo.stop_all_agents()
        elif args.network:
            for agent in DEMO_AGENTS:
                demo.start_agent(agent['username'], agent['port'])
            demo.demo_network_graph()
            demo.stop_all_agents()
        else:
            demo.interactive_menu()
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Interrupted by user[/yellow]")
        demo.stop_all_agents()
    except Exception as e:
        console.print(f"\n[red]❌ Error: {e}[/red]")
        demo.stop_all_agents()
        raise


if __name__ == "__main__":
    main()
