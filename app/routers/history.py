from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_user
from app.models.user import User
from app.routers import render
from app.services.history_service import HistoryService

router = APIRouter()


@router.get("/history")
def view_history(
    request: Request,
    page: int = 1,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    # ADR-006: 本人分のみ。ADR-013: 降順・20件ページング。
    history = HistoryService(db).list_history(current_user.id, page=max(page, 1))
    return render(request, "history.html", current_user, history=history)
