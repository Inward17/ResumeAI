from fastapi import APIRouter, Depends

from app.auth import AuthUser, get_current_user, upsert_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def get_me(user: AuthUser = Depends(get_current_user)):
    """Return (and record) the signed-in user. The frontend calls this after login."""
    return await upsert_user(user)
