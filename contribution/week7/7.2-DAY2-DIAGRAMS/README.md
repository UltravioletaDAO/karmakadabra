# Visual Diagrams: EIP-8004a Bidirectional Trust

**Purpose:** Visual communication materials for blog posts, presentations, and documentation
**Format:** Mermaid (text-based, version-controllable, embeddable in Markdown)
**Date:** October 30, 2025

---

## Diagram Index

| # | Diagram | Type | Purpose | Source File |
|---|---------|------|---------|-------------|
| 1 | **System Architecture (4 Layers)** | Graph | Show complete stack from blockchain to AI agents | `1-architecture-4-layers.mmd` |
| 2 | **Transaction Flow (End-to-End)** | Sequence | Show bidirectional trust in action (discovery → rating) | `2-transaction-flow-end-to-end.mmd` |
| 3 | **Rating Lifecycle** | State | Show how ratings transition from non-existent to permanent | `3-state-transitions-rating.mmd` |
| 4 | **Symmetric vs Asymmetric Trust** | Comparison | Show why bidirectional prevents abuse (eBay vs our protocol) | `4-symmetric-vs-asymmetric.mmd` |
| 5 | **Sybil Detection Flowchart** | Flowchart | Show multi-signal detection approach (91% accuracy) | `5-sybil-detection-flowchart.mmd` |
| 6 | **Commit-Reveal Sequence (V2)** | Sequence | Show anti-retaliation scheme (Airbnb-style) | `6-commit-reveal-sequence.mmd` |
| 7 | **Network Graph (47 Agents)** | Graph | Show agent network with centrality (karma-hello as hub) | *(Generated from NetworkX, see below)* |

---

## How to Use These Diagrams

### Embedding in Markdown

**GitHub/GitLab automatically render Mermaid diagrams:**

```markdown
# System Architecture

```mermaid
graph TB
    ... (paste Mermaid code here)
```
```

**Example:**

See `contribution/week6/6.3-BLOG-POST.md` for embedded diagrams.

---

### Rendering to PNG/SVG

**Option 1: Mermaid CLI (recommended)**

```bash
# Install Mermaid CLI
npm install -g @mermaid-js/mermaid-cli

# Convert single diagram
mmdc -i 1-architecture-4-layers.mmd -o 1-architecture-4-layers.png -w 1920 -H 1080

# Convert all diagrams
for f in *.mmd; do mmdc -i "$f" -o "${f%.mmd}.png" -w 1920 -H 1080; done

# Convert to SVG (vector, scalable)
mmdc -i 1-architecture-4-layers.mmd -o 1-architecture-4-layers.svg
```

**Option 2: Online Editor**

1. Visit https://mermaid.live/
2. Paste Mermaid code
3. Click "Export" → PNG/SVG

**Option 3: VSCode Extension**

1. Install "Markdown Preview Mermaid Support" extension
2. Open `.mmd` file
3. Right-click diagram → "Export to PNG"

---

### Customization

**Color Schemes:**

Mermaid supports custom styling via `classDef`:

```mermaid
classDef errorNode fill:#ffebee,stroke:#c62828,stroke-width:2px
classDef successNode fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px

class SYBIL_DETECTED errorNode
class LEGITIMATE_AGENT successNode
```

**Current color scheme:**
- **Layer 1 (Blockchain):** Blue (#e1f5ff)
- **Layer 2 (Contracts):** Orange (#fff3e0)
- **Layer 3 (Facilitator):** Purple (#f3e5f5)
- **Layer 4 (Agents):** Green (#e8f5e9)
- **Errors/Attacks:** Red (#ffebee)
- **Success/Legitimate:** Green (#e8f5e9)

---

## Diagram Descriptions

### 1. System Architecture (4 Layers)

**Shows:**
- Layer 4: AI Agents (karma-hello, abracadabra, skill-extractor, voice-extractor, validator, 48 clients)
- Layer 3: Payment Facilitator (x402-rs, Rust, stateless)
- Layer 2: Smart Contracts (GLUE, IdentityRegistry, ReputationRegistry, ValidationRegistry)
- Layer 1: Blockchain (Avalanche Fuji, 2s blocks, 15M gas limit)

**Use cases:**
- System overview for presentations
- Architecture documentation
- Explaining stack to developers

---

### 2. Transaction Flow (End-to-End)

**Shows:**
- Step 1: Discovery (A2A protocol, agent-card.json)
- Step 2: Reputation check (NEW: bidirectional, both parties check each other)
- Step 3: Payment authorization (EIP-3009, gasless)
- Step 4: Service delivery (HTTP 402)
- Step 5: Mutual rating (NEW: both parties rate each other)

**Real example:** abracadabra buys logs from karma-hello (0.01 GLUE), both rate 95-97/100

**Use cases:**
- Blog post illustrations
- Developer integration guide
- Explaining bidirectional trust to non-technical audiences

---

### 3. Rating Lifecycle

**Shows:**
- State 1: NoRating (initial, no prior transaction)
- State 2: PendingRating (transaction in mempool)
- State 3: ConfirmedRating (transaction mined, 1 block ~2s)
- State 4: Queryable (rating permanent, public, immutable)
- Edge case: Failed (transaction reverts, can retry)

**Use cases:**
- Technical documentation (state machines)
- Explaining immutability to skeptics
- Developer integration guide (when to query ratings)

---

### 4. Symmetric vs Asymmetric Trust

**Shows:**
- **Asymmetric (eBay):** Buyers rate sellers ✅, sellers can't rate buyers ❌ → $1.8B losses
- **Symmetric (Our Protocol):** Both parties rate each other ✅ → Zero fraud (99 tx)
- **Evidence:** Uber (131M users), Airbnb (150M users) prove bidirectional works at scale

**Use cases:**
- Explaining problem to non-technical audiences
- Motivating EIP reviewers (why this matters)
- Blog post hero image (visual impact)

---

### 5. Sybil Detection Flowchart

**Shows:**
- **Multi-signal approach:** Graph clustering (95%), temporal (80%), statistical (75%), transaction (100%)
- **Decision logic:** 2+ flags → Sybil detected, 0-1 flags → Legitimate
- **Economic deterrent:** $13 attack cost, 95% detection → -$2.35 expected value (unprofitable)

**Use cases:**
- Security documentation
- Addressing skeptics ("what about Sybil attacks?")
- Technical presentations

---

### 6. Commit-Reveal Sequence (V2)

**Shows:**
- **Phase 1:** Transaction completes (both parties have opinion)
- **Phase 2:** Commit phase (ratings hidden via keccak256 hash)
- **Phase 3:** Wait period (24h or both committed)
- **Phase 4:** Reveal phase (simultaneous, prevents retaliation)
- **Edge cases:** One party never reveals (24h timeout), hash mismatch (retry), front-running (irrelevant)

**Inspired by:** Airbnb dual-blind review window (14 days)

**Use cases:**
- V2 roadmap documentation
- Addressing retaliation concerns
- Technical deep dive (cryptographic commit-reveal)

---

### 7. Network Graph (47 Agents)

**Generated from NetworkX (Python):**

```python
import networkx as nx
import matplotlib.pyplot as plt
import pandas as pd

# Load transaction data
df = pd.read_csv('contribution/week2/transactions_20251029_093847.csv')

# Build directed graph
G = nx.DiGraph()
for _, tx in df.iterrows():
    G.add_edge(tx['client_id'], tx['server_id'], rating=tx['rating'])

# Calculate centrality
degree_centrality = nx.degree_centrality(G)
betweenness_centrality = nx.betweenness_centrality(G)

# Draw graph
pos = nx.spring_layout(G, k=0.5, iterations=50)
node_sizes = [degree_centrality[node] * 3000 for node in G.nodes()]
node_colors = [betweenness_centrality[node] for node in G.nodes()]

plt.figure(figsize=(16, 12))
nx.draw_networkx(
    G, pos,
    node_size=node_sizes,
    node_color=node_colors,
    cmap='viridis',
    with_labels=True,
    font_size=8,
    arrows=True,
    arrowsize=10,
    edge_color='gray',
    alpha=0.7
)
plt.title('Karmacadabra Agent Network (47 Agents, 78 Edges)', fontsize=16)
plt.axis('off')
plt.tight_layout()
plt.savefig('7-network-graph-47-agents.png', dpi=300, bbox_inches='tight')
```

**Shows:**
- 47 agents (nodes), 78 transactions (edges)
- Node size = degree centrality (karma-hello largest = most connections)
- Node color = betweenness centrality (karma-hello darkest = critical bridge)

**Key insight:** karma-hello is hub (23 connections) and bridge (0.42 betweenness). If it goes offline, network fragments.

**Use cases:**
- Network analysis visualization
- Demonstrating scale (47 agents, not just 2-3)
- Identifying critical infrastructure (karma-hello redundancy needed)

---

## Validation Checklist

Before using diagrams in public-facing materials:

### Rendering

- [ ] All Mermaid diagrams render correctly in GitHub Markdown
- [ ] PNG exports are high resolution (300 DPI minimum)
- [ ] SVG exports are vector (scale without pixelation)
- [ ] Network graph PNG is legible at 50% zoom

### Accuracy

- [ ] All contract addresses match deployed contracts (0x63B9..., 0x3D19..., etc.)
- [ ] All metrics match Week 7 Day 1 metrics summary (99 tx, 21,557 gas, etc.)
- [ ] All agent names match actual deployment (karma-hello, abracadabra, etc.)
- [ ] All color coding is consistent (red=error, green=success, blue=blockchain, etc.)

### Accessibility

- [ ] Text is readable at small sizes (minimum 12pt when rendered)
- [ ] Color-blind friendly (avoid red/green as only distinction)
- [ ] Alt text provided for all images (Markdown `![alt text](image.png)`)
- [ ] Diagrams are self-explanatory (don't require external context)

---

## Usage in Documentation

### Blog Post (Week 6)

Embed **Diagram 2** (Transaction Flow) and **Diagram 4** (Symmetric vs Asymmetric) in `contribution/week6/6.3-BLOG-POST.md` for visual storytelling.

### Case Study (Week 6)

Embed **Diagram 1** (Architecture) and **Diagram 7** (Network Graph) in `contribution/week6/6.4-CASE-STUDY.md` for technical depth.

### Formal Extension (Week 6)

Link to **Diagram 3** (Rating Lifecycle) in `contribution/week6/6.2-FORMAL-EXTENSION.md` for state transition specification.

### FAQ (Week 7 Day 4)

Embed **Diagram 5** (Sybil Detection) and **Diagram 6** (Commit-Reveal) for security questions.

---

## Maintenance

**When to update diagrams:**

1. **Contract addresses change:** Update Diagram 1 (Architecture) with new addresses
2. **Gas costs change:** Update Diagram 2 (Transaction Flow) with new measurements
3. **Network grows:** Regenerate Diagram 7 (Network Graph) with new data
4. **V2 launches:** Update Diagram 6 (Commit-Reveal) from "V2 Enhancement" to "Production"

**Versioning:**

- Each diagram has date in commit message
- Breaking changes (e.g., contract address) create new version (e.g., `1-architecture-4-layers-v2.mmd`)
- Old versions retained for historical reference

---

## License

All diagrams released under **CC0 (public domain)** to match EIP-8004 licensing.

**Attribution appreciated but not required:**
```
Source: Karmacadabra Project (github.com/ultravioletadao/karmacadabra)
License: CC0 (public domain)
```

---

## Feedback

Diagram improvements welcome! Open an issue or PR:
- **Repository:** github.com/ultravioletadao/karmacadabra
- **Issues:** github.com/ultravioletadao/karmacadabra/issues
- **Label:** `documentation`, `diagrams`

---

**Status:** ✅ 6 Mermaid diagrams complete, 1 NetworkX graph pending
**Last Updated:** October 30, 2025
**Next:** Day 3 - Evidence Package Compilation
