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

### Phase 2 SMTP Configuration (Real Gmail Account via SMTP)
To send real shortlist emails directly to candidates using your personal or company Gmail account, add your credentials to `.env`:

```env
# Gmail SMTP Configuration for Real Emails
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_16_character_app_password
SMTP_FROM_NAME="Talent Acquisition Team"
SMTP_FROM_EMAIL=your_email@gmail.com
SMTP_USE_TLS=true
SMTP_USE_SSL=false
```

### How to Get a Google App Password (Required for Gmail)
Google requires an **App Password** (16 characters) instead of your regular password:
1. Log into your Google Account: [Google Account Security](https://myaccount.google.com/security).
2. Ensure **2-Step Verification** is turned **ON**.
3. In the search bar at the top or under "How you sign in to Google", select **App passwords** (direct URL: [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)).
4. Enter an app name, e.g., `RAG Pro HR`, and click **Create**.
5. Google will display a 16-character code (e.g., `abcd efgh ijkl mnop`).
6. Copy that code and paste it into `.env` as `SMTP_PASSWORD`.
7. Set `SMTP_USER` and `SMTP_FROM_EMAIL` to your Gmail address.
8. That's it! When you approve a candidate, a real email is delivered directly to their inbox from your Gmail address.

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
| `POST` | `/candidates/{id}/retry-email` | Re-queues email delivery for candidates with failed email status. |
| `GET` | `/candidates/{id}/email-logs` | Retrieves email delivery log history (attempts, timestamps, errors). |

---

## 5. Phase 2 SMTP Delivery System

### Email Lifecycle & Retry Worker
1. **Human Trigger**: HR reviews candidate match details and clicks **"Approve & Send Shortlist Mail"**.
2. **Immediate Enqueue**:
   - Status updates to `Approved & Email Queued`.
   - Idempotency guard checks `has_successful_email_sent` to guarantee no candidate receives duplicate shortlist emails.
   - Initial dispatch log inserted into `email_logs` table (`status = 'pending'`, `attempts = 0`).
   - Background worker task `deliver_shortlist_email_task` is scheduled via FastAPI `BackgroundTasks`.
3. **Delivery Worker**:
   - Enforces a rate limit delay to avoid spamming the SMTP relay.
   - Attempts SMTP transport up to **3 times** with exponential backoff (`1s`, `2s`, `4s`).
   - On success:
     - `email_logs.status` $\rightarrow$ `sent`
     - Candidate status $\rightarrow$ `Shortlisted - Email Sent`
     - Audit log recorded $\rightarrow$ `SHORTLIST_EMAIL_SENT`
   - On failure after 3 attempts:
     - `email_logs.status` $\rightarrow$ `failed` (with full error message)
     - Candidate status $\rightarrow$ `Shortlisted - Email Failed`
     - Audit log recorded $\rightarrow$ `SHORTLIST_EMAIL_FAILED`
4. **Manual Retry Action**:
   - Candidates in status `Shortlisted - Email Failed` display a prominent **"Retry Email Send"** button in the review toolbar.
   - Clicking retry calls `POST /candidates/{id}/retry-email`, re-enqueues the background worker, and updates status back to `Approved & Email Queued`.

---

## 6. Running Automated Tests

Run the dedicated approval workflow unit test suite (Phase 1):
```bash
python -m unittest tests/test_approval_workflow.py
```

Run the Phase 2 SMTP email system unit test suite:
```bash
python -m unittest tests/test_smtp_email.py
```

Run all tests:
```bash
python -m unittest discover tests
```


