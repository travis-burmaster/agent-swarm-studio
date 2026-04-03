# Skill: Competitive Intelligence

## Purpose
Build a detailed competitive profile comparing the target company
against its top 3-5 competitors.

## Research Process

### Step 1: Find Competitors
Sources (in order of reliability):
1. G2 / Capterra "Compare" pages
2. The company's own "vs [competitor]" landing pages
3. "Alternatives to [company]" search results
4. Reddit discussions: "[company] vs [competitor]"
5. Job postings referencing competitors by name

### Step 2: Profile Each Competitor
For each competitor, fetch their homepage and pricing page:

```python
for competitor_url in competitor_urls:
    homepage = reach.fetch(competitor_url)
    pricing = reach.fetch(f"{competitor_url}/pricing")
    github = reach.search(f"org:{competitor_github} site:github.com")
    funding = reach.search(f'"{competitor_name}" raised OR Series OR ARR')
```

### Step 3: Build the Comparison Matrix

| Dimension | Target Co. | Comp. A | Comp. B | Comp. C |
|-----------|-----------|---------|---------|---------|
| Founded | | | | |
| HQ | | | | |
| Est. Stage | | | | |
| Pricing (entry) | | | | |
| Pricing (mid) | | | | |
| Primary ICP | | | | |
| GTM Motion | | | | |
| GitHub Stars | | | | |
| G2 Rating | | | | |
| Key Feature Diff | | | | |

### Step 4: SWOT vs. Each Competitor
For each main competitor, identify:
- **Target Company Strength** vs. this competitor
- **Target Company Weakness** vs. this competitor
- **Market Opportunity** the target company has that competitor doesn't address
- **Threat** this competitor poses

## Output
Return the full comparison matrix and SWOT notes.
Confidence-tag all data per RULES.md.
