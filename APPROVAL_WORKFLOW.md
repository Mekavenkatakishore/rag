# Human-in-the-Loop Shortlist Approval Workflow (Phase 1 & Phase 2 Setup)

This document provides setup, testing, and operational guidance for the **Human-in-the-Loop Shortlist Approval Workflow**.

---

## 1. Overview & Status Flow

After AI resume screening, candidates who meet qualification criteria automatically transition into:
```
[Screened] ──► [Shortlisted (Pending Approval)] ──► [Approved] (Phase 1)
                                                 │   └──► [Approved & Email Sent] (Phase 2 SMTP)
                                                 ├──► [On Hold]
                                                 └──► [Rejected]
```

### Critical Constraint
> **No automated email sending**: The system **never** sends emails automatically upon screening. An authorized HR user must inspect the explainable match details, review the side-by-side JD requirements against resume quotes, and explicitly click **"Approve & Send Shortlist Mail"**.

---

## 2. Phase 1 Features Implemented

1. **Shortlisted List Page (`/shortlisted`)**:
   - Table of candidates with status `Pending Approval` (default).
   - Columns: Rank, Candidate Name, Applied Role, Match Score %, Status Badge, Top Matched Skills, Date, Action.
   - Live filters: Status (`Pending Approval`, `Approved`, `On Hold`, `Rejected`, `All`), Minimum Score (`≥80%`, `≥60%`, `≥50%`), and Search by candidate name or position.
   - Sorting by: Match Score (High $\rightarrow$ Low, Low $\rightarrow$ High), Screening Date, Candidate Name.

2. **Candidate Review Screen (`/candidates/{id}/match-details`)**:
   - **Score Breakdown**: Deterministic scores for Required Skills (35%), Experience (20%), Semantic JD Relevance (15%), Projects (10%), Preferred Skills (10%), Education (5%), and Domain Fit (5%).
   - **Shortlisting Criteria Matrix**: Pass/Fail evaluation per rule (Required Skills $\ge 50\%$, Experience Years, Overall Score $\ge 60\%$, Education, Domain Relevance).
   - **AI Executive Summary & Red Flags**: 3-5 line explanation of why the candidate was shortlisted + flagged risks or deficits.
   - **Side-by-Side Comparison**: Target JD requirements alongside candidate resume evidence snippets with page numbers and document names.
   - **Skills Categorization**: Matched Skills (with citation quotes), Missing Skills, and Bonus/Additional Skills.
   - **Experience Match**: Required vs actual years gauge.
   - **Resume Document Preview**: Formatted text viewer of the candidate's original resume.

3. **Action Buttons & Modals**:
   - **Approve & Send Shortlist Mail** (Primary): Opens confirmation modal. In Phase 1, updates status to `Approved`, records audit logs, and stubs email delivery.
   - **Hold**: Sets status to `On Hold` with internal notes.
   - **Reject**: Opens rejection modal with standard reason selector and notes.
   - **Preview Email**: Opens email preview modal displaying rendered HTML and plain-text invitation templates.
   - **HR Notes**: Recruiter notes input persisted to the database.

4. **Security & RBAC**:
   - Protected by JWT Authentication and role check (`require_hr_or_admin`).
   - Immutable audit logging in `hr_audit_logs` tracking every approve, reject, and hold action.

---

## 3. Environment Variables Setup

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

### Phase 2 SMTP Configuration (Mailtrap / MailHog for Local Dev)
Add your SMTP credentials to `.env`:
```env
# SMTP Configuration (Mailtrap Sandbox Example)
SMTP_HOST=sandbox.smtp.mailtrap.io
SMTP_PORT=2525
SMTP_USER=your_mailtrap_user
SMTP_PASSWORD=your_mailtrap_password
SMTP_FROM_NAME="Talent Acquisition Team"
SMTP_FROM_EMAIL=careers@company.example.com
SMTP_USE_TLS=true
```

> **Development Tip (Mailtrap)**:
> 1. Sign up for free at [Mailtrap.io](https://mailtrap.io/).
> 2. Create an **Email Testing Inbox**.
> 3. Copy `Host`, `Port`, `Username`, and `Password` into `.env`.
> 4. In Phase 2, all test emails will be captured safely inside your Mailtrap sandbox without contacting actual candidate addresses.

---

## 4. API Endpoints Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/shortlisted` | List candidates for approval review with status filter & sorting. |
| `GET` | `/candidates/{id}/match-details` | Full explainable match details, criteria pass/fail, and citations. |
| `POST` | `/candidates/{id}/approve` | Approves candidate, logs audit trail, and stubs email dispatch. |
| `POST` | `/candidates/{id}/reject` | Rejects candidate with reason and internal notes. |
| `POST` | `/candidates/{id}/hold` | Places candidate On Hold. |
| `GET` | `/candidates/{id}/email-preview` | Renders HTML & plain-text shortlist email preview. |
| `GET` | `/candidates/{id}/audit-logs` | Retrieves complete audit history for a candidate. |

---

## 5. Running Automated Tests

Run the dedicated approval workflow unit test suite:
```bash
python -m unittest tests/test_approval_workflow.py
```

Run the complete test suite:
```bash
python -m unittest discover tests
```

