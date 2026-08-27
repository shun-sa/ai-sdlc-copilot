from fastapi import APIRouter, Depends, Request

from app.dependencies import get_current_user
from app.models.user import User
from app.routers import render

router = APIRouter()


@router.get("/")
def index(request: Request, current_user: User | None = Depends(get_current_user)):
    return render(request, "index.html", current_user)
