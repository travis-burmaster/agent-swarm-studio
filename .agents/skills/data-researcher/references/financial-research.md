# Skill: Financial Signal Research

## Purpose
Estimate a company's financial position using public signals
when actual financials are unavailable.

## Signal Sources

### Funding Signals
```
"{company_name}" funding OR raised OR Series A OR Series B OR seed
"{company_name}" site:crunchbase.com OR site:pitchbook.com
"{company_name}" investor OR backed by OR portfolio
"{company_name}" IPO OR SPAC OR acquisition OR acqui-hire
```

### Revenue Signals
```
"{company_name}" ARR OR annual recurring revenue OR revenue milestone
"{company_name}" "$" million OR billion revenue
"{company_name}" customers OR users OR subscribers milestone
```

### Employee Count → Revenue Estimation
Rule of thumb for SaaS companies:
- Early (1-10 employees): Pre-revenue to $500K ARR
- Seed (10-50): $500K - $5M ARR
- Series A (50-150): $5M - $15M ARR
- Series B (150-400): $15M - $50M ARR
- Series C+ (400+): $50M+ ARR

Cross-reference with pricing and customer count if available.

### Burn Rate Signals
- Recent mass layoffs → possible runway constraints
- Hiring freeze → cost reduction mode
- Very rapid hiring → flush with cash, growth mode
- Product pricing increases → margin improvement push

## Output Table
```
**Financial Signal Summary — [Company Name]**

Last Known Funding: [amount] [round] [date] [source]
Lead Investors: [names] [confidence tag]
Est. Employee Count: [range] [source]
ARR Estimate: [range] [confidence tag] [basis]
Revenue Stage: Pre-revenue | Early | Growth | Scale
Burn Rate Signal: Conservative | Normal | Aggressive
Exit Signals: None detected | M&A rumors | IPO prep
```

Always note: *ARR estimates are inference from public signals, not reported figures.*
