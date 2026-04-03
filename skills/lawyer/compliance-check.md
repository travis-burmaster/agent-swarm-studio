# Skill: Regulatory Compliance Check

## Purpose
Identify regulatory compliance signals and gaps for a company
based on their public digital footprint.

## Compliance Frameworks to Check

### GDPR (EU)
- Privacy Policy mentions "GDPR" or "EU residents"?
- Data Subject Rights section (access, deletion, portability)?
- Cookie consent banner indicators?
- DPO (Data Protection Officer) contact listed?
- Legal basis for processing stated?
- Cross-border transfer mechanisms (SCCs, adequacy)?

### CCPA / CPRA (California)
- "Do Not Sell My Personal Information" link?
- California residents section in Privacy Policy?
- Opt-out mechanism?

### HIPAA (Healthcare)
- BAA (Business Associate Agreement) offering?
- PHI handling language?
- HIPAA compliance certification claims?

### PCI-DSS (Payments)
- Payment processing (in-house vs. Stripe/Braintree)?
- PCI compliance badge/certification?
- Card data storage statements?

### SOC 2
- SOC 2 Type II certification mentioned?
- Security page exists?
- Penetration testing claims?
- Audit report available?

### Industry-Specific
- FinTech: FinCEN/FBAR, state money transmitter licenses
- Healthcare: FDA, HL7/FHIR compliance
- EdTech: FERPA, COPPA
- Government: FedRAMP, FISMA

## Search Queries to Run
```
"{company_name}" GDPR compliance OR GDPR certified
"{company_name}" HIPAA compliant OR HIPAA certified
"{company_name}" SOC 2 Type II
"{company_name}" PCI DSS compliant
"{company_name}" regulatory action OR enforcement OR fine
```

## Output Format
```
**Compliance Assessment — [Company Name]**

| Framework | Evidence | Status | Risk Level |
|-----------|---------|--------|-----------|
| GDPR | Privacy Policy mentions GDPR | ✅ Addressed | Low |
| CCPA | No opt-out link found | ❌ Missing | High |
| SOC 2 | Security page mentions SOC 2 Type II | ✅ Addressed | Low |
| HIPAA | N/A — not healthcare | — | N/A |
```
