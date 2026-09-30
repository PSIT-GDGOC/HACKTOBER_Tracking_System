# 🎃 GDGOC Hacktoberfest Platform — Complete End-to-End Testing & Lifecycle Guide

> **Official Testing Runbook & Operational Documentation**  
> Covers the complete lifecycle for **Maintainers**, **Student Contributors**, and the **Automated Tracking Engine**.

---

## 📑 Table of Contents

1. [System Architecture & Visual Workflow](#1-system-architecture--visual-workflow)
2. [Maintainer Guide: Setting Up, Creating Issues & Reviewing](#2-maintainer-guide-setting-up-creating-issues--reviewing)
3. [Student Guide: Onboarding, Claiming, Coding & PR Workflow](#3-student-guide-onboarding-claiming-coding--pr-workflow)
4. [Under the Hood: Automated Tracking & Webhook Processing](#4-under-the-hood-automated-tracking--webhook-processing)
5. [Merit, Scoring & End-of-Month Winner Counting](#5-merit-scoring--end-of-month-winner-counting)
6. [Step-by-Step Verification Runbook](#6-step-by-step-verification-runbook)
7. [Troubleshooting & Common Edge Cases](#7-troubleshooting--common-edge-cases)

---

## 1. System Architecture & Visual Workflow

```
+---------------------------------------------------------------------------------------------------------+
|                                    1. MAINTAINER SETUP                                                  |
|  - Main GitHub Repo configured with Webhook -> https://<backend-domain>/webhooks/github                |
|  - Maintainer creates Issue with labels: 'easy' / 'medium' / 'hard', 'hacktoberfest'                    |
+---------------------------------------------------+-----------------------------------------------------+
                                                    |
                                       GitHub Webhook: 'issues'
                                                    |
                                                    v
+---------------------------------------------------------------------------------------------------------+
|                                      2. SYSTEM INGESTION                                                |
|  - Backend verifies HMAC-SHA256 signature (`X-Hub-Signature-256`)                                       |
|  - Issue ingested into DB, difficulty assigned, published on Portal (`/issues`)                         |
+---------------------------------------------------+-----------------------------------------------------+
                                                    |
                                                    v
+---------------------------------------------------------------------------------------------------------+
|                                  3. STUDENT DISCOVERY & CLAIM                                           |
|  - Student logs in with Roll Number / Email -> Links GitHub username (`user.github_username`)           |
|  - Student clicks "Claim Issue" on Portal                                                               |
|  - DB creates active `Claim` + pending `Contribution` + starts countdown timer                          |
+---------------------------------------------------+-----------------------------------------------------+
                                                    |
                                                    v
+---------------------------------------------------------------------------------------------------------+
|                                    4. STUDENT DEV WORKFLOW                                              |
|  - Forks Main Repo -> Clones Fork locally -> Creates branch: `git checkout -b fix-issue-X`              |
|  - Solves issue -> Commits -> Pushes to Fork: `git push origin fix-issue-X`                             |
|  - Opens PR targeting Main Repo with description: "Fixes #X"                                            |
+---------------------------------------------------+-----------------------------------------------------+
                                                    |
                                   GitHub Webhook: 'pull_request' (opened)
                                                    |
                                                    v
+---------------------------------------------------------------------------------------------------------+
|                               5. AUTOMATED PR-TO-CLAIM LINKING                                          |
|  - Backend extracts `pr.user.login` and matches registered `user.github_username`                       |
|  - Backend parses issue ref ("Fixes #X") and matches active Claim                                       |
|  - Contribution status transitions: `claimed` -> `pr_submitted` / `under_review`                        |
|  - Student Dashboard updates in real time                                                               |
+---------------------------------------------------+-----------------------------------------------------+
                                                    |
                                                    v
+---------------------------------------------------------------------------------------------------------+
|                               6. MAINTAINER REVIEW & MERGE                                              |
|  - Maintainer reviews PR on GitHub (Requests changes OR Approves)                                       |
|  - Maintainer clicks "Merge pull request"                                                               |
+---------------------------------------------------+-----------------------------------------------------+
                                                    |
                                  GitHub Webhook: 'pull_request' (closed/merged)
                                                    |
                                                    v
+---------------------------------------------------------------------------------------------------------+
|                              7. RESOLUTION & MERIT ACCRUAL                                              |
|  - PR marked `MERGED` | Claim marked `COMPLETED` | Issue marked `CLOSED`                                |
|  - Contribution marked `MERGED` & validation_status = `VALID`                                            |
|  - Difficulty points awarded (+20 Easy, +40 Medium, +80 Hard)                                           |
|  - Student rises on the Leaderboard (`/leaderboard`) & announced in Activity Feed                       |
+---------------------------------------------------------------------------------------------------------+
```

---

## 2. Maintainer Guide: Setting Up, Creating Issues & Reviewing

### A. One-Time Webhook Configuration on Main Repository
Maintainers configure the webhook **once** on the organization / main repository:
1. Navigate to your GitHub repository: `https://github.com/<org>/<main-repo>`.
2. Go to **Settings** → **Webhooks** → Click **Add webhook**.
3. Fill out the fields:
   - **Payload URL**: `https://<your-backend-api-domain>/webhooks/github`  
     *(Example: `https://hacktober-tracking-system.onrender.com/webhooks/github`)*
   - **Content type**: `application/json` *(Crucial: do not use application/x-www-form-urlencoded)*
   - **Secret**: The exact value of `GITHUB_WEBHOOK_SECRET` in your backend server environment.
   - **SSL verification**: Enable SSL verification.
4. Under **Which events would you like to trigger this webhook?**:
   - Select **Let me select individual events**.
   - Check:
     - [x] **Issues**
     - [x] **Pull requests**
     - [x] **Pull request reviews**
     - [x] **Pushes**
5. Click **Add webhook**.
6. Verify under **Recent Deliveries** that the initial `ping` returned **`200 OK`**.

### B. Creating Tracked Issues
To publish tasks for students:
1. In the main repository, go to **Issues** → **New issue**.
2. Write a clear title and description outlining the required changes and acceptance criteria.
3. Apply labels on the right sidebar:
   - **Difficulty tag**: `easy`, `medium`, or `hard` *(determines points earned)*.
   - **Event tag**: `hacktoberfest`.
   - **Tech tag** *(optional)*: `frontend`, `backend`, `android`, `python`, `react`.
4. Click **Submit new issue**.
5. The GitHub webhook immediately dispatches the event, and the issue appears in the web portal within seconds.

### C. Reviewing & Merging Pull Requests
1. Open the Pull Request on GitHub.
2. Verify:
   - The student followed clean code practices.
   - The PR references the issue (e.g. `Fixes #12`).
   - The author's GitHub handle matches the claimed contributor on the portal.
3. **If changes are required**:
   - Click **Files changed** → **Review changes** → select **Request changes** and submit feedback.
   - The webhook notifies the student and updates their dashboard status to **`Changes Requested`**.
4. **If approved & ready**:
   - Click **Merge pull request** → **Confirm merge**.
   - The system automatically handles point awards, closes the claim, and logs the victory.

---

## 3. Student Guide: Onboarding, Claiming, Coding & PR Workflow

### Step 1: Account Creation & GitHub Linking
1. Open the Hacktoberfest Portal: `https://<portal-domain>`.
2. Register using college Roll Number or Email.
3. Complete ID verification (ID Card QR scan or verification code).
4. Go to **Profile** / **Settings**:
   - Link your **GitHub Username** (e.g., `octocat`).  
     *(CRITICAL: Must match the exact account used to author git commits).*

### Step 2: Browsing & Claiming an Issue
1. Navigate to the **Issues** tab on the portal.
2. Filter by difficulty (`Easy`, `Medium`, `Hard`) or tech stack.
3. Click on an available issue → Click **Claim Issue**:
   - A lock is placed on the issue. Other students cannot claim it.
   - A countdown timer (e.g. 48 hours) begins on your Dashboard.

### Step 3: Forking the Repository
Open-source contributors write code in their own copy of the project:
1. On GitHub, visit the main repository link provided on the issue card.
2. Click **Fork** (top-right corner) → Click **Create fork**.
3. You now have `https://github.com/<your-username>/<repo-name>`.

### Step 4: Local Setup & Branch Creation
Open your terminal (VS Code / Command Prompt) and run:

```bash
# 1. Clone your fork locally
git clone https://github.com/<your-username>/<repo-name>.git

# 2. Enter repository directory
cd <repo-name>

# 3. Create a clean dedicated feature branch
git checkout -b fix-issue-<issue_number>
```

### Step 5: Implement, Commit & Push
1. Make your code changes and test locally.
2. In VS Code, save all modified files (`Ctrl + S`).
3. Stage, commit, and push to your GitHub fork:

```bash
# 1. Check changed files
git status

# 2. Stage changes
git add .

# 3. Commit with a meaningful message
git commit -m "fix: resolve navigation bar alignment for issue #12"

# 4. Push to your fork
git push origin fix-issue-<issue_number>
```

> **Note on Push Permission Errors**:  
> If pushing fails with `permission denied`, ensure you are pushing to your **own fork URL** (`<your-username>/<repo-name>.git`) using a GitHub Personal Access Token (PAT).

### Step 6: Opening the Pull Request
1. Go to your fork on GitHub. Click **Compare & pull request** on the yellow banner.
2. In the PR form:
   - **Title**: `fix: resolve navigation layout for issue #12`
   - **Description**: Must contain the linking keyword:
     ```text
     Fixes #12
     
     ### Changes
     - Corrected CSS flex wrap on mobile viewport
     - Validated layout in Chrome and Firefox
     ```
3. Click **Create pull request**.
4. Check your student portal dashboard: status turns to **`PR Submitted`**!

---

## 4. Under the Hood: Automated Tracking & Webhook Processing

### HMAC-SHA256 Signature Verification
Every inbound request to `/webhooks/github` is signed with the header `X-Hub-Signature-256`.  
The backend computes:
```python
expected_signature = "sha256=" + hmac.new(
    key=settings.GITHUB_WEBHOOK_SECRET.encode(),
    msg=raw_body,
    digestmod=hashlib.sha256
).hexdigest()
```
If the signature doesn't match, the server returns `401 Unauthorized` immediately.

### Event Routing & State Transitions

| GitHub Webhook Event | Payload Condition | System Action | Contribution Status |
| :--- | :--- | :--- | :--- |
| `issues` | `action in ["opened", "labeled"]` | Creates/updates `Issue` record in DB with difficulty tags | `N/A` |
| `pull_request` | `action: "opened"` | Matches `pr.user.login` to `User.github_username`. Parses `Fixes #X` to match active `Claim`. | `claimed` ➔ `pr_submitted` |
| `pull_request_review` | `state: "changes_requested"` | Dispatches notification to student with review notes | `pr_submitted` ➔ `changes_requested` |
| `pull_request_review` | `state: "approved"` | Updates claim review indicator | `pr_submitted` ➔ `under_review` |
| `pull_request` | `action: "closed"`, `merged: true` | Closes PR & Issue, completes Claim, awards difficulty points | `pr_submitted` ➔ `MERGED` (`VALID`) |

---

## 5. Merit, Scoring & End-of-Month Winner Counting

### Scoring Matrix

| Issue Difficulty Label | Base Points Awarded | Review Speed Multiplier |
| :--- | :--- | :--- |
| `easy` | **20 Points** | Standard |
| `medium` | **40 Points** | Standard |
| `hard` | **80 Points** | Standard |

### How Maintainers Count Winners at Month-End

#### Option A: The Live Web Portal
Open `https://<portal-domain>/#/leaderboard`:
- Dynamic rankings sort students by:
  1. `total_points` (DESC)
  2. `merged_prs` (DESC)
  3. `valid_contributions` (DESC)
- Displays rank, avatar, student name, GitHub handle, total merged PR count, and total score.

#### Option B: Automated REST API
Maintainers or automated certificate bots can query:
```http
GET /api/v1/leaderboard?per_page=100
```
Returns a structured JSON payload with all student rankings and contribution counts.

#### Option C: Official College SQL Export (For Swag & Certificates)
Run this query directly in the **Neon PostgreSQL Console** to export a clean CSV:

```sql
SELECT 
    u.psit_roll_no               AS "Roll Number",
    u.name                       AS "Student Name",
    u.email                      AS "Registered Email",
    u.github_username            AS "GitHub Handle",
    COUNT(DISTINCT pr.id)        AS "Total Merged PRs",
    COALESCE(SUM(
        CASE 
            WHEN i.difficulty = 'hard' THEN 80
            WHEN i.difficulty = 'medium' THEN 40
            ELSE 20
        END
    ), 0)                        AS "Total Points",
    COUNT(DISTINCT c.id)         AS "Valid Contributions"
FROM users u
LEFT JOIN pull_requests pr ON pr.user_id = u.id AND pr.status = 'merged'
LEFT JOIN contributions c  ON c.user_id = u.id AND c.status = 'merged'
LEFT JOIN issues i         ON i.id = c.issue_id
WHERE u.role = 'student'
GROUP BY u.id, u.psit_roll_no, u.name, u.email, u.github_username
ORDER BY "Total Points" DESC, "Total Merged PRs" DESC;
```

---

## 6. Step-by-Step Verification Runbook

Follow this checklist to test any newly deployed instance:

| Step | Action | Expected Result | Pass/Fail |
| :--- | :--- | :--- | :--- |
| **1** | Ping Webhook from GitHub Settings | GitHub Recent Deliveries returns `200 OK`. | `[ ]` |
| **2** | Create Issue on GitHub with label `easy` | Issue appears on `/issues` page with 20 pt badge. | `[ ]` |
| **3** | Student registers & links GitHub username | Profile displays verified handle. | `[ ]` |
| **4** | Student claims Issue on portal | Issue shows "Claimed"; timer begins on dashboard. | `[ ]` |
| **5** | Second student attempts to claim same issue | System rejects with 400 (Already Claimed). | `[ ]` |
| **6** | Student forks repo, creates branch, pushes commit | Code visible on student's GitHub fork. | `[ ]` |
| **7** | Student opens PR with `Fixes #X` | Webhook delivery returns `200`; dashboard shows `PR Submitted`. | `[ ]` |
| **8** | Maintainer requests changes | Dashboard badge switches to `Changes Requested`. | `[ ]` |
| **9** | Maintainer merges PR on GitHub | Webhook delivery returns `200`; status turns `Merged`. | `[ ]` |
| **10** | Student checks Leaderboard | Student ranks with +20 points and 1 merged PR. | `[ ]` |

---

## 7. Troubleshooting & Common Edge Cases

### 1. Webhook Returns `401 Unauthorized`
- **Cause**: The Secret entered in GitHub repository settings does not match `GITHUB_WEBHOOK_SECRET` in the backend server's environment variables.
- **Solution**: Copy the secret from your Render/Railway dashboard and paste it into GitHub's Webhook Secret field.

### 2. `git push` Fails with `(permission denied)`
- **Cause**: The student is trying to push directly to the organization's main repo instead of their own fork, OR Windows Credential Manager is using an old account.
- **Solution**: Fork the repository first, set the remote to the fork (`git remote set-url origin https://github.com/<username>/<repo>.git`), and push using a GitHub Personal Access Token (PAT).

### 3. Git Says `nothing to commit, working tree clean`
- **Cause**: Files were created outside the repository directory, or files have unsaved changes in the editor.
- **Solution**: Save the file (`Ctrl + S`), verify file location in the VS Code explorer, and move it inside the cloned folder.

### 4. PR Merged but Points Not Awarded
- **Cause**: The student forgot to include `Fixes #<number>` in the PR description, or their GitHub username on the portal had a typo.
- **Solution**: Maintainers can use the portal's **Admin / Maintainer Drawer** to manually validate and complete the claim, awarding points retroactively.
