from tools.market_research import get_comparables

# Default call — same as freelancer_agent.py uses
default = get_comparables()
print(f'Default (no skill): {len(default)} results')
for c in default:
    print(' -', c['text'])

# Skill filter
ml = get_comparables(skill='machine learning')
print(f'\nFiltered (machine learning): {len(ml)} results')
for c in ml:
    print(' -', c['text'])

# Nonsense filter — should fall back to full set, not empty
none_match = get_comparables(skill='underwater basket weaving')
print(f'\nFiltered (no match): {len(none_match)} results (should be 4, fallback)')
