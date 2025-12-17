import os
import shutil
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Request, Form, UploadFile, File as FastAPIFile, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models import User, Device, File

# Создаем роутер вместо app
router = APIRouter()

templates = Jinja2Templates(directory="templates")
UPLOAD_DIR = "uploads/videos" # Дублируем или выносим в config.py

# --- Вспомогательная функция для Auth ---
def get_current_web_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("user_token")
    if not token:
        return None
    user = db.query(User).filter(User.token == token).first()
    return user

# --- Маршруты ---

@router.get("/web/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/web/login")
def login_submit(request: Request, token: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.token == token).first()
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Неверный токен"})
    
    response = RedirectResponse(url="/web/dashboard", status_code=303)
    response.set_cookie(key="user_token", value=token)
    return response

@router.get("/web/logout")
def logout():
    response = RedirectResponse(url="/web/login")
    response.delete_cookie("user_token")
    return response

@router.get("/web/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request, 
    user: User = Depends(get_current_web_user), 
    db: Session = Depends(get_db)
):
    if not user:
        return RedirectResponse(url="/web/login")
    
    devices = db.query(Device).filter(Device.user_id == user.id).all()
    files = db.query(File).filter(File.user_id == user.id).all()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "devices": devices,
        "files": files
    })

@router.post("/web/device/action")
def device_action(
    device_id: int = Form(...),
    action: str = Form(...),
    user: User = Depends(get_current_web_user),
    db: Session = Depends(get_db)
):
    if not user:
        return RedirectResponse(url="/web/login", status_code=303)
    
    device = db.query(Device).filter(Device.id == device_id, Device.user_id == user.id).first()
    if device:
        if action == "activate":
            device.status = "active"
        elif action == "block":
            device.status = "blocked"
        elif action == "delete":
            db.delete(device)
        db.commit()
    
    return RedirectResponse(url="/web/dashboard", status_code=303)

@router.post("/web/file/upload")
def web_upload_file(
    description: str = Form(...),
    file: UploadFile = FastAPIFile(...),
    user: User = Depends(get_current_web_user),
    db: Session = Depends(get_db)
):
    if not user:
        return RedirectResponse(url="/web/login", status_code=303)
    
    file_id = uuid.uuid4().hex
    filename = f"{file_id}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    db_file = File(
        file_id=file_id,
        url=file_path,
        description=description,
        user_id=user.id,
    )
    db.add(db_file)
    db.commit()
    
    return RedirectResponse(url="/web/dashboard", status_code=303)

@router.post("/web/file/delete")
def web_delete_file(
    file_id: str = Form(...),
    user: User = Depends(get_current_web_user),
    db: Session = Depends(get_db)
):
    if not user:
        return RedirectResponse(url="/web/login", status_code=303)
    
    file = db.query(File).filter(File.file_id == file_id, File.user_id == user.id).first()
    if file:
        if file.url and os.path.exists(file.url):
            try:
                os.remove(file.url)
            except:
                pass
        db.delete(file)
        db.commit()

    return RedirectResponse(url="/web/dashboard", status_code=303)

@router.get("/web/stream/{file_id}")
def stream_video(
    file_id: str,
    user: User = Depends(get_current_web_user),
    db: Session = Depends(get_db)
):
    if not user:
        raise HTTPException(status_code=403, detail="Not authenticated")

    file = db.query(File).filter(File.file_id == file_id, File.user_id == user.id).first()
    
    if not file or not os.path.exists(file.url):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=file.url,
        media_type="video/mp4",
        filename=os.path.basename(file.url)
    )