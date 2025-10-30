#!/usr/bin/env python3
"""
Generate Network Graph from Week 2 Transaction Data

This script creates Diagram 7: Network Graph showing 47 agents and 78 edges
with centrality visualization (node size = degree, color = betweenness).

Usage:
    python generate_network_graph.py

Output:
    7-network-graph-47-agents.png (1920x1440, 300 DPI)
"""

import sys
import os
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

try:
    import networkx as nx
    import matplotlib.pyplot as plt
    import pandas as pd
    import numpy as np
except ImportError as e:
    print(f"Error: Missing dependency - {e}")
    print("\nInstall dependencies:")
    print("  pip install networkx matplotlib pandas numpy")
    sys.exit(1)


def load_transaction_data():
    """Load Week 2 transaction data from CSV."""
    csv_path = Path(__file__).parent.parent.parent / "week2" / "transactions_20251029_093847.csv"

    if not csv_path.exists():
        print(f"Error: Transaction data not found at {csv_path}")
        print("\nExpected location: contribution/week2/transactions_20251029_093847.csv")
        print("Run Week 2 simulation first: python scripts/simulate_marketplace.py")
        sys.exit(1)

    print(f"Loading transaction data from {csv_path}...")
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} transactions")
    return df


def build_graph(df):
    """Build directed graph from transaction data."""
    print("\nBuilding directed graph...")
    G = nx.DiGraph()

    for _, tx in df.iterrows():
        client_id = tx['client_id']
        server_id = tx['server_id']
        rating = tx['rating']

        # Add edge with rating as weight
        G.add_edge(client_id, server_id, rating=rating)

    print(f"Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    return G


def calculate_centrality(G):
    """Calculate centrality metrics for all nodes."""
    print("\nCalculating centrality metrics...")

    degree_cent = nx.degree_centrality(G)
    betweenness_cent = nx.betweenness_centrality(G)
    closeness_cent = nx.closeness_centrality(G)

    # Sort by degree centrality (most connected)
    top_degree = sorted(degree_cent.items(), key=lambda x: x[1], reverse=True)[:5]
    print("\nTop 5 by Degree Centrality (most connections):")
    for node, cent in top_degree:
        print(f"  Agent {node}: {cent:.3f}")

    # Sort by betweenness centrality (critical bridges)
    top_betweenness = sorted(betweenness_cent.items(), key=lambda x: x[1], reverse=True)[:5]
    print("\nTop 5 by Betweenness Centrality (critical bridges):")
    for node, cent in top_betweenness:
        print(f"  Agent {node}: {cent:.3f}")

    return degree_cent, betweenness_cent, closeness_cent


def create_visualization(G, degree_cent, betweenness_cent, output_path):
    """Create network visualization with centrality."""
    print("\nCreating visualization...")

    # Layout
    print("  Computing spring layout (this may take a moment)...")
    pos = nx.spring_layout(G, k=0.5, iterations=50, seed=42)

    # Node sizes based on degree centrality (more connections = larger)
    node_sizes = [degree_cent[node] * 3000 for node in G.nodes()]

    # Node colors based on betweenness centrality (critical bridges = darker)
    node_colors = [betweenness_cent[node] for node in G.nodes()]

    # Create figure
    plt.figure(figsize=(16, 12))

    # Draw network
    print("  Drawing nodes and edges...")
    nx.draw_networkx_nodes(
        G, pos,
        node_size=node_sizes,
        node_color=node_colors,
        cmap='viridis',
        alpha=0.8,
        edgecolors='black',
        linewidths=0.5
    )

    nx.draw_networkx_edges(
        G, pos,
        arrows=True,
        arrowsize=10,
        edge_color='gray',
        alpha=0.3,
        width=0.5,
        connectionstyle='arc3,rad=0.1'  # Curved edges for better visibility
    )

    nx.draw_networkx_labels(
        G, pos,
        font_size=6,
        font_family='sans-serif',
        font_weight='bold'
    )

    # Title and legend
    plt.title('Karmacadabra Agent Network\n47 Agents, 78 Bidirectional Connections',
              fontsize=16, fontweight='bold', pad=20)

    # Color bar for betweenness centrality
    sm = plt.cm.ScalarMappable(cmap='viridis',
                                norm=plt.Normalize(vmin=min(node_colors),
                                                  vmax=max(node_colors)))
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=plt.gca(), fraction=0.046, pad=0.04)
    cbar.set_label('Betweenness Centrality\n(Critical Bridge Importance)',
                   rotation=270, labelpad=20, fontsize=10)

    # Legend for node size
    legend_elements = [
        plt.scatter([], [], s=100, c='gray', alpha=0.6, label='Low Degree'),
        plt.scatter([], [], s=500, c='gray', alpha=0.6, label='Medium Degree'),
        plt.scatter([], [], s=1000, c='gray', alpha=0.6, label='High Degree (Hub)')
    ]
    plt.legend(handles=legend_elements, loc='upper right', title='Node Size = Degree Centrality')

    plt.axis('off')
    plt.tight_layout()

    # Save
    print(f"  Saving to {output_path}...")
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"✅ Network graph saved to {output_path}")

    # File size
    file_size_kb = os.path.getsize(output_path) / 1024
    print(f"   File size: {file_size_kb:.1f} KB")


def print_statistics(G, degree_cent, betweenness_cent):
    """Print network statistics."""
    print("\n" + "="*60)
    print("NETWORK STATISTICS")
    print("="*60)

    print(f"\nBasic Metrics:")
    print(f"  Nodes (agents): {G.number_of_nodes()}")
    print(f"  Edges (transactions): {G.number_of_edges()}")
    print(f"  Density: {nx.density(G):.4f} ({nx.density(G)*100:.2f}%)")
    print(f"  Average degree: {sum(dict(G.degree()).values()) / G.number_of_nodes():.2f}")

    print(f"\nConnectivity:")
    if nx.is_strongly_connected(G):
        print(f"  Strongly connected: Yes")
    else:
        print(f"  Strongly connected: No")
        print(f"  Weakly connected components: {nx.number_weakly_connected_components(G)}")

    print(f"\nCentrality Ranges:")
    print(f"  Degree centrality: {min(degree_cent.values()):.3f} - {max(degree_cent.values()):.3f}")
    print(f"  Betweenness centrality: {min(betweenness_cent.values()):.3f} - {max(betweenness_cent.values()):.3f}")

    print(f"\nKey Insight:")
    top_hub = max(degree_cent, key=degree_cent.get)
    top_bridge = max(betweenness_cent, key=betweenness_cent.get)
    print(f"  Most connected (hub): Agent {top_hub} (degree: {degree_cent[top_hub]:.3f})")
    print(f"  Most critical (bridge): Agent {top_bridge} (betweenness: {betweenness_cent[top_bridge]:.3f})")

    if top_hub == top_bridge:
        print(f"  → Agent {top_hub} is both hub AND bridge (single point of failure!)")
    else:
        print(f"  → Different agents serve different roles (distributed network)")


def main():
    """Main execution."""
    print("="*60)
    print("NETWORK GRAPH GENERATOR")
    print("="*60)

    # Load data
    df = load_transaction_data()

    # Build graph
    G = build_graph(df)

    # Calculate centrality
    degree_cent, betweenness_cent, closeness_cent = calculate_centrality(G)

    # Create visualization
    output_path = Path(__file__).parent / "7-network-graph-47-agents.png"
    create_visualization(G, degree_cent, betweenness_cent, output_path)

    # Print statistics
    print_statistics(G, degree_cent, betweenness_cent)

    print("\n" + "="*60)
    print("✅ DONE")
    print("="*60)
    print(f"\nOutput: {output_path}")
    print("Use in: Blog post, case study, presentations")


if __name__ == "__main__":
    main()
