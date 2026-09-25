"""FastAPI Router for Module 9: Unified Global Search"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.search import UnifiedSearchResponse
from app.services import search_service

router = APIRouter(tags=["Search"])


@router.get(
    "/search",
    response_model=UnifiedSearchResponse,
    summary="Unified multi-entity global search",
    description="Search across issues, pull requests, contributors, repositories, and commits with full-text query matching."
)
def global_search(
    q: str = Query(..., min_length=1, description="Search query string"),
    category: Optional[str] = Query(
        "all",
        description="Filter results by category: 'all', 'issues', 'pull_requests', 'contributors', 'repositories', 'commits'"
    ),
    limit: int = Query(10, ge=1, le=50, description="Max results per entity type"),
    db: Session = Depends(get_db),
):
    return search_service.search_all(
        db=db,
        query_str=q,
        entity_type=category,
        limit=limit,
    )
