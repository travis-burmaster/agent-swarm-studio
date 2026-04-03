# Skill: Contract & Legal Document Review

## Purpose
Systematically review ToS, Privacy Policies, and other legal documents
found at a company URL.

## Execution Steps

1. Fetch the document URL using agent-search-tool
2. Extract all numbered sections and headings
3. Scan for HIGH-RISK clauses (see checklist below)
4. Classify each finding by severity and type
5. Add to the main legal analysis output

## High-Risk Clause Checklist

### Arbitration & Dispute Resolution
- [ ] Mandatory arbitration clause present?
- [ ] Class-action waiver present?
- [ ] Governing law favorable to company (not user)?
- [ ] Venue limited to company HQ jurisdiction?

### Data Rights & Privacy
- [ ] Company claims broad license to user data?
- [ ] Data sold or shared with "third parties"?
- [ ] No deletion right (GDPR Article 17)?
- [ ] Retention period absent or "indefinite"?
- [ ] Children's data (COPPA) — age gate present?

### Liability & Warranty
- [ ] "AS-IS" warranty disclaimer?
- [ ] Liability cap = subscription fee paid?
- [ ] Exclusion of consequential damages?
- [ ] Indemnification clause (who indemnifies whom)?

### Modification Rights
- [ ] "We may change these terms at any time" without notice?
- [ ] Continued use = acceptance of new terms?

### IP Ownership
- [ ] User-generated content license — scope?
- [ ] Work-for-hire language for submissions?
- [ ] Reverse engineering prohibition?

## Output Format

For each document reviewed:
```
**Document:** [name] — [URL]
**Last Updated:** [date if visible]
**Word Count Estimate:** [rough count]
**High-Risk Clauses Found:** [count]

[List findings per RULES.md Rule 2 confidence tags]
```
