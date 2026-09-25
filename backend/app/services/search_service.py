"""Business logic for Module 9: Unified Global Search across Issues, PRs, Contributors, Repos, Commits"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, cast, String

from app.models.issue import Issue
from app.models.pull_request import PullRequest
from app.models.user import User
from app.models.repository import Repository
from app.models.commit import Commit
from app.schemas.search import (
    SearchIssueResult,
    SearchPRResult,
    SearchUserResult,
    SearchRepoResult,
    SearchCommitResult,
    UnifiedSearchResponse,
)


def search_all(
    db: Session,
    query_str: str,
    entity_type: Optional[str] = "all",
    limit: int = 10,
) -> UnifiedSearchResponse:
    """
    Unified multi-entity search across issues, pull requests, contributors, repositories, and commits.
    Accepts natural text keywords or entity-specific identifiers.
    """
    clean_q = query_str.strip()
    if not clean_q:
        return UnifiedSearchResponse(
            query=query_str,
            total_results=0,
            issues=[],
            pull_requests=[],
            contributors=[],
            repositories=[],
            commits=[],
        )

    pattern = f"%{clean_q}%"
    filter_type = (entity_type or "all").lower()

    # 1. Search Issues
    issues_res: List[SearchIssueResult] = []
    if filter_type in ["all", "issues", "issue"]:
        issue_conds = [
            Issue.title.ilike(pattern),
            Issue.description.ilike(pattern),
            Issue.category.ilike(pattern),
            cast(Issue.tech_tags, String).ilike(pattern),
        ]
        if clean_q.isdigit():
            issue_conds.append(Issue.github_issue_id == int(clean_q))

        issues = (
            db.query(Issue, Repository.name.label("repo_name"))
            .outerjoin(Repository, Repository.id == Issue.repo_id)
            .filter(or_(*issue_conds))
            .order_by(Issue.created_at.desc())
            .limit(limit)
            .all()
        )

        for iss, repo_name in issues:
            diff_val = iss.difficulty.value if hasattr(iss.difficulty, "value") else str(iss.difficulty)
            status_val = iss.status.value if hasattr(iss.status, "value") else str(iss.status)
            issues_res.append(
                SearchIssueResult(
                    id=iss.id,
                    repo_id=iss.repo_id,
                    repo_name=repo_name,
                    github_issue_id=iss.github_issue_id,
                    title=iss.title,
                    difficulty=diff_val,
                    category=iss.category,
                    tech_tags=iss.tech_tags or [],
                    status=status_val,
                )
            )

    # 2. Search Pull Requests
    prs_res: List[SearchPRResult] = []
    if filter_type in ["all", "pull_requests", "prs", "pr"]:
        pr_conds = [PullRequest.title.ilike(pattern)]
        if clean_q.isdigit():
            pr_conds.append(PullRequest.github_pr_id == int(clean_q))

        prs = (
            db.query(
                PullRequest,
                Repository.name.label("repo_name"),
                User.name.label("author_name"),
                User.github_username.label("author_github")
            )
            .outerjoin(Repository, Repository.id == PullRequest.repo_id)
            .outerjoin(User, User.id == PullRequest.user_id)
            .filter(or_(*pr_conds))
            .order_by(PullRequest.created_at.desc())
            .limit(limit)
            .all()
        )

        for pr, repo_name, author_name, author_github in prs:
            status_val = pr.status.value if hasattr(pr.status, "value") else str(pr.status)
            prs_res.append(
                SearchPRResult(
                    id=pr.id,
                    repo_id=pr.repo_id,
                    repo_name=repo_name,
                    github_pr_id=pr.github_pr_id,
                    title=pr.title,
                    status=status_val,
                    author_id=pr.user_id,
                    author_name=author_name,
                    author_github=author_github,
                )
            )

    # 3. Search Contributors (Users)
    users_res: List[SearchUserResult] = []
    if filter_type in ["all", "contributors", "users", "user"]:
        users = (
            db.query(User)
            .filter(
                or_(
                    User.name.ilike(pattern),
                    User.github_username.ilike(pattern),
                    User.psit_roll_no.ilike(pattern),
                )
            )
            .order_by(User.created_at.desc())
            .limit(limit)
            .all()
        )

        for u in users:
            role_val = u.role.value if hasattr(u.role, "value") else str(u.role)
            avatar = f"https://github.com/{u.github_username}.png" if u.github_username else None
            users_res.append(
                SearchUserResult(
                    id=u.id,
                    name=u.name,
                    github_username=u.github_username,
                    avatar_url=avatar,
                    role=role_val,
                )
            )

    # 4. Search Repositories
    repos_res: List[SearchRepoResult] = []
    if filter_type in ["all", "repositories", "repos", "repo"]:
        repos = (
            db.query(Repository)
            .filter(
                or_(
                    Repository.name.ilike(pattern),
                    cast(Repository.platform, String).ilike(pattern),
                )
            )
            .limit(limit)
            .all()
        )

        for r in repos:
            plat_val = r.platform.value if hasattr(r.platform, "value") else str(r.platform)
            repos_res.append(
                SearchRepoResult(
                    id=r.id,
                    name=r.name,
                    github_repo_url=r.github_repo_url,
                    platform=plat_val,
                )
            )

    # 5. Search Commits
    commits_res: List[SearchCommitResult] = []
    if filter_type in ["all", "commits", "commit"]:
        commits = (
            db.query(
                Commit,
                Repository.name.label("repo_name"),
                User.name.label("author_name")
            )
            .outerjoin(Repository, Repository.id == Commit.repo_id)
            .outerjoin(User, User.id == Commit.user_id)
            .filter(
                or_(
                    Commit.message.ilike(pattern),
                    Commit.github_commit_sha.ilike(pattern),
                )
            )
            .order_by(Commit.committed_at.desc())
            .limit(limit)
            .all()
        )

        for c, repo_name, author_name in commits:
            commits_res.append(
                SearchCommitResult(
                    id=c.id,
                    repo_id=c.repo_id,
                    repo_name=repo_name,
                    github_commit_sha=c.github_commit_sha,
                    message=c.message,
                    committed_at=c.committed_at,
                    author_name=author_name,
                )
            )

    total_matches = len(issues_res) + len(prs_res) + len(users_res) + len(repos_res) + len(commits_res)

    return UnifiedSearchResponse(
        query=clean_q,
        total_results=total_matches,
        issues=issues_res,
        pull_requests=prs_res,
        contributors=users_res,
        repositories=repos_res,
        commits=commits_res,
    )
