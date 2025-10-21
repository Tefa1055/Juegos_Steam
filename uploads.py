from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
import os, time
from auth import get_current_user

router = APIRouter()

@router.post("/image")
async def upload_image(file: UploadFile = File(...), user = Depends(get_current_user)):
    # Guardar localmente (en Render es efímero; usa S3/Cloudinary para prod)
    name = f"img_{int(time.time())}_{file.filename}"
    path = os.path.join("static", "uploads", name)
    with open(path, "wb") as f:
        f.write(await file.read())
    return {"url": f"/static/uploads/{name}"}
