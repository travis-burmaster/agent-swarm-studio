# Skill: Market Analysis

## Purpose
Size and map the market a company operates in using
public signals and structured search.

## Step-by-Step Process

### 1. Identify the Market Category
From the homepage and About page, extract:
- The 2-3 word market category (e.g., "HR software", "cloud security", "API management")
- The primary problem being solved
- The customer segment (SMB, mid-market, enterprise, consumer)

### 2. Estimate Market Size
Search for TAM/SAM from analyst reports:
```
"{market_category}" TAM OR market size OR billion 2024 OR 2025
"{market_category}" Gartner OR IDC OR Forrester report
"{market_category}" fastest growing OR CAGR
```

Report findings with [CONFIRMED] / [INFERRED] / [UNVERIFIED] tags.

### 3. Identify Top Competitors
```
best {market_category} software OR tools
{company_name} alternatives site:g2.com OR capterra.com
{company_name} competitors {year}
```

Build competitor table with columns:
Company | URL | Stage | Key Differentiator | Est. Market Position

### 4. Market Timing Assessment
- Is the market growing, mature, or declining?
- What macro/regulatory trends are driving demand?
- Any recent category consolidation (M&A)?

## Output Table
```
**Market Intelligence Summary**

Category: [name]
Est. TAM: [range] [confidence tag]
Est. SAM: [range] [confidence tag]
Growth Rate: [estimate] [confidence tag]
Competitive Intensity: Low / Medium / High / Very High
Market Maturity: Emerging / Growth / Mature / Declining
```
