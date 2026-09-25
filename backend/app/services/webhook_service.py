import hashlib
import hmac
from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.config import settings
from app.models import (
    Repository,
    Issue, IssueStatus, IssueDifficulty,
    Claim, ClaimStatus,
    PullRequest, PRStatus,
    Commit,
    Contribution, ContributionStatus, ContributionValidation,
    Review, ReviewStatus,
    Notification,
    ActivityFeed,
    User, UserRole
)
from app.services.issue_service import _infer_issue_metadata

logger = logging.getLogger(__name__)


def verify_github_signature(raw_body: bytes, signature_header: Optional[str]) -> bool:
    """
    Verify GitHub HMAC-SHA256 webhook signature.
    Prevents unauthorized or spoofed webhook payloads.
    """
    secret = settings.GITHUB_WEBHOOK_SECRET
    if not secret:
        # In local dev if no secret configured, allow with warning
        logger.warning("GITHUB_WEBHOOK_SECRET is empty. Webhook signature verification bypassed.")
        return True

    if not signature_header:
        return False

    if not signature_header.startswith("sha256="):
        return False

    expected_signature = "sha256=" + hmac.new(
        key=secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_signature, signature_header)


def process_webhook_event(event_type: str, payload: Dict[str, Any], db: Session) -> Dict[str, Any]:
    """
    Central dispatcher routing GitHub webhook events to specialized handlers.
    Dispatches:
      - ping
      - issues
      - pull_request
      - push
      - pull_request_review
    """
    if event_type == "ping":
        zen = payload.get("zen", "pong")
        return {"status": "success", "event": "ping", "detail": f"Ping received: {zen}"}

    repo_data = payload.get("repository", {})
    repo_url = repo_data.get("html_url") or repo_data.get("url")
    repo = None
    if repo_url:
        repo = db.query(Repository).filter(Repository.github_repo_url.ilike(f"%{repo_data.get('name', '')}%")).first()
        if not repo:
            repo = db.query(Repository).filter(Repository.name == repo_data.get("name")).first()

    if event_type == "issues":
        return _handle_issues_event(payload, repo, db)
    elif event_type == "pull_request":
        return _handle_pull_request_event(payload, repo, db)
    elif event_type == "push":
        return _handle_push_event(payload, repo, db)
    elif event_type == "pull_request_review":
        return _handle_pull_request_review_event(payload, repo, db)
    else:
        return {"status": "ignored", "event": event_type, "detail": f"Unhandled event type '{event_type}'."}


def _handle_issues_event(payload: Dict[str, Any], repo: Optional[Repository], db: Session) -> Dict[str, Any]:
    """Handle issue lifecycle events (opened, edited, labeled, closed, reopened)."""
    action = payload.get("action")
    issue_data = payload.get("issue", {})
    gh_issue_id = issue_data.get("id")

    if not gh_issue_id:
        return {"status": "error", "event": "issues", "action": action, "detail": "Missing issue data in payload."}

    issue = db.query(Issue).filter(Issue.github_issue_id == gh_issue_id).first()
    label_names = [lbl["name"] for lbl in issue_data.get("labels", []) if isinstance(lbl, dict) and "name" in lbl]
    difficulty, category, tech_tags = _infer_issue_metadata(label_names)

    if not issue and repo:
        issue = Issue(
            repo_id=repo.id,
            github_issue_id=gh_issue_id,
            title=issue_data.get("title", "Untitled"),
            description=issue_data.get("body", ""),
            difficulty=difficulty,
            category=category,
            tech_tags=tech_tags,
            labels=label_names,
            status=IssueStatus.OPEN,
        )
        db.add(issue)
        db.flush()
    elif issue:
        issue.title = issue_data.get("title", issue.title)
        issue.description = issue_data.get("body", issue.description)
        issue.labels = label_names
        issue.tech_tags = tech_tags
        if category:
            issue.category = category

    if issue:
        if action == "closed":
            issue.status = IssueStatus.CLOSED
        elif action == "reopened":
            issue.status = IssueStatus.OPEN

    db.commit()
    return {"status": "success", "event": "issues", "action": action, "detail": f"Issue #{gh_issue_id} processed."}


def _handle_pull_request_event(payload: Dict[str, Any], repo: Optional[Repository], db: Session) -> Dict[str, Any]:
    """
    Handle pull_request events.
    Auto-links PR to student's claimed issue via GitHub username match.
    Updates contribution lifecycle state machine.
    """
    action = payload.get("action")
    pr_data = payload.get("pull_request", {})
    gh_pr_id = pr_data.get("id")
    pr_title = pr_data.get("title", "Untitled PR")
    pr_number = pr_data.get("number")
    merged = pr_data.get("merged", False)
    author_login = (pr_data.get("user") or {}).get("login")

    now = datetime.now(timezone.utc)

    # 1. Match PR author with student in DB
    author_user = None
    if author_login:
        author_user = db.query(User).filter(User.github_username.ilike(author_login)).first()

    # 2. Match repository if not found
    repo_id = repo.id if repo else 1

    # 3. Find or create PullRequest record
    pr = db.query(PullRequest).filter(PullRequest.github_pr_id == gh_pr_id).first()
    if not pr:
        pr = PullRequest(
            repo_id=repo_id,
            github_pr_id=gh_pr_id,
            user_id=author_user.id if author_user else 1,
            title=pr_title,
            status=PRStatus.OPEN,
        )
        db.add(pr)
        db.flush()

    # 4. Auto-link to active claim if author is verified student
    linked_issue_id = pr.issue_id
    if author_user and not linked_issue_id:
        active_claim = (
            db.query(Claim)
            .filter(Claim.user_id == author_user.id, Claim.status == ClaimStatus.ACTIVE)
            .order_by(Claim.claimed_at.desc())
            .first()
        )
        if active_claim:
            pr.issue_id = active_claim.issue_id
            linked_issue_id = active_claim.issue_id

            # Move issue to IN_PROGRESS
            issue = db.query(Issue).filter(Issue.id == active_claim.issue_id).first()
            if issue and issue.status == IssueStatus.CLAIMED:
                issue.status = IssueStatus.IN_PROGRESS

            # Update or create contribution state machine
            contrib = (
                db.query(Contribution)
                .filter(Contribution.issue_id == active_claim.issue_id, Contribution.user_id == author_user.id)
                .order_by(Contribution.created_at.desc())
                .first()
            )
            if contrib:
                contrib.pr_id = pr.id
                contrib.status = ContributionStatus.PR_SUBMITTED
                timeline = list(contrib.timeline_json or [])
                timeline.append({
                    "status": "pr_submitted",
                    "timestamp": now.isoformat(),
                    "detail": f"PR #{pr_number} submitted on GitHub by @{author_login}"
                })
                contrib.timeline_json = timeline

    # 5. Handle action-specific transitions
    if action in ["opened", "reopened"]:
        pr.status = PRStatus.OPEN
        pr.title = pr_title

        # Record activity feed
        db.add(ActivityFeed(
            type="pr_opened",
            actor_id=author_user.id if author_user else None,
            target_type="pull_request",
            target_id=pr.id,
            created_at=now,
        ))

        # Notify student author
        if author_user:
            db.add(Notification(
                user_id=author_user.id,
                type="pr_opened",
                payload={
                    "title": f"🚀 PR #{pr_number} Linked",
                    "message": f"Your PR '{pr.title}' has been linked to your contribution.",
                    "pr_id": pr.id,
                    "issue_id": linked_issue_id,
                },
                read=False,
                created_at=now,
            ))
    elif action == "closed":
        if merged:
            pr.status = PRStatus.MERGED
            # Contribution marked MERGED and VALID
            if linked_issue_id and author_user:
                contrib = (
                    db.query(Contribution)
                    .filter(Contribution.issue_id == linked_issue_id, Contribution.user_id == author_user.id)
                    .order_by(Contribution.created_at.desc())
                    .first()
                )
                if contrib:
                    contrib.status = ContributionStatus.MERGED
                    contrib.validation_status = ContributionValidation.VALID
                    timeline = list(contrib.timeline_json or [])
                    timeline.append({
                        "status": "merged",
                        "timestamp": now.isoformat(),
                        "detail": f"PR #{pr_number} successfully merged into main!"
                    })
                    contrib.timeline_json = timeline

                # Close issue & complete claim
                issue = db.query(Issue).filter(Issue.id == linked_issue_id).first()
                if issue:
                    issue.status = IssueStatus.CLOSED

                claim = (
                    db.query(Claim)
                    .filter(Claim.issue_id == linked_issue_id, Claim.user_id == author_user.id, Claim.status == ClaimStatus.ACTIVE)
                    .first()
                )
                if claim:
                    claim.status = ClaimStatus.COMPLETED

                # Send celebration notification
                db.add(Notification(
                    user_id=author_user.id,
                    type="pr_merged",
                    payload={
                        "title": "🎉 PR Merged!",
                        "message": f"Your PR '{pr.title}' was merged. Your contribution is validated!",
                        "pr_id": pr.id,
                        "issue_id": linked_issue_id
                    },
                    read=False
                ))

                # Record in activity feed
                db.add(ActivityFeed(
                    type="pr_merged",
                    actor_id=author_user.id if author_user else None,
                    target_type="pull_request",
                    target_id=pr.id,
                    created_at=now,
                ))
        else:
            pr.status = PRStatus.CLOSED

    db.commit()
    return {
        "status": "success",
        "event": "pull_request",
        "action": action,
        "detail": f"PR #{pr_number} processed. Auto-linked to issue ID: {linked_issue_id}",
        "data": {"pr_id": pr.id, "linked_issue_id": linked_issue_id, "status": pr.status.value}
    }


def _handle_push_event(payload: Dict[str, Any], repo: Optional[Repository], db: Session) -> Dict[str, Any]:
    """Handle push events to extract and record commits linked to author and repo."""
    commits_data = payload.get("commits", [])
    repo_id = repo.id if repo else 1
    sender_login = (payload.get("sender") or {}).get("login")
    now = datetime.now(timezone.utc)

    sender_user = None
    if sender_login:
        sender_user = db.query(User).filter(User.github_username.ilike(sender_login)).first()

    saved_count = 0
    for c_data in commits_data:
        commit_sha = c_data.get("id")
        message = c_data.get("message", "No commit message")
        if not commit_sha:
            continue

        existing = db.query(Commit).filter(Commit.github_commit_sha == commit_sha).first()
        if existing:
            continue

        author_info = c_data.get("author", {})
        committer_user = sender_user
        if not committer_user and author_info.get("username"):
            committer_user = db.query(User).filter(User.github_username.ilike(author_info["username"])).first()
        if not committer_user and author_info.get("email"):
            committer_user = db.query(User).filter(User.email.ilike(author_info["email"])).first()

        # Check if committer has an active claim
        linked_issue_id = None
        if committer_user:
            active_claim = (
                db.query(Claim)
                .filter(Claim.user_id == committer_user.id, Claim.status == ClaimStatus.ACTIVE)
                .order_by(Claim.claimed_at.desc())
                .first()
            )
            if active_claim:
                linked_issue_id = active_claim.issue_id

        commit_record = Commit(
            repo_id=repo_id,
            github_commit_sha=commit_sha,
            user_id=committer_user.id if committer_user else None,
            message=message,
            issue_id=linked_issue_id,
            committed_at=now,
        )
        db.add(commit_record)
        saved_count += 1

    db.commit()
    return {
        "status": "success",
        "event": "push",
        "detail": f"Processed push event. Recorded {saved_count} new commits.",
        "data": {"recorded_commits": saved_count}
    }


def _handle_pull_request_review_event(payload: Dict[str, Any], repo: Optional[Repository], db: Session) -> Dict[str, Any]:
    """Handle pull_request_review events, record Review, update Contribution, notify student."""
    action = payload.get("action")
    review_data = payload.get("review", {})
    pr_data = payload.get("pull_request", {})
    gh_pr_id = pr_data.get("id")
    state = (review_data.get("state") or "").lower()
    review_comment = review_data.get("body") or ""
    reviewer_login = (review_data.get("user") or {}).get("login")
    now = datetime.now(timezone.utc)

    pr = db.query(PullRequest).filter(PullRequest.github_pr_id == gh_pr_id).first()
    if not pr:
        return {"status": "error", "event": "pull_request_review", "detail": f"PR with github_pr_id {gh_pr_id} not found."}

    # Find reviewer user
    reviewer_user = None
    if reviewer_login:
        reviewer_user = db.query(User).filter(User.github_username.ilike(reviewer_login)).first()

    # Map state to ReviewStatus
    status_map = {
        "approved": ReviewStatus.APPROVED,
        "changes_requested": ReviewStatus.CHANGES_REQUESTED,
        "commented": ReviewStatus.COMMENTED,
        "dismissed": ReviewStatus.DISMISSED,
    }
    review_status = status_map.get(state, ReviewStatus.COMMENTED)

    # Save review record
    review = Review(
        pr_id=pr.id,
        reviewer_id=reviewer_user.id if reviewer_user else 1,
        status=review_status,
        comment=review_comment,
        reviewed_at=now,
    )
    db.add(review)

    # Update contribution lifecycle status
    if pr.issue_id:
        contrib = (
            db.query(Contribution)
            .filter(Contribution.issue_id == pr.issue_id, Contribution.user_id == pr.user_id)
            .order_by(Contribution.created_at.desc())
            .first()
        )
        if contrib:
            timeline = list(contrib.timeline_json or [])
            if review_status == ReviewStatus.APPROVED:
                contrib.status = ContributionStatus.ACCEPTED
                timeline.append({"status": "accepted", "timestamp": now.isoformat(), "detail": f"Review approved by @{reviewer_login}"})
            elif review_status == ReviewStatus.CHANGES_REQUESTED:
                contrib.status = ContributionStatus.CHANGES_REQUESTED
                timeline.append({"status": "changes_requested", "timestamp": now.isoformat(), "detail": f"Changes requested by @{reviewer_login}: {review_comment[:100]}"})
            elif review_status == ReviewStatus.COMMENTED:
                contrib.status = ContributionStatus.UNDER_REVIEW
                timeline.append({"status": "under_review", "timestamp": now.isoformat(), "detail": f"Maintainer commented: {review_comment[:100]}"})
            contrib.timeline_json = timeline

    # Send notification to PR author
    if pr.user_id:
        db.add(Notification(
            user_id=pr.user_id,
            type="pr_review",
            payload={
                "title": f"Review on PR #{pr_data.get('number')}",
                "message": f"Reviewer @{reviewer_login or 'maintainer'} submitted a review: {review_status.value.replace('_', ' ').title()}",
                "pr_id": pr.id,
                "status": review_status.value
            },
            read=False
        ))

    # Record in activity feed
    db.add(ActivityFeed(
        type="review_submitted",
        actor_id=reviewer_user.id if reviewer_user else None,
        target_type="pull_request",
        target_id=pr.id,
        created_at=now,
    ))

    db.commit()
    return {
        "status": "success",
        "event": "pull_request_review",
        "action": action,
        "detail": f"Review recorded for PR #{pr_data.get('number')} with status '{review_status.value}'.",
        "data": {"review_id": review.id, "status": review_status.value}
    }
