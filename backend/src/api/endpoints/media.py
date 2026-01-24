from fastapi import APIRouter, File, HTTPException, Request, UploadFile
import requests

from src.core.config import settings

router = APIRouter(prefix="/media", tags=["media"])


@router.post("/upload")
def upload_media(request: Request, file: UploadFile = File(...)):
    storage_url = settings.MEDIA_STORAGE_URL.rstrip("/")
    if not file:
        raise HTTPException(status_code=400, detail="Missing file")

    try:
        file.file.seek(0)
        response = requests.post(
            f"{storage_url}/upload",
            files={
                "file": (
                    file.filename or "upload",
                    file.file,
                    file.content_type or "application/octet-stream",
                )
            },
            cookies=request.cookies,
            timeout=15,
        )
    except requests.RequestException:
        raise HTTPException(status_code=503, detail="Media storage unavailable")

    if not response.ok:
        detail = "Upload failed"
        try:
            payload = response.json()
            detail = payload.get("detail", detail)
        except ValueError:
            if response.text:
                detail = response.text
        raise HTTPException(status_code=response.status_code, detail=detail)

    try:
        return response.json()
    except ValueError:
        raise HTTPException(status_code=502, detail="Invalid storage response")
