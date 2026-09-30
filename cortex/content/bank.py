"""Cortex Bank knowledge base (synthetic).

Single source of truth for the ~70 generated PDFs and for the evaluation's gold answers.
Every cross-reference here (policy -> regulation, SOP -> control, finding -> control ...)
is rendered into the PDFs as plain text, so GraphRAG has to recover it from documents.
"""

BANK = {
    "name": "Cortex Bank",
    "founded": 1926,
    "hq": "Harbour Square, Port Aldridge",
    "tagline": "Trusted since 1926",
}

# code, name, head role, mandate
DEPARTMENTS = [
    ("RET", "Retail Banking", "Head of Retail Banking", "Branch and digital banking for 2.1 million personal customers."),
    ("CCB", "Corporate & Commercial Banking", "Head of Corporate Banking", "Lending, cash management and trade finance for mid-market and large corporates."),
    ("WLT", "Wealth Management", "Head of Wealth", "Advisory and discretionary portfolio services for high-net-worth clients."),
    ("TRM", "Treasury & Markets", "Group Treasurer", "Funding, liquidity management and client trading."),
    ("CRD", "Credit", "Chief Credit Officer", "Credit policy, underwriting and portfolio monitoring."),
    ("RSK", "Risk Management", "Chief Risk Officer", "Second-line oversight of all risk types, capital and model risk."),
    ("CMP", "Compliance (AML/KYC)", "Chief Compliance Officer", "Financial crime prevention, KYC and regulatory compliance."),
    ("OPS", "Operations", "Chief Operating Officer", "Payments, reconciliations, vendor management and finance operations."),
    ("ITC", "IT & Cyber", "Chief Information Officer", "Technology, cyber security, resilience and the Cortex AI Platform."),
    ("HRS", "Human Resources", "Chief People Officer", "Recruitment, conduct, training and employee data."),
    ("LGL", "Legal & Data Protection", "General Counsel", "Legal affairs, data protection (DPO) and contracts."),
    ("IAU", "Internal Audit", "Chief Audit Executive", "Independent third-line assurance reporting to the Board Audit Committee."),
]

# id, short name, full name, summary
REGULATIONS = [
    ("REG-BASEL", "Basel III/IV", "Basel III / IV capital and liquidity framework", "Minimum capital (CET1), leverage and liquidity (LCR, NSFR) requirements."),
    ("REG-AML", "AML/KYC", "Anti-Money Laundering & Counter-Terrorist Financing rules (AMLD / FATF)", "Customer due diligence, transaction monitoring and suspicious activity reporting."),
    ("REG-GDPR", "GDPR", "General Data Protection Regulation", "Lawful processing, data minimisation, retention limits and data subject rights."),
    ("REG-DORA", "DORA", "Digital Operational Resilience Act", "ICT risk management, incident reporting, resilience testing and ICT third-party risk."),
    ("REG-PCI", "PCI-DSS", "Payment Card Industry Data Security Standard v4.0", "Protection of cardholder data, network segmentation and encryption."),
    ("REG-SOX", "SOX", "Sarbanes-Oxley internal control over financial reporting", "Documented and tested controls over financial reporting."),
    ("REG-BCBS239", "BCBS 239", "BCBS 239 Principles for risk data aggregation and reporting", "Accurate, complete and timely risk data with documented lineage."),
    ("REG-EUAI", "EU AI Act", "EU Artificial Intelligence Act", "Obligations for high-risk AI systems: risk management, data governance, human oversight, transparency and logging. Credit scoring and recruitment are high-risk uses."),
    ("REG-MIFID", "MiFID II", "Markets in Financial Instruments Directive II", "Suitability and appropriateness of investment advice and client protection."),
]

# id, name, category
RISKS = [
    ("RSK-CR", "Credit risk", "Financial"),
    ("RSK-MR", "Market risk", "Financial"),
    ("RSK-LQ", "Liquidity risk", "Financial"),
    ("RSK-OP", "Operational risk", "Non-financial"),
    ("RSK-CY", "Cyber risk", "Non-financial"),
    ("RSK-FC", "Financial crime risk", "Non-financial"),
    ("RSK-CD", "Conduct risk", "Non-financial"),
    ("RSK-DP", "Data privacy risk", "Non-financial"),
    ("RSK-MD", "Model and AI risk", "Non-financial"),
    ("RSK-TP", "Third-party risk", "Non-financial"),
]

# id, name, description
SYSTEMS = [
    ("SYS-CORE", "Heritage Core", "Core banking ledger, IBM mainframe (COBOL), in service since 1974 and inherited in part from Harbor Trust."),
    ("SYS-PAY", "PayHub", "Payments gateway for SEPA, SWIFT and card schemes."),
    ("SYS-CRM", "Clientele CRM", "Customer relationship management and onboarding workflows."),
    ("SYS-LOS", "LoanFlow", "Loan origination and credit decisioning platform."),
    ("SYS-TMS", "Sentinel", "Transaction monitoring and sanctions screening system."),
    ("SYS-DWH", "Atlas", "Enterprise data warehouse and risk data mart."),
    ("SYS-TRD", "Meridian", "Trading and treasury platform, inherited from Meridian Securities (2004)."),
    ("SYS-HR", "PeopleCore", "HR information system including the TalentMatch AI screening module."),
    ("SYS-AIP", "Cortex AI Platform", "Internal model registry, feature store and model serving platform."),
]

# id, name, type, frequency, owner dept, mitigates risks, description
CONTROLS = [
    ("CTL-KYC-01", "Identity verification", "Preventive", "Per event", "CMP", ["RSK-FC"], "Verify customer identity with two independent sources before account activation."),
    ("CTL-KYC-02", "Sanctions and PEP screening", "Preventive", "Per event", "CMP", ["RSK-FC"], "Screen customers and counterparties against sanctions and PEP lists at onboarding and daily thereafter."),
    ("CTL-KYC-03", "Enhanced due diligence", "Preventive", "Per event", "CMP", ["RSK-FC"], "Source-of-wealth checks and senior approval for high-risk customers and PEPs."),
    ("CTL-TM-01", "Transaction monitoring alert review", "Detective", "Daily", "CMP", ["RSK-FC"], "Review Sentinel alerts within 5 business days; escalate unexplained activity."),
    ("CTL-TM-02", "Cash threshold reporting", "Detective", "Per event", "RET", ["RSK-FC"], "Report cash transactions of 10,000 or more and structured deposits."),
    ("CTL-SAR-01", "Suspicious activity reporting", "Corrective", "Per event", "CMP", ["RSK-FC"], "File suspicious activity reports with the FIU within 30 days of detection."),
    ("CTL-DP-01", "Data protection impact assessment", "Preventive", "Per change", "LGL", ["RSK-DP"], "DPIA required before any new processing of personal data at high risk, including AI use cases."),
    ("CTL-DP-02", "Data retention enforcement", "Preventive", "Quarterly", "LGL", ["RSK-DP"], "Delete or anonymise personal data after the retention period in the Records Schedule."),
    ("CTL-DP-03", "Data subject request handling", "Corrective", "Per event", "LGL", ["RSK-DP"], "Respond to access and erasure requests within one month."),
    ("CTL-IT-01", "ICT incident classification and reporting", "Detective", "Per event", "ITC", ["RSK-OP", "RSK-CY"], "Classify ICT incidents and send the initial major-incident notification to the regulator within 4 hours."),
    ("CTL-IT-02", "Digital resilience testing", "Detective", "Annual", "ITC", ["RSK-OP", "RSK-CY"], "Annual resilience and scenario testing of all critical systems, including failover of Heritage Core."),
    ("CTL-IT-03", "ICT third-party register", "Preventive", "Quarterly", "OPS", ["RSK-TP"], "Maintain a complete register of ICT third-party arrangements supporting critical functions."),
    ("CTL-IT-04", "Privileged access management", "Preventive", "Continuous", "ITC", ["RSK-CY"], "Just-in-time admin access, no standing privileges, quarterly recertification."),
    ("CTL-IT-05", "Encryption of data at rest and in transit", "Preventive", "Continuous", "ITC", ["RSK-CY", "RSK-DP"], "AES-256 at rest and TLS 1.2+ in transit for all confidential data."),
    ("CTL-PCI-01", "Cardholder data segmentation", "Preventive", "Continuous", "ITC", ["RSK-CY"], "Isolate the cardholder data environment from the corporate network."),
    ("CTL-CR-01", "Four-eyes credit approval", "Preventive", "Per event", "CRD", ["RSK-CR"], "Two independent approvers for every credit decision above the delegated authority limit."),
    ("CTL-CR-02", "Credit limit monitoring", "Detective", "Daily", "CRD", ["RSK-CR"], "Daily monitoring of exposures against approved limits."),
    ("CTL-CR-03", "Collateral valuation", "Detective", "Annual", "CRD", ["RSK-CR"], "Independent revaluation of collateral at least every 12 months."),
    ("CTL-RK-01", "Internal capital adequacy assessment (ICAAP)", "Detective", "Annual", "RSK", ["RSK-CR", "RSK-MR", "RSK-OP"], "Annual assessment of capital needs against the risk profile."),
    ("CTL-RK-02", "Enterprise stress testing", "Detective", "Semi-annual", "RSK", ["RSK-CR", "RSK-LQ", "RSK-MR"], "Group-wide stress scenarios on capital and liquidity."),
    ("CTL-TR-01", "LCR monitoring", "Detective", "Daily", "TRM", ["RSK-LQ"], "Daily liquidity coverage ratio calculation with an internal floor of 110%."),
    ("CTL-TR-02", "Contingency funding plan", "Corrective", "Annual", "TRM", ["RSK-LQ"], "Tested plan to raise liquidity under stress."),
    ("CTL-TR-03", "Trader limit enforcement", "Preventive", "Real-time", "TRM", ["RSK-MR"], "Hard limits on trader positions with escalation of breaches within 1 hour."),
    ("CTL-TR-04", "Independent price verification", "Detective", "Monthly", "RSK", ["RSK-MR"], "Independent verification of trading book valuations."),
    ("CTL-FR-01", "Account reconciliation", "Detective", "Daily", "OPS", ["RSK-OP"], "Daily reconciliation of nostro, suspense and payment accounts."),
    ("CTL-FR-02", "Maker-checker on journals and payments", "Preventive", "Per event", "OPS", ["RSK-OP", "RSK-FC"], "Every manual journal and payment above 50,000 needs a second checker."),
    ("CTL-DA-01", "Risk data lineage", "Preventive", "Per change", "RSK", ["RSK-OP"], "Documented lineage from source system to every regulatory risk report."),
    ("CTL-DA-02", "Risk data quality checks", "Detective", "Daily", "RSK", ["RSK-OP"], "Automated completeness and accuracy checks on the Atlas risk data mart."),
    ("CTL-AI-01", "AI model inventory", "Preventive", "Continuous", "ITC", ["RSK-MD"], "Every AI or statistical model is registered in the Cortex AI Platform with a named owner and risk tier."),
    ("CTL-AI-02", "Human oversight of automated decisions", "Preventive", "Per event", "ITC", ["RSK-MD", "RSK-CD"], "A trained human can review and override any high-risk automated decision."),
    ("CTL-AI-03", "Bias and fairness testing", "Detective", "Annual", "RSK", ["RSK-MD", "RSK-CD"], "Fairness testing across protected characteristics before deployment and every 12 months."),
    ("CTL-AI-04", "Explainability and customer notice", "Preventive", "Per event", "ITC", ["RSK-MD", "RSK-CD"], "Plain-language reasons for automated decisions and notice to customers that AI is used."),
    ("CTL-MR-01", "Independent model validation", "Detective", "Annual", "RSK", ["RSK-MD"], "Second-line validation of high-risk models before use and annually."),
    ("CTL-CD-01", "Suitability assessment", "Preventive", "Per event", "WLT", ["RSK-CD"], "Documented suitability assessment before any investment recommendation."),
    ("CTL-HR-01", "Pre-employment screening", "Preventive", "Per event", "HRS", ["RSK-FC", "RSK-CD"], "Background, reference and conflict-of-interest checks before hire."),
    ("CTL-HR-02", "Segregation of duties matrix", "Preventive", "Semi-annual", "HRS", ["RSK-OP", "RSK-FC"], "Maintain and recertify the matrix of incompatible duties."),
    ("CTL-TP-01", "Vendor due diligence", "Preventive", "Per event", "OPS", ["RSK-TP"], "Financial, security and resilience due diligence before contracting a vendor."),
]

# id, title, dept, regulations, controls, risk appetite statements, version, effective, level
POLICIES = [
    ("POL-AML-001", "Anti-Money Laundering & Counter-Terrorist Financing Policy", "CMP", ["REG-AML"], ["CTL-KYC-01", "CTL-KYC-02", "CTL-TM-01", "CTL-TM-02", "CTL-SAR-01", "CTL-FR-02"],
     ["Cortex Bank has zero tolerance for knowingly facilitating money laundering or terrorist financing.", "All customers are risk-rated at onboarding and re-rated on trigger events.", "Suspicious activity must be reported regardless of amount."], "5.2", "2025-03-01", 1),
    ("POL-KYC-002", "Customer Due Diligence Policy", "CMP", ["REG-AML"], ["CTL-KYC-01", "CTL-KYC-02", "CTL-KYC-03"],
     ["No account may be activated before identity verification is complete.", "Politically exposed persons require enhanced due diligence and approval by the Chief Compliance Officer."], "4.0", "2024-11-15", 1),
    ("POL-PRV-001", "Data Privacy Policy", "LGL", ["REG-GDPR"], ["CTL-DP-01", "CTL-DP-02", "CTL-DP-03", "CTL-IT-05"],
     ["Personal data is processed only for specified, lawful purposes.", "Retention periods in the Records Schedule are mandatory.", "The Data Protection Officer must be consulted on every DPIA."], "3.1", "2025-05-20", 1),
    ("POL-ICT-001", "ICT Risk Management Policy", "ITC", ["REG-DORA"], ["CTL-IT-01", "CTL-IT-02", "CTL-IT-03", "CTL-IT-04"],
     ["Critical functions must be recoverable within their approved recovery time objective.", "Major ICT incidents are notified to the regulator within 4 hours of classification."], "2.0", "2025-01-17", 1),
    ("POL-CYB-002", "Information Security Policy", "ITC", ["REG-DORA", "REG-PCI"], ["CTL-IT-04", "CTL-IT-05", "CTL-PCI-01"],
     ["No standing administrative privileges are permitted.", "Cardholder data is stored only inside the segmented cardholder data environment."], "6.3", "2025-06-30", 1),
    ("POL-CRD-001", "Credit Risk Policy", "CRD", ["REG-BASEL"], ["CTL-CR-01", "CTL-CR-02", "CTL-CR-03"],
     ["Single-name concentration may not exceed 10% of Tier 1 capital.", "The non-performing loan ratio appetite is below 3%."], "7.1", "2025-02-10", 2),
    ("POL-CAP-001", "Capital Adequacy Policy", "RSK", ["REG-BASEL"], ["CTL-RK-01", "CTL-RK-02"],
     ["The bank maintains a CET1 ratio of at least 12.5%, above the regulatory minimum plus buffers."], "3.0", "2025-04-01", 3),
    ("POL-LIQ-001", "Liquidity Risk Policy", "TRM", ["REG-BASEL"], ["CTL-TR-01", "CTL-TR-02", "CTL-RK-02"],
     ["The liquidity coverage ratio must stay at or above an internal floor of 110%."], "4.2", "2025-04-01", 2),
    ("POL-MKT-001", "Market Risk & Trading Policy", "TRM", ["REG-BASEL"], ["CTL-TR-03", "CTL-TR-04"],
     ["Proprietary trading is limited to hedging activity.", "Limit breaches are escalated to the Chief Risk Officer within 1 hour."], "3.4", "2024-09-01", 2),
    ("POL-FIN-001", "Financial Reporting Controls Policy", "OPS", ["REG-SOX"], ["CTL-FR-01", "CTL-FR-02"],
     ["All key financial reporting controls are documented, owned and tested annually."], "2.2", "2025-01-01", 1),
    ("POL-DAT-001", "Risk Data Aggregation Policy", "RSK", ["REG-BCBS239"], ["CTL-DA-01", "CTL-DA-02"],
     ["Every regulatory risk report must have documented, reconciled lineage to source systems."], "1.3", "2024-12-01", 2),
    ("POL-AI-001", "Responsible AI Policy", "ITC", ["REG-EUAI", "REG-GDPR"], ["CTL-AI-01", "CTL-AI-02", "CTL-AI-03", "CTL-AI-04", "CTL-DP-01"],
     ["No AI system may be used in a high-risk decision without human oversight.", "Credit scoring and recruitment screening are classified as high-risk AI uses.", "Every AI model must be registered in the Cortex AI Platform before use."], "1.2", "2026-01-15", 1),
    ("POL-MRM-001", "Model Risk Management Policy", "RSK", ["REG-EUAI", "REG-BASEL"], ["CTL-AI-01", "CTL-MR-01", "CTL-AI-03"],
     ["High-risk models require independent validation before first use and annually thereafter."], "2.1", "2025-09-01", 2),
    ("POL-SUI-001", "Suitability & Client Protection Policy", "WLT", ["REG-MIFID"], ["CTL-CD-01", "CTL-AI-02"],
     ["No investment recommendation may be made without a current suitability assessment.", "Robo-advice outputs are reviewed by a licensed adviser before execution."], "2.0", "2025-07-01", 1),
    ("POL-HR-001", "People & Conduct Policy", "HRS", ["REG-GDPR"], ["CTL-HR-01", "CTL-HR-02", "CTL-AI-02"],
     ["Hiring decisions are made by people; AI tools may only assist.", "Incompatible duties are never assigned to the same person."], "3.0", "2025-10-01", 1),
    ("POL-TPR-001", "Third-Party Risk Policy", "OPS", ["REG-DORA"], ["CTL-TP-01", "CTL-IT-03"],
     ["Critical ICT providers require exit plans and annual resilience evidence."], "1.4", "2025-03-15", 1),
    ("POL-IAU-001", "Internal Audit Charter", "IAU", ["REG-SOX"], [],
     ["Internal Audit has unrestricted access to all records, systems and staff.", "All high-rated findings are reported to the Board Audit Committee."], "4.0", "2024-06-01", 1),
]

# id, title, dept, policies, systems, steps [(text, controls)], version, effective, level
SOPS = [
    ("SOP-RET-001", "Retail Account Opening", "RET", ["POL-KYC-002", "POL-PRV-001"], ["SYS-CRM", "SYS-CORE"], [
        ("Capture customer details in Clientele CRM and obtain privacy notice acknowledgement.", ["CTL-DP-02"]),
        ("Verify identity using two independent sources (document scan and electronic check).", ["CTL-KYC-01"]),
        ("Run sanctions and PEP screening; stop and refer any match to Compliance.", ["CTL-KYC-02"]),
        ("Assign customer risk rating; high-risk customers follow SOP-CMP-003.", ["CTL-KYC-03"]),
        ("Activate the account in Heritage Core only after all checks show 'Passed'.", []),
    ], "3.0", "2021-04-12", 1),
    ("SOP-RET-002", "Cash Handling & Teller Operations", "RET", ["POL-AML-001", "POL-FIN-001"], ["SYS-CORE"], [
        ("Count cash in view of the customer and record in Heritage Core.", []),
        ("For cash transactions of 10,000 or more, complete a cash threshold report.", ["CTL-TM-02"]),
        ("Refer suspected structuring (repeated deposits just below 10,000) to the branch AML champion.", ["CTL-TM-02"]),
        ("End-of-day teller balancing is checked by a second staff member.", ["CTL-FR-02"]),
    ], "2.4", "2023-02-01", 1),
    ("SOP-CMP-001", "Transaction Monitoring Alert Handling", "CMP", ["POL-AML-001"], ["SYS-TMS"], [
        ("Triage Sentinel alerts daily by risk score.", ["CTL-TM-01"]),
        ("Investigate alerts within 5 business days using customer profile and transaction history.", ["CTL-TM-01"]),
        ("Close with rationale or escalate to Level 2 investigator.", ["CTL-TM-01"]),
        ("Escalated cases with unexplained activity proceed to SOP-CMP-002.", ["CTL-SAR-01"]),
        ("Alerts linked to shared devices or addresses across customers are flagged as potential fraud rings.", ["CTL-TM-01"]),
    ], "3.0", "2024-05-01", 3),
    ("SOP-CMP-002", "Suspicious Activity Reporting", "CMP", ["POL-AML-001"], ["SYS-TMS"], [
        ("MLRO reviews the escalated case file.", ["CTL-SAR-01"]),
        ("File the SAR with the FIU within 30 days of detection.", ["CTL-SAR-01"]),
        ("Do not tip off the customer; restrict case access to Compliance.", []),
    ], "2.1", "2024-05-01", 3),
    ("SOP-CMP-003", "Enhanced Due Diligence for High-Risk Customers and PEPs", "CMP", ["POL-KYC-002"], ["SYS-CRM"], [
        ("Collect source-of-wealth and source-of-funds evidence.", ["CTL-KYC-03"]),
        ("Obtain approval from the Chief Compliance Officer for PEP relationships.", ["CTL-KYC-03"]),
        ("Re-review high-risk relationships every 12 months.", ["CTL-KYC-03"]),
    ], "2.0", "2024-11-15", 3),
    ("SOP-CRD-001", "Commercial Credit Approval", "CRD", ["POL-CRD-001"], ["SYS-LOS"], [
        ("Relationship manager submits the credit application in LoanFlow.", []),
        ("Credit analyst prepares the risk rating and collateral assessment.", ["CTL-CR-03"]),
        ("Two independent approvers sign off above delegated authority.", ["CTL-CR-01"]),
        ("Approved limits are loaded and monitored daily.", ["CTL-CR-02"]),
    ], "4.0", "2022-03-01", 2),
    ("SOP-CRD-002", "Retail Credit Scoring & Automated Decisioning", "CRD", ["POL-CRD-001", "POL-AI-001", "POL-MRM-001"], ["SYS-LOS", "SYS-AIP"], [
        ("Applications are scored by credit scoring model CS-v4 served from the Cortex AI Platform.", ["CTL-AI-01"]),
        ("Declines and borderline scores are routed to a credit officer for human review.", ["CTL-AI-02"]),
        ("Customers receive plain-language reasons for the decision and notice that AI was used.", ["CTL-AI-04"]),
        ("CS-v4 is fairness-tested annually and validated by Model Risk.", ["CTL-AI-03", "CTL-MR-01"]),
    ], "2.0", "2025-08-01", 2),
    ("SOP-WLT-001", "Client Suitability Assessment", "WLT", ["POL-SUI-001"], ["SYS-CRM", "SYS-AIP"], [
        ("Complete the client risk profile questionnaire.", ["CTL-CD-01"]),
        ("Generate the model portfolio proposal using the robo-advice engine.", []),
        ("A licensed adviser reviews and approves the proposal before execution.", ["CTL-AI-02"]),
    ], "1.5", "2025-07-01", 2),
    ("SOP-TRM-001", "Daily Liquidity Monitoring", "TRM", ["POL-LIQ-001"], ["SYS-TRD", "SYS-DWH"], [
        ("Calculate the LCR by 09:00 from Atlas and Meridian positions.", ["CTL-TR-01"]),
        ("If the LCR falls below 115%, alert the Group Treasurer; below 110%, invoke the contingency funding plan.", ["CTL-TR-01", "CTL-TR-02"]),
    ], "3.1", "2024-04-01", 2),
    ("SOP-TRM-002", "Trader Limit Breach Escalation", "TRM", ["POL-MKT-001"], ["SYS-TRD"], [
        ("Meridian blocks orders that breach hard limits.", ["CTL-TR-03"]),
        ("Soft-limit breaches are escalated to the desk head and the Chief Risk Officer within 1 hour.", ["CTL-TR-03"]),
    ], "2.0", "2024-09-01", 2),
    ("SOP-RSK-001", "Enterprise Stress Testing", "RSK", ["POL-CAP-001", "POL-LIQ-001"], ["SYS-DWH"], [
        ("Define baseline, adverse and severely adverse scenarios.", ["CTL-RK-02"]),
        ("Project capital and liquidity over three years.", ["CTL-RK-02", "CTL-RK-01"]),
        ("Present results to the Board Risk Committee.", []),
    ], "2.0", "2025-04-01", 3),
    ("SOP-RSK-002", "Risk Data Lineage & Quality Checks", "RSK", ["POL-DAT-001"], ["SYS-DWH", "SYS-CORE"], [
        ("Document lineage from Heritage Core and source systems to Atlas reports.", ["CTL-DA-01"]),
        ("Run daily data quality rules; breaches above tolerance are logged as data incidents.", ["CTL-DA-02"]),
    ], "1.2", "2024-12-01", 2),
    ("SOP-RSK-003", "Model Validation", "RSK", ["POL-MRM-001", "POL-AI-001"], ["SYS-AIP"], [
        ("Confirm the model is registered with an owner and risk tier.", ["CTL-AI-01"]),
        ("Perform independent validation of data, methodology and performance.", ["CTL-MR-01"]),
        ("Run bias and fairness tests across protected characteristics.", ["CTL-AI-03"]),
    ], "2.0", "2025-09-01", 2),
    ("SOP-ITC-001", "ICT Incident Management & Regulatory Reporting", "ITC", ["POL-ICT-001"], ["SYS-CORE", "SYS-PAY"], [
        ("Log the incident and assign severity within 30 minutes.", ["CTL-IT-01"]),
        ("If classified as major, send the initial notification to the regulator within 4 hours.", ["CTL-IT-01"]),
        ("Submit the intermediate report within 72 hours and the final report within one month.", ["CTL-IT-01"]),
    ], "2.0", "2025-01-17", 0),
    ("SOP-ITC-002", "Privileged Access Management", "ITC", ["POL-CYB-002", "POL-ICT-001"], ["SYS-CORE", "SYS-PAY", "SYS-AIP"], [
        ("Request admin access just-in-time through the PAM vault with a ticket reference.", ["CTL-IT-04"]),
        ("Access expires automatically after 8 hours.", ["CTL-IT-04"]),
        ("Quarterly recertification of all privileged accounts, including contractors.", ["CTL-IT-04"]),
    ], "3.0", "2023-10-01", 0),
    ("SOP-ITC-003", "AI Model Deployment & Monitoring", "ITC", ["POL-AI-001", "POL-MRM-001"], ["SYS-AIP"], [
        ("Register the model in the Cortex AI Platform with owner and risk tier.", ["CTL-AI-01"]),
        ("High-risk models require validation evidence (SOP-RSK-003) and a DPIA before deployment.", ["CTL-MR-01", "CTL-DP-01"]),
        ("Configure human override and decision logging.", ["CTL-AI-02"]),
        ("Publish the customer-facing explanation template.", ["CTL-AI-04"]),
        ("Monitor drift monthly and retire unused models.", ["CTL-AI-01"]),
    ], "1.1", "2026-01-15", 1),
    ("SOP-OPS-001", "Payment Processing & Reconciliation", "OPS", ["POL-FIN-001", "POL-CYB-002"], ["SYS-PAY", "SYS-CORE"], [
        ("Payments above 50,000 require maker-checker approval in PayHub.", ["CTL-FR-02"]),
        ("Card payments are processed only within the cardholder data environment.", ["CTL-PCI-01"]),
        ("Reconcile nostro and suspense accounts daily.", ["CTL-FR-01"]),
    ], "4.2", "2024-02-01", 1),
    ("SOP-OPS-002", "Vendor Onboarding", "OPS", ["POL-TPR-001"], [], [
        ("Complete vendor due diligence including security and resilience questionnaires.", ["CTL-TP-01"]),
        ("Record ICT arrangements in the third-party register.", ["CTL-IT-03"]),
        ("Critical vendors require an exit plan before contract signature.", ["CTL-TP-01"]),
    ], "1.3", "2025-03-15", 1),
    ("SOP-HRS-001", "Recruitment & AI-Assisted Screening", "HRS", ["POL-HR-001", "POL-AI-001", "POL-PRV-001"], ["SYS-HR"], [
        ("TalentMatch ranks applications; it may not reject candidates automatically.", ["CTL-AI-02"]),
        ("A recruiter reviews every shortlist and every rejection.", ["CTL-AI-02"]),
        ("TalentMatch is fairness-tested annually.", ["CTL-AI-03"]),
        ("Complete pre-employment screening before an offer is confirmed.", ["CTL-HR-01"]),
    ], "2.0", "2025-10-01", 1),
    ("SOP-LGL-001", "Data Subject Access Requests", "LGL", ["POL-PRV-001"], ["SYS-CRM", "SYS-CORE"], [
        ("Log the request and verify the requester's identity.", ["CTL-DP-03"]),
        ("Collect data from Clientele CRM, Heritage Core and archives.", ["CTL-DP-03"]),
        ("Respond within one month.", ["CTL-DP-03"]),
    ], "2.0", "2024-07-01", 1),
    ("SOP-IAU-001", "Annual Control Testing", "IAU", ["POL-IAU-001", "POL-FIN-001"], [], [
        ("Build the annual audit plan from the risk and control inventory.", []),
        ("Test design and operating effectiveness of key controls.", []),
        ("Rate findings High, Medium or Low and agree remediation dates with owners.", []),
    ], "3.0", "2024-06-01", 4),
]

# Legacy versions: id, title, dept, version, effective, retired, superseded by (current SOP), summary, level
LEGACY_SOPS = [
    ("SOP-RET-001-V1", "Branch Account Opening (Paper Process)", "RET", "1.0", "1998-06-01", "2012-03-01", "SOP-RET-001",
     "Paper application forms, identity checked visually by the teller, ledger cards posted to Heritage Core overnight.", 1),
    ("SOP-CRD-001-V1", "Branch Credit Committee Procedure", "CRD", "1.0", "1987-01-15", "2022-03-01", "SOP-CRD-001",
     "Credit decisions taken by a monthly branch credit committee, inherited from Northgate Commercial Bank.", 2),
    ("SOP-CMP-001-V2", "Manual AML Review of Large Transactions", "CMP", "2.0", "2012-09-01", "2024-05-01", "SOP-CMP-001",
     "Monthly manual review of transactions above 15,000 using spreadsheet extracts.", 3),
    ("SOP-ITC-002-V1", "Administrator Account Procedure", "ITC", "1.0", "2009-02-01", "2023-10-01", "SOP-ITC-002",
     "Named administrator accounts with standing privileges, reviewed annually.", 0),
    ("SOP-OPS-001-V1", "Payment Release Procedure", "OPS", "1.0", "2004-05-01", "2024-02-01", "SOP-OPS-001",
     "Payments released by a single operator; dual control only above 250,000.", 1),
    ("SOP-HRS-001-V1", "Recruitment Procedure", "HRS", "1.0", "2016-01-01", "2025-10-01", "SOP-HRS-001",
     "Manual CV review by recruiters; no AI tools in use.", 1),
]

# id, title, owner dept, applies to (roles/systems/SOPs), rules, level
GUARDRAILS = [
    ("GRD-001", "Segregation of Duties Standard", "RSK", ["SOP-CRD-001", "SOP-OPS-001", "SOP-IAU-001"],
     ["The person who originates a credit or payment may not approve it.", "Internal Audit staff may not audit processes they operated in the previous 12 months."], 1),
    ("GRD-002", "Maker-Checker Standard", "OPS", ["SOP-OPS-001", "SOP-RET-002", "POL-FIN-001"],
     ["Manual journals and payments above 50,000 require an independent checker.", "Checkers must hold a role at least equal in grade to the maker."], 1),
    ("GRD-003", "Generative AI Acceptable Use Standard", "ITC", ["SYS-AIP", "ALL-STAFF"],
     ["Customer personal data must never be entered into public generative AI tools.", "Only tools approved in the Cortex AI Platform may be used for bank work.", "AI-generated content sent to customers must be reviewed by a person."], 0),
    ("GRD-004", "Data Access & Classification Standard", "ITC", ["ALL-STAFF"],
     ["L0 Public/Contractor: runbooks for assigned systems only.", "L1 Internal: bank-wide policies and general procedures.", "L2 Confidential: department procedures and credit data, need-to-know.", "L3 Restricted: financial crime cases, risk appetite and KRIs.", "L4 Highly Restricted: board risk reports and audit findings."], 1),
    ("GRD-005", "Human-in-the-Loop Standard for Automated Decisions", "RSK", ["SOP-CRD-002", "SOP-HRS-001", "SOP-WLT-001"],
     ["High-risk automated decisions must be reviewable and overridable by a trained person.", "Override rates are reported monthly to the Model Risk Committee."], 1),
    ("GRD-006", "Contractor Privileged Access Guardrail", "ITC", ["SOP-ITC-002", "ROLE-CONTRACTOR"],
     ["Contractors never hold standing administrative access.", "Contractor access is limited to systems named in their statement of work."], 0),
]

# KRI/KPI frameworks: id, title, dept, level, indicators [(id, name, measures controls, target, current, status)]
KRI_FRAMEWORKS = [
    ("KRI-FC", "Financial Crime KRI Framework", "CMP", 3, [
        ("KRI-FC-01", "Transaction monitoring alerts older than 5 days", ["CTL-TM-01"], "< 200", "340", "Breach"),
        ("KRI-FC-02", "SARs filed within 30 days", ["CTL-SAR-01"], "100%", "94%", "Amber"),
        ("KRI-FC-03", "Customers with overdue KYC refresh", ["CTL-KYC-03"], "< 1%", "0.7%", "Green"),
    ]),
    ("KRI-IT", "Operational Resilience KPI Framework", "ITC", 3, [
        ("KRI-IT-01", "Major incidents notified within 4 hours", ["CTL-IT-01"], "100%", "92%", "Amber"),
        ("KRI-IT-02", "Critical systems resilience-tested in last 12 months", ["CTL-IT-02"], "100%", "78%", "Breach"),
        ("KRI-IT-03", "Accounts with standing admin privileges", ["CTL-IT-04"], "0", "14", "Breach"),
    ]),
    ("KRI-AI", "AI & Model Risk KRI Framework", "RSK", 3, [
        ("KRI-AI-01", "High-risk models fairness-tested in last 12 months", ["CTL-AI-03"], "100%", "71%", "Breach"),
        ("KRI-AI-02", "Models in production without a registered owner", ["CTL-AI-01"], "0", "3", "Breach"),
        ("KRI-AI-03", "Automated decisions overridden by humans", ["CTL-AI-02"], "2-10%", "6%", "Green"),
    ]),
    ("KRI-CAP", "Capital, Liquidity & Credit KPI Framework", "RSK", 4, [
        ("KRI-CAP-01", "CET1 ratio", ["CTL-RK-01"], ">= 12.5%", "13.8%", "Green"),
        ("KRI-CAP-02", "Liquidity coverage ratio", ["CTL-TR-01"], ">= 110%", "134%", "Green"),
        ("KRI-CAP-03", "Non-performing loan ratio", ["CTL-CR-02"], "< 3%", "2.6%", "Green"),
        ("KRI-CAP-04", "Collateral revaluations overdue", ["CTL-CR-03"], "0", "57", "Amber"),
    ]),
]

# Audit reports: id, title, date, level, scope depts, findings [(id, title, severity, control, owner dept, due, status)]
AUDIT_REPORTS = [
    ("AR-2025-03", "Audit of AML Transaction Monitoring", "2025-04-28", 3, ["CMP"], [
        ("AF-2025-011", "Alert backlog: 340 alerts older than 5 days", "High", "CTL-TM-01", "CMP", "2025-12-31", "Overdue"),
        ("AF-2025-012", "6% of SARs filed after the 30-day deadline", "Medium", "CTL-SAR-01", "CMP", "2025-09-30", "Closed"),
    ]),
    ("AR-2025-07", "Audit of AI Governance", "2025-08-19", 4, ["ITC", "RSK", "CRD", "HRS"], [
        ("AF-2025-031", "Credit scoring model CS-v4 not fairness-tested for 18 months", "High", "CTL-AI-03", "RSK", "2026-03-31", "Open"),
        ("AF-2025-032", "Three shadow AI models in HR not registered in the Cortex AI Platform", "Medium", "CTL-AI-01", "HRS", "2026-01-31", "Open"),
    ]),
    ("AR-2025-09", "Audit of ICT Resilience (DORA Readiness)", "2025-10-06", 4, ["ITC", "OPS"], [
        ("AF-2025-041", "Heritage Core failover not included in resilience testing", "High", "CTL-IT-02", "ITC", "2026-06-30", "Open"),
        ("AF-2025-042", "Four ICT vendors missing from the third-party register", "Low", "CTL-IT-03", "OPS", "2026-02-28", "Closed"),
    ]),
    ("AR-2026-02", "Audit of Privileged Access", "2026-03-12", 4, ["ITC"], [
        ("AF-2026-005", "14 contractor accounts with standing administrative access", "High", "CTL-IT-04", "ITC", "2026-07-31", "Open"),
    ]),
    ("AR-2026-04", "Audit of Commercial Credit Process", "2026-05-05", 4, ["CRD"], [
        ("AF-2026-011", "57 collateral revaluations overdue beyond 12 months", "Medium", "CTL-CR-03", "CRD", "2026-11-30", "Open"),
    ]),
    ("AR-2026-06", "Audit of Data Privacy Controls", "2026-07-14", 4, ["LGL", "RET"], [
        ("AF-2026-017", "Retention exceptions: closed-account data kept beyond 10 years in Clientele CRM", "Medium", "CTL-DP-02", "LGL", "2026-12-31", "Open"),
    ]),
]

# Regulatory change notices: id, title, date, regulation, summary, impacted policies, actions
CHANGE_NOTICES = [
    ("RCN-2026-01", "EU AI Act: High-Risk AI Obligations", "2026-02-02", "REG-EUAI",
     "Per the bank's regulatory calendar, obligations for high-risk AI systems (including creditworthiness assessment and recruitment) apply to Cortex Bank from August 2026.",
     ["POL-AI-001", "POL-MRM-001", "POL-HR-001"],
     ["Complete fairness testing for CS-v4 and TalentMatch.", "Register all shadow models.", "Update customer notices for automated decisions."]),
    ("RCN-2026-02", "DORA: Threat-Led Penetration Testing", "2026-04-20", "REG-DORA",
     "The bank has been designated for threat-led penetration testing of critical functions within the next testing cycle.",
     ["POL-ICT-001", "POL-TPR-001"],
     ["Include Heritage Core and PayHub in scope.", "Confirm critical ICT vendors' participation."]),
]

# Mergers & history: year, event
HISTORY = [
    (1926, "Founded as Cortex Savings & Loan in Port Aldridge."),
    (1958, "Merged with Harbor Trust, gaining 40 branches and the ledger that became Heritage Core."),
    (1974, "Heritage Core mainframe goes live."),
    (1987, "Acquired Northgate Commercial Bank; commercial lending and the branch credit committee model inherited."),
    (2004, "Acquired Meridian Securities; Meridian trading platform and Treasury & Markets division established."),
    (2019, "Acquired FinEdge, a digital lender; automated credit decisioning introduced."),
    (2023, "Launched the Cortex AI Platform."),
]

# Impersonation roles: id, name, clearance, dept scope ("ALL" = every department)
ROLES = [
    ("ROLE-TELLER", "Branch Teller", 1, ["RET"]),
    ("ROLE-RM", "Relationship Manager (Wealth)", 2, ["WLT", "RET"]),
    ("ROLE-CREDIT", "Credit Analyst", 2, ["CRD", "RSK"]),
    ("ROLE-COMPLIANCE", "Compliance Officer (AML/KYC)", 3, ["CMP", "RET", "OPS"]),
    ("ROLE-CRO", "Chief Risk Officer", 4, ["ALL"]),
    ("ROLE-AUDITOR", "Internal Auditor", 4, ["ALL"]),
    ("ROLE-CONTRACTOR", "External Contractor (IT)", 0, ["ITC"]),
]


def can_access(role_id: str, doc_level: int, doc_dept: str) -> bool:
    """Access rule shared by the generator (metadata) and the app (retrieval filter)."""
    _, _, clearance, scope = next(r for r in ROLES if r[0] == role_id)
    if doc_level > clearance:
        return False
    if doc_level <= 1 and clearance >= 1:
        return True
    if doc_level == 0:
        return doc_dept in scope or "ALL" in scope
    return "ALL" in scope or doc_dept in scope
