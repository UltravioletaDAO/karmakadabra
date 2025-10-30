#!/usr/bin/env python3
"""
Statistical analysis of Week 2 Day 3 marketplace simulation data.
Analyzes 99 real blockchain transactions from Avalanche Fuji testnet.

This script performs comprehensive analysis including:
- Rating distributions and asymmetries
- Gas cost analysis and projections
- Network graph of agent interactions
- Temporal patterns and throughput
"""

import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import networkx as nx
from pathlib import Path
from datetime import datetime
from collections import Counter
import numpy as np

# Configure plotting
sns.set_theme(style="whitegrid")
plt.rcParams['figure.figsize'] = (12, 8)
plt.rcParams['figure.dpi'] = 100

def load_data(json_path: str) -> pd.DataFrame:
    """Load transaction data from JSON file."""
    with open(json_path) as f:
        data = json.load(f)
    df = pd.DataFrame(data)

    # Convert timestamp to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    return df

def print_basic_stats(df: pd.DataFrame):
    """Print basic statistics about the dataset."""
    print("=" * 70)
    print("📊 BASIC STATISTICS")
    print("=" * 70)
    print(f"Total transactions: {len(df)}")
    print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"Time span: {(df['timestamp'].max() - df['timestamp'].min()).total_seconds():.1f} seconds")
    print(f"\nUnique buyers: {df['buyer_name'].nunique()}")
    print(f"Unique sellers: {df['seller_name'].nunique()}")
    print(f"\nScenarios distribution:")
    for scenario, count in df['scenario'].value_counts().items():
        print(f"  - {scenario}: {count} ({count/len(df)*100:.1f}%)")
    print()

def analyze_ratings(df: pd.DataFrame, output_dir: Path):
    """Analyze rating distributions and asymmetries."""
    print("=" * 70)
    print("⭐ RATING ANALYSIS")
    print("=" * 70)

    # Basic rating statistics
    print(f"Buyer ratings  - Mean: {df['buyer_rating'].mean():.2f}, Median: {df['buyer_rating'].median():.0f}, Std: {df['buyer_rating'].std():.2f}")
    print(f"Seller ratings - Mean: {df['seller_rating'].mean():.2f}, Median: {df['seller_rating'].median():.0f}, Std: {df['seller_rating'].std():.2f}")
    print(f"Rating diff    - Mean: {df['rating_diff'].mean():.2f}, Median: {df['rating_diff'].median():.0f}, Std: {df['rating_diff'].std():.2f}")

    # Detect asymmetries
    buyer_higher = (df['rating_diff'] > 0).sum()
    seller_higher = (df['rating_diff'] < 0).sum()
    equal = (df['rating_diff'] == 0).sum()
    print(f"\n🔍 Asymmetry Analysis:")
    print(f"  Buyer rated higher:  {buyer_higher} ({buyer_higher/len(df)*100:.1f}%)")
    print(f"  Seller rated higher: {seller_higher} ({seller_higher/len(df)*100:.1f}%)")
    print(f"  Equal ratings:       {equal} ({equal/len(df)*100:.1f}%)")

    # Create visualizations
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))

    # 1. Buyer rating distribution
    axes[0, 0].hist(df['buyer_rating'], bins=20, color='skyblue', edgecolor='black', alpha=0.7)
    axes[0, 0].axvline(df['buyer_rating'].mean(), color='red', linestyle='--', label=f'Mean: {df["buyer_rating"].mean():.1f}')
    axes[0, 0].set_xlabel('Buyer Rating')
    axes[0, 0].set_ylabel('Frequency')
    axes[0, 0].set_title('Distribution of Buyer Ratings')
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)

    # 2. Seller rating distribution
    axes[0, 1].hist(df['seller_rating'], bins=20, color='lightcoral', edgecolor='black', alpha=0.7)
    axes[0, 1].axvline(df['seller_rating'].mean(), color='red', linestyle='--', label=f'Mean: {df["seller_rating"].mean():.1f}')
    axes[0, 1].set_xlabel('Seller Rating')
    axes[0, 1].set_ylabel('Frequency')
    axes[0, 1].set_title('Distribution of Seller Ratings')
    axes[0, 1].legend()
    axes[0, 1].grid(True, alpha=0.3)

    # 3. Rating difference distribution
    axes[1, 0].hist(df['rating_diff'], bins=30, color='lightgreen', edgecolor='black', alpha=0.7)
    axes[1, 0].axvline(0, color='red', linestyle='--', linewidth=2, label='Equal ratings')
    axes[1, 0].axvline(df['rating_diff'].mean(), color='blue', linestyle='--', label=f'Mean: {df["rating_diff"].mean():.1f}')
    axes[1, 0].set_xlabel('Rating Difference (Buyer - Seller)')
    axes[1, 0].set_ylabel('Frequency')
    axes[1, 0].set_title('Distribution of Rating Differences')
    axes[1, 0].legend()
    axes[1, 0].grid(True, alpha=0.3)

    # 4. Scatter plot: buyer vs seller ratings
    axes[1, 1].scatter(df['buyer_rating'], df['seller_rating'], alpha=0.5, s=50)
    axes[1, 1].plot([0, 100], [0, 100], 'r--', linewidth=2, label='Equal ratings line')
    axes[1, 1].set_xlabel('Buyer Rating')
    axes[1, 1].set_ylabel('Seller Rating')
    axes[1, 1].set_title('Buyer vs Seller Ratings')
    axes[1, 1].legend()
    axes[1, 1].grid(True, alpha=0.3)
    axes[1, 1].set_xlim(0, 100)
    axes[1, 1].set_ylim(0, 100)

    plt.tight_layout()
    output_path = output_dir / "day4_rating_analysis.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n✅ Rating visualizations saved to: {output_path}")
    plt.close()

    # Scenario-based analysis
    print(f"\n📋 Rating by Scenario:")
    for scenario in df['scenario'].unique():
        scenario_df = df[df['scenario'] == scenario]
        print(f"  {scenario}:")
        print(f"    Buyer:  {scenario_df['buyer_rating'].mean():.1f} ± {scenario_df['buyer_rating'].std():.1f}")
        print(f"    Seller: {scenario_df['seller_rating'].mean():.1f} ± {scenario_df['seller_rating'].std():.1f}")
    print()

def analyze_gas_costs(df: pd.DataFrame, output_dir: Path):
    """Analyze gas consumption patterns."""
    print("=" * 70)
    print("⛽ GAS COST ANALYSIS")
    print("=" * 70)

    # Basic gas statistics
    print(f"Gas used - Mean: {df['gas_used'].mean():.0f}, Median: {df['gas_used'].median():.0f}, Std: {df['gas_used'].std():.0f}")
    print(f"Gas used - Min: {df['gas_used'].min():.0f}, Max: {df['gas_used'].max():.0f}")
    print(f"Total gas consumed: {df['gas_used'].sum():,}")

    # Cost projections (example prices)
    # Avalanche Fuji testnet vs mainnet estimates
    AVAX_PRICE = 30  # USD (example)
    GWEI_TO_AVAX = 1e-9
    GAS_PRICE_FUJI = 25  # nAVAX (25 Gwei)
    GAS_PRICE_MAINNET = 25  # nAVAX (can be higher on mainnet)

    avg_cost_fuji = df['gas_used'].mean() * GAS_PRICE_FUJI * GWEI_TO_AVAX
    total_cost_fuji = df['gas_used'].sum() * GAS_PRICE_FUJI * GWEI_TO_AVAX

    print(f"\n💰 Cost Estimates (Fuji testnet at 25 nAVAX gas price):")
    print(f"  Average per transaction: {avg_cost_fuji:.6f} AVAX (${avg_cost_fuji * AVAX_PRICE:.4f})")
    print(f"  Total for 99 transactions: {total_cost_fuji:.6f} AVAX (${total_cost_fuji * AVAX_PRICE:.4f})")

    # Mainnet projection
    avg_cost_mainnet = df['gas_used'].mean() * GAS_PRICE_MAINNET * GWEI_TO_AVAX
    total_cost_mainnet = df['gas_used'].sum() * GAS_PRICE_MAINNET * GWEI_TO_AVAX

    print(f"\n🌐 Mainnet Projection (25 nAVAX gas price, ${AVAX_PRICE} AVAX):")
    print(f"  Average per transaction: {avg_cost_mainnet:.6f} AVAX (${avg_cost_mainnet * AVAX_PRICE:.4f})")
    print(f"  Total for 99 transactions: {total_cost_mainnet:.6f} AVAX (${total_cost_mainnet * AVAX_PRICE:.4f})")
    print(f"  Per 1,000 transactions: {avg_cost_mainnet * 1000:.4f} AVAX (${avg_cost_mainnet * 1000 * AVAX_PRICE:.2f})")
    print(f"  Per 10,000 transactions: {avg_cost_mainnet * 10000:.4f} AVAX (${avg_cost_mainnet * 10000 * AVAX_PRICE:.2f})")

    # Create visualizations
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))

    # 1. Gas distribution
    axes[0, 0].hist(df['gas_used'], bins=20, color='orange', edgecolor='black', alpha=0.7)
    axes[0, 0].axvline(df['gas_used'].mean(), color='red', linestyle='--', label=f'Mean: {df["gas_used"].mean():.0f}')
    axes[0, 0].set_xlabel('Gas Used')
    axes[0, 0].set_ylabel('Frequency')
    axes[0, 0].set_title('Distribution of Gas Consumption')
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)

    # 2. Gas by scenario (box plot)
    scenario_gas = [df[df['scenario'] == s]['gas_used'].values for s in df['scenario'].unique()]
    axes[0, 1].boxplot(scenario_gas, tick_labels=df['scenario'].unique())
    axes[0, 1].set_xlabel('Scenario')
    axes[0, 1].set_ylabel('Gas Used')
    axes[0, 1].set_title('Gas Consumption by Scenario')
    axes[0, 1].grid(True, alpha=0.3)
    plt.setp(axes[0, 1].xaxis.get_majorticklabels(), rotation=45, ha='right')

    # 3. Gas over time
    axes[1, 0].plot(range(len(df)), df['gas_used'], marker='o', linestyle='-', alpha=0.6, markersize=4)
    axes[1, 0].axhline(df['gas_used'].mean(), color='red', linestyle='--', label=f'Mean: {df["gas_used"].mean():.0f}')
    axes[1, 0].set_xlabel('Transaction Index')
    axes[1, 0].set_ylabel('Gas Used')
    axes[1, 0].set_title('Gas Consumption Over Time')
    axes[1, 0].legend()
    axes[1, 0].grid(True, alpha=0.3)

    # 4. Cumulative gas consumption
    axes[1, 1].plot(range(len(df)), df['gas_used'].cumsum(), marker='', linestyle='-', linewidth=2, color='green')
    axes[1, 1].set_xlabel('Transaction Index')
    axes[1, 1].set_ylabel('Cumulative Gas Used')
    axes[1, 1].set_title('Cumulative Gas Consumption')
    axes[1, 1].grid(True, alpha=0.3)
    axes[1, 1].ticklabel_format(style='plain', axis='y')

    plt.tight_layout()
    output_path = output_dir / "day4_gas_analysis.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n✅ Gas visualizations saved to: {output_path}")
    plt.close()

    # Gas by scenario statistics
    print(f"\n📋 Gas Usage by Scenario:")
    for scenario in df['scenario'].unique():
        scenario_df = df[df['scenario'] == scenario]
        print(f"  {scenario}: {scenario_df['gas_used'].mean():.0f} ± {scenario_df['gas_used'].std():.0f}")
    print()

def analyze_network(df: pd.DataFrame, output_dir: Path):
    """Create network graph of agent interactions."""
    print("=" * 70)
    print("🕸️  NETWORK ANALYSIS")
    print("=" * 70)

    # Build directed graph (buyer -> seller)
    G = nx.DiGraph()

    # Add edges with weights (number of transactions)
    edge_weights = {}
    for _, row in df.iterrows():
        buyer = row['buyer_name']
        seller = row['seller_name']
        edge = (buyer, seller)
        edge_weights[edge] = edge_weights.get(edge, 0) + 1

    for (buyer, seller), weight in edge_weights.items():
        G.add_edge(buyer, seller, weight=weight)

    print(f"Network nodes (agents): {G.number_of_nodes()}")
    print(f"Network edges (unique interactions): {G.number_of_edges()}")
    print(f"Total transactions: {sum(edge_weights.values())}")

    # Calculate centrality measures
    in_degree = dict(G.in_degree())
    out_degree = dict(G.out_degree())

    print(f"\n📊 Top Sellers (most incoming transactions):")
    top_sellers = sorted(in_degree.items(), key=lambda x: x[1], reverse=True)[:5]
    for agent, count in top_sellers:
        print(f"  {agent}: {count} incoming transactions")

    print(f"\n📊 Top Buyers (most outgoing transactions):")
    top_buyers = sorted(out_degree.items(), key=lambda x: x[1], reverse=True)[:5]
    for agent, count in top_buyers:
        print(f"  {agent}: {count} outgoing transactions")

    # Average ratings by agent
    print(f"\n⭐ Average Ratings by Agent:")

    # As buyer
    buyer_ratings = df.groupby('buyer_name')['buyer_rating'].agg(['mean', 'count'])
    buyer_ratings = buyer_ratings.sort_values('mean', ascending=False)
    print(f"\n  As Buyer:")
    for agent, row in buyer_ratings.head(5).iterrows():
        print(f"    {agent}: {row['mean']:.1f} (n={int(row['count'])})")

    # As seller
    seller_ratings = df.groupby('seller_name')['seller_rating'].agg(['mean', 'count'])
    seller_ratings = seller_ratings.sort_values('mean', ascending=False)
    print(f"\n  As Seller:")
    for agent, row in seller_ratings.head(5).iterrows():
        print(f"    {agent}: {row['mean']:.1f} (n={int(row['count'])})")

    # Create network visualization
    fig, ax = plt.subplots(figsize=(16, 12))

    # Use spring layout for better visualization
    pos = nx.spring_layout(G, k=2, iterations=50, seed=42)

    # Draw nodes
    node_sizes = [300 + (in_degree.get(node, 0) + out_degree.get(node, 0)) * 100 for node in G.nodes()]
    nx.draw_networkx_nodes(G, pos, node_size=node_sizes, node_color='lightblue',
                          alpha=0.7, edgecolors='black', linewidths=2, ax=ax)

    # Draw edges with varying widths based on weight
    edges = G.edges()
    weights = [G[u][v]['weight'] for u, v in edges]
    nx.draw_networkx_edges(G, pos, width=[w * 0.5 for w in weights],
                          alpha=0.4, edge_color='gray',
                          arrows=True, arrowsize=15, ax=ax,
                          connectionstyle='arc3,rad=0.1')

    # Draw labels
    nx.draw_networkx_labels(G, pos, font_size=9, font_weight='bold', ax=ax)

    ax.set_title('Agent Interaction Network\n(Node size = total transactions, Edge width = transaction count)',
                fontsize=14, fontweight='bold', pad=20)
    ax.axis('off')

    plt.tight_layout()
    output_path = output_dir / "day4_network_graph.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n✅ Network graph saved to: {output_path}")
    plt.close()
    print()

def analyze_temporal(df: pd.DataFrame, output_dir: Path):
    """Analyze temporal patterns and throughput."""
    print("=" * 70)
    print("⏱️  TEMPORAL ANALYSIS")
    print("=" * 70)

    # Calculate block time differences
    df_sorted = df.sort_values('block_number')
    df_sorted['block_diff'] = df_sorted['block_number'].diff()
    df_sorted['time_diff'] = df_sorted['timestamp'].diff().dt.total_seconds()

    # Remove first row (NaN from diff)
    df_sorted = df_sorted.dropna(subset=['block_diff', 'time_diff'])

    print(f"Average block difference: {df_sorted['block_diff'].mean():.2f} blocks")
    print(f"Average time between transactions: {df_sorted['time_diff'].mean():.2f} seconds")
    print(f"Transactions per minute: {60 / df_sorted['time_diff'].mean():.2f}")

    # Block time analysis (Avalanche Fuji typically ~2s)
    block_times = df_sorted[df_sorted['block_diff'] == 1]['time_diff']
    if len(block_times) > 0:
        print(f"\nBlock time analysis (consecutive blocks only):")
        print(f"  Mean: {block_times.mean():.2f}s")
        print(f"  Median: {block_times.median():.2f}s")
        print(f"  Std: {block_times.std():.2f}s")
        print(f"  Min: {block_times.min():.2f}s")
        print(f"  Max: {block_times.max():.2f}s")

    # Create visualizations
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))

    # 1. Transactions over time
    axes[0, 0].plot(df['timestamp'], range(len(df)), marker='o', linestyle='-', markersize=3)
    axes[0, 0].set_xlabel('Timestamp')
    axes[0, 0].set_ylabel('Transaction Count')
    axes[0, 0].set_title('Transactions Over Time')
    axes[0, 0].grid(True, alpha=0.3)
    plt.setp(axes[0, 0].xaxis.get_majorticklabels(), rotation=45, ha='right')

    # 2. Block number progression
    axes[0, 1].plot(range(len(df)), df['block_number'], marker='o', linestyle='-', markersize=4, alpha=0.6)
    axes[0, 1].set_xlabel('Transaction Index')
    axes[0, 1].set_ylabel('Block Number')
    axes[0, 1].set_title('Block Number Progression')
    axes[0, 1].grid(True, alpha=0.3)

    # 3. Time between transactions
    if len(df_sorted) > 0:
        axes[1, 0].hist(df_sorted['time_diff'], bins=20, color='purple', edgecolor='black', alpha=0.7)
        axes[1, 0].axvline(df_sorted['time_diff'].mean(), color='red', linestyle='--',
                          label=f'Mean: {df_sorted["time_diff"].mean():.2f}s')
        axes[1, 0].set_xlabel('Time Between Transactions (seconds)')
        axes[1, 0].set_ylabel('Frequency')
        axes[1, 0].set_title('Distribution of Inter-Transaction Time')
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3)

    # 4. Block differences
    if len(df_sorted) > 0:
        axes[1, 1].hist(df_sorted['block_diff'], bins=20, color='teal', edgecolor='black', alpha=0.7)
        axes[1, 1].set_xlabel('Block Difference')
        axes[1, 1].set_ylabel('Frequency')
        axes[1, 1].set_title('Distribution of Block Differences')
        axes[1, 1].grid(True, alpha=0.3)

    plt.tight_layout()
    output_path = output_dir / "day4_temporal_analysis.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n✅ Temporal visualizations saved to: {output_path}")
    plt.close()
    print()

def generate_summary_stats(df: pd.DataFrame) -> dict:
    """Generate summary statistics for the report."""
    stats = {
        'total_transactions': len(df),
        'unique_buyers': df['buyer_name'].nunique(),
        'unique_sellers': df['seller_name'].nunique(),
        'avg_buyer_rating': df['buyer_rating'].mean(),
        'avg_seller_rating': df['seller_rating'].mean(),
        'avg_rating_diff': df['rating_diff'].mean(),
        'avg_gas_used': df['gas_used'].mean(),
        'total_gas_used': df['gas_used'].sum(),
        'min_gas': df['gas_used'].min(),
        'max_gas': df['gas_used'].max(),
        'date_range': (df['timestamp'].min(), df['timestamp'].max()),
        'time_span_seconds': (df['timestamp'].max() - df['timestamp'].min()).total_seconds(),
        'scenarios': df['scenario'].value_counts().to_dict(),
    }
    return stats

def main():
    """Main analysis execution."""
    print("\n" + "=" * 70)
    print("🚀 KARMACADABRA - WEEK 2 DAY 4: DATA ANALYSIS")
    print("=" * 70)
    print("Analyzing 99 real blockchain transactions from Avalanche Fuji testnet")
    print("=" * 70 + "\n")

    # Setup paths
    script_dir = Path(__file__).parent
    data_path = script_dir / "day3_full_100tx.json"
    output_dir = script_dir.parent / "data"

    # Create output directory if it doesn't exist
    output_dir.mkdir(exist_ok=True)

    # Load data
    print(f"📂 Loading data from: {data_path}")
    df = load_data(data_path)
    print(f"✅ Loaded {len(df)} transactions\n")

    # Run analyses
    print_basic_stats(df)
    analyze_ratings(df, output_dir)
    analyze_gas_costs(df, output_dir)
    analyze_network(df, output_dir)
    analyze_temporal(df, output_dir)

    # Generate summary stats for report
    stats = generate_summary_stats(df)

    # Save summary stats to JSON
    summary_path = output_dir / "day4_summary_stats.json"
    with open(summary_path, 'w') as f:
        # Convert datetime objects and numpy types to native Python types for JSON serialization
        stats_json = stats.copy()
        stats_json['date_range'] = [dt.isoformat() for dt in stats['date_range']]
        stats_json['total_transactions'] = int(stats['total_transactions'])
        stats_json['unique_buyers'] = int(stats['unique_buyers'])
        stats_json['unique_sellers'] = int(stats['unique_sellers'])
        stats_json['avg_buyer_rating'] = float(stats['avg_buyer_rating'])
        stats_json['avg_seller_rating'] = float(stats['avg_seller_rating'])
        stats_json['avg_rating_diff'] = float(stats['avg_rating_diff'])
        stats_json['avg_gas_used'] = float(stats['avg_gas_used'])
        stats_json['total_gas_used'] = int(stats['total_gas_used'])
        stats_json['min_gas'] = int(stats['min_gas'])
        stats_json['max_gas'] = int(stats['max_gas'])
        stats_json['time_span_seconds'] = float(stats['time_span_seconds'])
        stats_json['scenarios'] = {k: int(v) for k, v in stats['scenarios'].items()}
        json.dump(stats_json, f, indent=2)
    print(f"📊 Summary statistics saved to: {summary_path}")

    print("\n" + "=" * 70)
    print("✅ ANALYSIS COMPLETE!")
    print("=" * 70)
    print(f"Generated files in {output_dir}:")
    print("  - day4_rating_analysis.png")
    print("  - day4_gas_analysis.png")
    print("  - day4_network_graph.png")
    print("  - day4_temporal_analysis.png")
    print("  - day4_summary_stats.json")
    print("\nNext step: Create 2.9-DAY4-DATA-ANALYSIS.md report")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()
