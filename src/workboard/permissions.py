"""The single write-permission rule: you may only write to your own team's items."""

from __future__ import annotations

from fastapi import HTTPException

from workboard.users import User


def ensure_can_write(user: User, item_team: str) -> None:
    """Raise 403 unless ``user`` belongs to ``item_team``.

    Args:
        user: The authenticated caller.
        item_team: Team that owns the item being written.

    Raises:
        HTTPException: With status 403 when the teams differ.
    """
    if user.team != item_team:
        raise HTTPException(status_code=403, detail="You can only modify your own team's items")
