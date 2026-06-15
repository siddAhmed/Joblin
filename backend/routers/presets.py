import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import set_setting
from backend.database import get_session
from backend.dependencies.auth import CurrentUser

router = APIRouter(prefix="/presets", tags=["presets"])
Session = Annotated[AsyncSession, Depends(get_session)]

PRESETS_DIR = Path(__file__).parent.parent.parent / "presets"


@router.get("")
async def list_presets(current_user: CurrentUser):
    presets = []
    for path in sorted(PRESETS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        presets.append({"name": path.stem, "group": data.get("group", ""), "label": data.get("label", ""), "description": data.get("description", ""), "criteria": data.get("criteria", {})})
    return presets


@router.post("/{name}/apply")
async def apply_preset(name: str, session: Session, current_user: CurrentUser):
    path = PRESETS_DIR / f"{name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Preset '{name}' not found")
    data = json.loads(path.read_text())
    criteria = data.get("criteria")
    if not criteria:
        raise HTTPException(status_code=400, detail="Preset has no criteria field")
    await set_setting(session, "criteria", criteria, user_id=current_user.id)
    return {"applied": name}
