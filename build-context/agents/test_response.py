import json

with open('final_test.json', 'r') as f:
    d = json.load(f)

success = 'detail' not in d

print("=" * 70)
print("SKILL-EXTRACTOR TEST RESULTS")
print("=" * 70)

if not success:
    print("ERROR:", d.get('detail', 'Unknown error'))
else:
    print("STATUS: SUCCESS")
    print("")
    print(f"Total fields: {len(d.keys())}")
    print(f"Agent viability: {d.get('agent_viability', 'N/A')}")
    print(f"Agent name: {d.get('agent_identity', {}).get('agent_name', 'N/A')}")
    print(f"Agent domain: {d.get('agent_identity', {}).get('agent_domain', 'N/A')}")
    print("")
    print("NEW FIELDS:")
    print(f"  - user_needs_analysis: {'YES' if 'user_needs_analysis' in d else 'NO'}")
    print(f"  - market_opportunities: {'YES' if 'market_opportunities' in d else 'NO'}")
    print(f"  - revenue_model: {'YES' if 'revenue_model' in d else 'NO'}")
    print(f"  - implementation_roadmap: {'YES' if 'implementation_roadmap' in d else 'NO'}")
    print("")

    if 'market_opportunities' in d:
        signals = d['market_opportunities'].get('signals_for_other_agents', [])
        print(f"Market opportunities detected: {len(signals)}")

    if 'revenue_model' in d:
        month6 = d['revenue_model'].get('month_6_projection', {})
        print(f"Month 6 projection: {month6.get('usd_equivalent', 'N/A')}")

print("=" * 70)
