"""Pydantic schemas for Module 9: Unified Global Search"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class SearchIssueResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    repo_id: int
    repo_name: Optional[str] = None
    github_issue_id: int
    title: str
    difficulty: str
    category: Optional[str] = None
    tech_tags: List[str] = []
    status: str


class SearchPRResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    repo_id: int
    repo_name: Optional[str] = None
    github_pr_id: int
    title: str
    status: str
    author_id: Optional[int] = None
    author_name: Optional[str] = None
    author_github: Optional[str] = None


class SearchUserResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    github_username: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str


class SearchRepoResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    github_repo_url: str
    platform: str


class SearchCommitResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    repo_id: int
    repo_name: Optional[str] = None
    github_commit_sha: str
    message: str
    committed_at: datetime
    author_name: Optional[str] = None


class UnifiedSearchResponse(BaseModel):
    query: str
    total_results: int
    issues: List[SearchIssueResult] = []
    pull_requests: List[SearchPRResult] = []
    contributors: List[SearchUserResult] = []
    repositories: List[SearchRepoResult] = []
    commits: List[SearchCommitResult] = []
