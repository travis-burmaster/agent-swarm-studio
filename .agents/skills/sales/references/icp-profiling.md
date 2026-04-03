# Skill: ICP (Ideal Customer Profile) Profiling

## Purpose
Reconstruct the company's Ideal Customer Profile from
their case studies, testimonials, integrations, and positioning.

## Data Collection

### From Case Studies & Testimonials
Fetch: /customers, /case-studies, /testimonials, /success-stories

For each example found, extract:
- Company name (or type if anonymized)
- Industry
- Company size (employee count / revenue if mentioned)
- Job title of the person quoted
- Problem they solved
- Outcome metric (if mentioned)

### From Pricing Page
Pricing tiers reveal ICP segmentation:
- Tier names (Starter / Pro / Enterprise = SMB / Mid / Enterprise split)
- Feature gating (what's removed from lower tiers tells you what enterprise cares about)
- Seat limits or usage caps (reveal team size targeting)
- Price points (budget range of target customer)

### From Integration List
Integrations reveal the customer's existing tech stack:
- Salesforce/HubSpot = B2B sales customers
- Shopify/WooCommerce = ecommerce customers
- Slack/Teams = mid-size to enterprise
- QuickBooks/Xero = SMB
- Workday/BambooHR = HR teams
- Snowflake/dbt = data teams

### From Blog Content
Blog topics reveal who they're speaking to:
- Technical posts → developer buyer
- ROI/cost posts → finance/ops buyer
- Compliance posts → legal/security buyer
- Leadership posts → executive buyer

## ICP Output Template
```
**Reconstructed ICP — [Company Name]**

Firmographics:
- Company Size: [range]
- Industry: [top 2-3]
- Geography: [primary markets]
- Revenue/Funding: [estimate]

Buyer Persona:
- Primary Buyer: [job title]
- Economic Buyer: [job title if different]
- Champion: [job title]
- Blocker/Skeptic: [job title]

Trigger Events (what causes them to buy):
1. [trigger]
2. [trigger]

Pain Points Addressed:
1. [pain]
2. [pain]

Success Metrics (what they measure ROI on):
1. [metric]

Confidence in ICP reconstruction: [Low / Medium / High]
Basis: [case studies / pricing / integration signals / blog content]
```
