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

    # If a secret is configured or running in production:
    if secret or (settings.ENV != "development" and not settings.DEBUG):
        if not secret:
            logger.error("Rejecting webhook in production: GITHUB_WEBHOOK_SECRET is not configured.")
            return False
        if not signature_header or not signature_header.startswith("sha256="):
            logger.error("Rejecting webhook: Missing or malformed X-Hub-Signature-256 header.")
            return False
        expected_signature = "sha256=" + hmac.new(
            key=secret.encode("utf-8"),
            msg=raw_body,
            digestmod=hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_signature, signature_header)

    # In local development / test mode with no secret configured:
    if signature_header:
        dev_secret = "dev_webhook_secret_for_testing"
        if not signature_header.startswith("sha256="):
            return False
        expected_signature = "sha256=" + hmac.new(
            key=dev_secret.encode("utf-8"),
            msg=raw_body,
            digestmod=hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_signature, signature_header)

    logger.warning("No secret configured and no signature provided. Allowed only in dev/test environment.")
    return True


def _get_or_create_repo_from_payload(payload: Dict[str, Any], db: Session) -> Optional[Repository]:
    """Dynamically get or create a Repository from webhook payload."""
    repo_data = payload.get("repository")
    if not repo_data or not isinstance(repo_data, dict):
        return None

    repo_url = repo_data.get("html_url") or repo_data.get("url")
    repo_name = repo_data.get("name")
    if not repo_name and not repo_url:
        return None

    if not repo_name and repo_url:
        repo_name = repo_url.rstrip("/").split("/")[-1]
    if not repo_url and repo_name:
        repo_url = f"https://github.com/PSIT-GDGOC/{repo_name}"

    repo = None
    if repo_url:
        repo = db.query(Repository).filter(Repository.github_repo_url.ilike(repo_url)).first()
        if not repo and repo_name:
            repo = db.query(Repository).filter(Repository.github_repo_url.ilike(f"%{repo_name}%")).first()
    if not repo and repo_name:
        repo = db.query(Repository).filter(Repository.name.ilike(repo_name)).first()

    if not repo:
        from app.models import PlatformType
        lower_name = (repo_name or "").lower()
        lower_url = (repo_url or "").lower()
        platform = PlatformType.ANDROID if ("android" in lower_name or "android" in lower_url) else PlatformType.WEB
        
        repo = Repository(
            name=repo_name,
            github_repo_url=repo_url,
            platform=platform
        )
        db.add(repo)
        try:
            db.commit()
            db.refresh(repo)
            logger.info(f"Auto-registered new repository from webhook: {repo_name} ({repo_url})")
        except Exception as e:
            db.rollback()
            logger.warning(f"Failed to auto-create repository '{repo_name}': {e}")
            repo = db.query(Repository).filter(Repository.name == repo_name).first()

    return repo


def _handle_repository_event(payload: Dict[str, Any], db: Session) -> Dict[str, Any]:
    """Handle repository lifecycle webhook events (created, deleted, edited, publicized, privatized, archived)."""
    action = payload.get("action")
    repo_data = payload.get("repository", {})
    repo_name = repo_data.get("name")
    repo_url = repo_data.get("html_url") or repo_data.get("url")

    if not repo_name and not repo_url:
        return {"status": "error", "event": "repository", "action": action, "detail": "Missing repository data in payload."}

    if action in ["created", "publicized", "renamed", "edited", "unarchived", "transferred"]:
        repo = _get_or_create_repo_from_payload(payload, db)
        if repo:
            if repo_name and repo.name != repo_name:
                repo.name = repo_name
            if repo_url and repo.github_repo_url != repo_url:
                repo.github_repo_url = repo_url
            db.commit()
            return {
                "status": "success",
                "event": "repository",
                "action": action,
                "detail": f"Repository '{repo.name}' synchronized (ID: {repo.id})."
            }
    elif action in ["deleted", "privatized", "archived"]:
        repo = None
        if repo_url:
            repo = db.query(Repository).filter(Repository.github_repo_url.ilike(repo_url)).first()
        if not repo and repo_name:
            repo = db.query(Repository).filter(Repository.name.ilike(repo_name)).first()

        if repo:
            deleted_id = repo.id
            deleted_name = repo.name
            db.delete(repo)
            db.commit()
            return {
                "status": "success",
                "event": "repository",
                "action": action,
                "detail": f"Repository '{deleted_name}' (ID: {deleted_id}) removed from system due to GitHub event '{action}'."
            }

    return {"status": "ignored", "event": "repository", "action": action, "detail": f"Repository action '{action}' acknowledged."}


def process_webhook_event(event_type: str, payload: Dict[str, Any], db: Session) -> Dict[str, Any]:
    """
    Central dispatcher routing GitHub webhook events to specialized handlers.
    Dispatches:
      - ping
      - repository
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

    if not repo and repo_data.get("name"):
        try:
            from app.services.org_sync_service import sync_single_repo_from_webhook
            repo = sync_single_repo_from_webhook(db=db, repo_data=repo_data)
        except Exception as e:
            logger.warning("Could not auto-create repo for webhook event: %s", e)

    if not repo:
        repo = _get_or_create_repo_from_payload(payload, db)

    if event_type == "repository":
        return _handle_repository_event(payload, db)
    elif event_type == "issues":
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
    """Handle issue lifecycle events (opened, edited, labeled, closed, reopened, deleted)."""
    action = payload.get("action")
    issue_data = payload.get("issue", {})
    gh_issue_id = issue_data.get("id")

    if not gh_issue_id:
        return {"status": "error", "event": "issues", "action": action, "detail": "Missing issue data in payload."}

    if not repo:
        repo = _get_or_create_repo_from_payload(payload, db)

    issue = db.query(Issue).filter(Issue.github_issue_id == gh_issue_id).first()
    if not repo and issue:
        repo = db.query(Repository).filter(Repository.id == issue.repo_id).first()

    if action == "deleted" and issue:
        db.delete(issue)
        db.commit()
        return {"status": "success", "event": "issues", "action": action, "detail": f"Issue #{gh_issue_id} deleted."}

    label_names = [lbl["name"] for lbl in issue_data.get("labels", []) if isinstance(lbl, dict) and "name" in lbl]
    difficulty, category, tech_tags = _infer_issue_metadata(label_names)

    # If repo wasn't matched upstream, attempt to find or auto-create it now
    if not repo:
        repo_data = payload.get("repository", {})
        repo_name = repo_data.get("name")
        if repo_name:
            repo = db.query(Repository).filter(Repository.name == repo_name).first()
            if not repo:
                try:
                    from app.services.org_sync_service import sync_single_repo_from_webhook
                    repo = sync_single_repo_from_webhook(db=db, repo_data=repo_data)
                except Exception as e:
                    logger.warning("Error auto-creating repo for issue webhook: %s", e)

    if not repo and not issue:
        logger.error(
            "Cannot process issue #%s: Repository '%s' could not be resolved or created in DB",
            gh_issue_id, payload.get("repository", {}).get("name")
        )
        return {
            "status": "error",
            "event": "issues",
            "action": action,
            "detail": f"Repository '{payload.get('repository', {}).get('name')}' not registered in platform DB."
        }

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
            status=IssueStatus.CLOSED if action == "closed" else IssueStatus.OPEN,
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
        state_reason = (issue_data.get("state_reason") or "completed").lower()
        is_closed = (action == "closed") or (issue_data.get("state") == "closed")
        if is_closed:
            from app.services.issue_service import close_or_complete_issue
            close_or_complete_issue(db=db, issue=issue, state_reason=state_reason)
        elif action in ["reopened", "opened"] or (issue_data.get("state") == "open" and issue.status == IssueStatus.CLOSED):
            from app.services.issue_service import reopen_issue
            reopen_issue(db=db, issue=issue)

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

    # Also detect issue references in PR title or body like #12, Closes #12, Fixes #12
    if not linked_issue_id:
        pr_body = pr_data.get("body") or ""
        pr_full_text = f"{pr_title} {pr_body}"
        import re
        matches = re.findall(r'(?:#|issue\s+|closes\s+|fixes\s+)(\d+)', pr_full_text, re.IGNORECASE)
        for num_str in matches:
            try:
                num = int(num_str)
                matched_iss = db.query(Issue).filter(
                    Issue.repo_id == repo_id,
                    (Issue.github_issue_id == num) | (Issue.id == num)
                ).first()
                if matched_iss:
                    pr.issue_id = matched_iss.id
                    linked_issue_id = matched_iss.id
                    break
            except Exception:
                pass

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
                    "repo_id": pr.repo_id,
                },
                read=False,
                created_at=now,
            ))
    elif action == "closed":
        if merged:
            pr.status = PRStatus.MERGED
            # Close linked issue and complete active claims
            if linked_issue_id:
                from app.services.issue_service import close_or_complete_issue
                issue = db.query(Issue).filter(Issue.id == linked_issue_id).first()
                if issue:
                    close_or_complete_issue(db=db, issue=issue, state_reason="completed")

            # Update student contribution record to MERGED and VALID
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

                # Send celebration notification
                db.add(Notification(
                    user_id=author_user.id,
                    type="pr_merged",
                    payload={
                        "title": "🎉 PR Merged!",
                        "message": f"Your PR '{pr.title}' was merged. Your contribution is validated!",
                        "pr_id": pr.id,
                        "issue_id": linked_issue_id,
                        "repo_id": pr.repo_id,
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
                "issue_id": pr.issue_id,
                "repo_id": pr.repo_id,
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
