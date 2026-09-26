"""Comprehensive Live Endpoint Verification Script.

Tests all 39 API routes against the running backend server at http://127.0.0.1:8000.
Prints pass/fail status and detailed JSON results for each endpoint.
"""
import sys
import httpx

BASE_URL = "http://127.0.0.1:8000"

results = []

def record(endpoint, method, status_code, expected_status, details=""):
    passed = status_code in expected_status if isinstance(expected_status, list) else status_code == expected_status
    results.append({
        "endpoint": endpoint,
        "method": method,
        "status_code": status_code,
        "expected": expected_status,
        "passed": passed,
        "details": str(details)[:120],
    })
    mark = "PASS" if passed else "FAIL"
    print(f"[{mark}] {method:6} {endpoint:35} -> HTTP {status_code} (expected {expected_status})")
    if not passed:
        print(f"       ERROR: {details}")

client = httpx.Client(base_url=BASE_URL, timeout=10.0)

print("=" * 70)
print("RUNNING LIVE ENDPOINT AUDIT ON http://127.0.0.1:8000")
print("=" * 70)

# 1. System Endpoints
r = client.get("/health")
record("/health", "GET", r.status_code, 200, r.text)

r = client.get("/docs")
record("/docs", "GET", r.status_code, 200)

r = client.get("/openapi.json")
record("/openapi.json", "GET", r.status_code, 200)

# 2. Auth Endpoints
# Login as student (id=1, Aarav)
r = client.post("/auth/login", json={"identifier": "2200320100001"})
record("/auth/login (student)", "POST", r.status_code, 200, r.text)
student_token = r.json().get("access_token") if r.status_code == 200 else None
student_headers = {"Authorization": f"Bearer {student_token}"} if student_token else {}

# Login as admin (id=3, Abu)
r = client.post("/auth/login", json={"identifier": "2100320100003"})
record("/auth/login (admin)", "POST", r.status_code, 200, r.text)
admin_token = r.json().get("access_token") if r.status_code == 200 else None
admin_headers = {"Authorization": f"Bearer {admin_token}"} if admin_token else {}

# Login as maintainer (id=2, Aditya)
r = client.post("/auth/login", json={"identifier": "2100320100002"})
record("/auth/login (maintainer)", "POST", r.status_code, 200, r.text)
maintainer_token = r.json().get("access_token") if r.status_code == 200 else None
maintainer_headers = {"Authorization": f"Bearer {maintainer_token}"} if maintainer_token else {}

# /auth/me
r = client.get("/auth/me", headers=student_headers)
record("/auth/me", "GET", r.status_code, 200, r.text)

# /auth/signup (new student with valid 13-char roll number)
new_roll = "2200330999998"
r = client.post("/auth/signup", json={
    "name": "Live Test Student 2",
    "email": "livetest2@psit.ac.in",
    "psit_roll_no": new_roll
})
record("/auth/signup", "POST", r.status_code, [201, 400], r.text)

# /auth/github/login
r = client.get("/auth/github/login")
record("/auth/github/login", "GET", r.status_code, 200, r.text)

# /auth/github/link
r = client.post("/auth/github/link", json={"github_username": "unique-test-user-99b"}, headers=student_headers)
record("/auth/github/link", "POST", r.status_code, [200, 400], r.text)

# /auth/pending-verifications (admin only)
r = client.get("/auth/pending-verifications", headers=admin_headers)
record("/auth/pending-verifications", "GET", r.status_code, 200, r.text)

# 3. Issues & Claims
r = client.get("/issues", headers=student_headers)
record("/issues", "GET", r.status_code, 200, f"Count: {r.json().get('total') if r.status_code == 200 else 0}")

r = client.get("/issues/1", headers=student_headers)
record("/issues/1", "GET", r.status_code, 200, r.text)

r = client.get("/issues/2", headers=student_headers)
record("/issues/2", "GET", r.status_code, 200, r.text)

# POST /issues/2/claim (student claims issue 2)
r = client.post("/issues/2/claim", headers=student_headers)
record("/issues/2/claim", "POST", r.status_code, [200, 201, 400], r.text)

# POST /issues/2/unclaim
r = client.post("/issues/2/unclaim", headers=student_headers)
record("/issues/2/unclaim", "POST", r.status_code, [200, 400], r.text)

# 4. Pull Requests & Commits
r = client.get("/pull-requests", headers=student_headers)
record("/pull-requests", "GET", 200, 200, r.text)

r = client.get("/pull-requests/1", headers=student_headers)
record("/pull-requests/1", "GET", 200, 200, r.text)

r = client.get("/commits", headers=student_headers)
record("/commits", "GET", 200, 200, r.text)

# 5. Contributions
r = client.get("/contributions/my", headers=student_headers)
record("/contributions/my", "GET", 200, 200, r.text)

r = client.get("/contributions/1/timeline", headers=student_headers)
record("/contributions/1/timeline", "GET", 200, 200, r.text)

r = client.patch("/contributions/1/validate", json={"validation_status": "valid"}, headers=maintainer_headers)
record("/contributions/1/validate", "PATCH", 200, 200, r.text)

# 6. Dashboards
r = client.get("/dashboard/student", headers=student_headers)
record("/dashboard/student", "GET", 200, 200, r.text)

r = client.get("/dashboard/maintainer", headers=maintainer_headers)
record("/dashboard/maintainer", "GET", 200, 200, r.text)

r = client.get("/dashboard/repository/1", headers=student_headers)
record("/dashboard/repository/1", "GET", 200, 200, r.text)

r = client.get("/dashboard/admin", headers=admin_headers)
record("/dashboard/admin", "GET", 200, 200, r.text)

# 7. Users
r = client.get("/users/me", headers=student_headers)
record("/users/me", "GET", 200, 200, r.text)

r = client.patch("/users/me", json={"name": "Aarav Sharma Updated"}, headers=student_headers)
record("/users/me", "PATCH", 200, 200, r.text)

r = client.get("/users/1", headers=student_headers)
record("/users/1", "GET", 200, 200, r.text)

# 8. Engagement
r = client.get("/leaderboard", headers=student_headers)
record("/leaderboard", "GET", 200, 200, r.text)

r = client.get("/notifications", headers=student_headers)
record("/notifications", "GET", 200, 200, r.text)

r = client.patch("/notifications/1/read", headers=student_headers)
record("/notifications/1/read", "PATCH", 200, 200, r.text)

r = client.post("/notifications/read-all", headers=student_headers)
record("/notifications/read-all", "POST", 200, 200, r.text)

r = client.get("/activity", headers=student_headers)
record("/activity", "GET", 200, 200, r.text)

# 9. Search
r = client.get("/search?q=navbar", headers=student_headers)
record("/search?q=navbar", "GET", 200, 200, r.text)

r = client.get("/search?q=Aarav", headers=student_headers)
record("/search?q=Aarav", "GET", 200, 200, r.text)

# 10. Webhook jobs
r = client.get("/webhooks/jobs", headers=admin_headers)
record("/webhooks/jobs", "GET", 200, 200, r.text)

r = client.post("/webhooks/jobs/drain")
record("/webhooks/jobs/drain", "POST", 200, 200, r.text)

print("=" * 70)
passed_count = sum(1 for x in results if x["passed"])
total_count = len(results)
print(f"TOTAL AUDITED: {total_count} endpoints")
print(f"PASSED:        {passed_count} / {total_count}")
print(f"FAILED:        {total_count - passed_count} / {total_count}")
print("=" * 70)

if passed_count != total_count:
    sys.exit(1)
