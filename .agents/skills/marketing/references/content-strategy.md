# Skill: Content Strategy Analysis

## Purpose
Evaluate a company's content marketing strategy for depth,
consistency, and SEO leverage.

## Assessment Areas

### Blog & Content Audit
```python
blog = reach.fetch(f"{company_url}/blog")
# Count posts visible on index page
# Note categories/tags
# Note most recent post date
# Estimate posting frequency
```

Assess:
- Post count (visible from blog index)
- Publishing frequency (from post dates)
- Average estimated length (short <500w, medium 500-1500w, long 1500w+)
- Content types: how-to, opinion, case study, news, comparison, guide?
- Topic clusters: is there a clear pillar content strategy?
- Author attribution: individual bylines or generic brand?

### Cornerstone Content Check
Search for definitive guides:
```
site:{company_domain} "ultimate guide" OR "complete guide" OR "how to"
site:{company_domain} "vs" OR "comparison" OR "alternatives"
```
Competitor comparison pages are high-converting SEO gold.
Does the company have them?

### Content-ICP Alignment
Does the blog content match the buying journey of their ICP?
- Awareness content: problem-focused ("why X matters")
- Consideration content: solution-focused ("how to solve X")
- Decision content: product-focused ("why [company] for X")

Estimate the % breakdown.

### Guest & Authority Content
```
"{company_name}" site:forbes.com OR techcrunch.com OR medium.com author
```
Are company leaders publishing externally for SEO authority?

## Output
```
**Content Strategy Assessment — [Company Name]**

Blog Volume: ~[N] posts
Posting Cadence: [daily / weekly / monthly / sporadic / none]
Content Quality: [Low / Medium / High]
Pillar Strategy: [Present / Partial / Absent]
ICP Alignment: [Weak / Moderate / Strong]
Competitor Comparison Pages: [Yes / No]
External Authority Content: [Active / Occasional / None]

Top Content Gaps:
1. [gap]
2. [gap]
3. [gap]

Content Opportunities:
1. [opportunity with estimated traffic upside]
```
