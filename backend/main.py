from fastapi import FastAPI, HTTPException, Depends
from fastapi import UploadFile, File as FastAPIFile, Form
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security.utils import get_authorization_scheme_param
import typing
from sqlalchemy.orm import Session
from typing import List
from database import SessionLocal
from models import User, Device, File
from pydantic import BaseModel
import uuid
import shutil
import os

UPLOAD_DIR = "uploads/videos"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="Media-Content Distribution System API")


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============== Schemas ==============


class NewDeviceRequest(BaseModel):
    token: str
    id: str  # уникальный ID устройства


class CheckVideosRequest(BaseModel):
    token: str
    id: str
    videos: List[str]


class VideoResponse(BaseModel):
    id: str
    url: str


class UserCreate(BaseModel):
    full_name: str
    username: str
    token: str


class DeviceCreate(BaseModel):
    device_id: str
    description: str
    user_id: int


class FileCreate(BaseModel):
    file_id: str
    url: str
    description: str
    user_id: int


# ============== Admin Endpoints ==============


@app.get("/")
def greetings():
    return {
        "message": "Добро пожаловать в API системы распространения мультимедийного контента!"
    }


@app.get("/api/admin/users")
def get_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return users


@app.get("/api/admin/users/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.post("/api/admin/users")
def create_user(data: UserCreate, db: Session = Depends(get_db)):
    user = User(**data.dict())
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.delete("/api/admin/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"status": "deleted"}


@app.get("/api/admin/devices")
def get_devices(db: Session = Depends(get_db)):
    return db.query(Device).all()


@app.get("/api/admin/users/{user_id}/devices")
def get_user_devices(user_id: int, db: Session = Depends(get_db)):
    return db.query(Device).filter(Device.user_id == user_id).all()


@app.post("/api/admin/devices")
def create_device(data: DeviceCreate, db: Session = Depends(get_db)):
    device = Device(**data.dict())
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


@app.delete("/api/admin/devices/{device_id}")
def delete_device(device_id: int, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    db.delete(device)
    db.commit()
    return {"status": "deleted"}


@app.get("/api/admin/files")
def get_files(db: Session = Depends(get_db)):
    return db.query(File).all()


@app.get("/api/admin/users/{user_id}/files")
def get_user_files(user_id: int, db: Session = Depends(get_db)):
    return db.query(File).filter(File.user_id == user_id).all()


@app.post("/api/admin/files")
def create_file(data: FileCreate, db: Session = Depends(get_db)):
    file = File(**data.dict())
    db.add(file)
    db.commit()
    db.refresh(file)
    return file


@app.delete("/api/admin/files/{file_id}")
def delete_file(file_id: str, db: Session = Depends(get_db)):
    # 1. Ищем файл в БД по file_id
    file = db.query(File).filter(File.file_id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    # 2. Удаляем файл с диска
    file_path = file.url
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete file from disk: {str(e)}"
            )

    # 3. Удаляем запись из БД
    db.delete(file)
    db.commit()

    return {
        "result": "deleted",
        "file_id": file.file_id
    }


@app.post("/api/admin/files/upload")
def upload_file(
    user_id: int = Form(...),
    description: str = Form(""),
    file: UploadFile = FastAPIFile(...),
    db: Session = Depends(get_db),
):
    # 1. Проверяем пользователя
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 2. Генерируем ID и путь
    file_id = uuid.uuid4().hex
    filename = f"{file_id}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    # 3. Сохраняем файл на диск
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 4. Записываем в БД
    db_file = File(
        file_id=file_id,
        url=file_path,
        description=description,
        user_id=user.id,
    )

    db.add(db_file)
    db.commit()
    db.refresh(db_file)

    return {"result": "uploaded", "file_id": file_id, "path": file_path}


# ============== Public Endpoints (V3) ==============


@app.post("/newdevice")
def add_device(data: NewDeviceRequest, db: Session = Depends(get_db)):
    """
    Добавление устройства в личный кабинет
    """
    # Проверяем пользователя по токену
    user = db.query(User).filter(User.token == data.token).first()
    if not user:
        return {"success": False, "message": "Invalid token"}

    # Проверяем наличие устройства с таким ID в кабинете
    existing_device = (
        db.query(Device)
        .filter(Device.device_id == data.id, Device.user_id == user.id)
        .first()
    )

    if existing_device:
        return {"success": False, "message": f"deviceID уже существует"}

    # Добавляем новое устройство со статусом "unverified"
    new_device = Device(
        device_id=data.id, description="", status="unverified", user_id=user.id
    )
    db.add(new_device)
    db.commit()

    return {"success": True, "message": "Запрос на добавление отправлен"}


@app.post("/check-videos")
def check_videos(data: CheckVideosRequest, db: Session = Depends(get_db)):
    """
    Проверка актуальности списка видео на устройстве
    """
    # Проверяем пользователя по токену
    user = db.query(User).filter(User.token == data.token).first()
    if not user:
        return {"success": False, "message": "Invalid token"}

    # Проверяем наличие и статус устройства
    device = (
        db.query(Device)
        .filter(Device.device_id == data.id, Device.user_id == user.id)
        .first()
    )

    if not device:
        return {"success": False, "message": "Неизвестное устройство"}

    if device.status != "active":
        return {"success": False, "message": "Устройство не активно"}

    # Получаем список видео пользователя
    server_files = db.query(File).filter(File.user_id == user.id).all()
    server_file_ids = {f.file_id for f in server_files}
    client_file_ids = set(data.videos)

    # Сравниваем списки
    if server_file_ids == client_file_ids:
        return {"success": True, "actual": True, "message": "Список актуален"}

    # Формируем актуальный список видео
    videos_response = [{"id": f.file_id, "url": f.url} for f in server_files]

    return {
        "success": True,
        "actual": False,
        "message": "Список не актуален",
        "videos": videos_response,
    }


@app.get("/download/{file_id}")
def download_file(
    file_id: str, token: str, id: str, db: Session = Depends(get_db)
):
    """
    Скачивание медиафайла устройством
    """

    # 1. Проверяем пользователя
    user = db.query(User).filter(User.token == token).first()
    if not user:
        raise HTTPException(status_code=403, detail="Invalid token")

    # 2. Проверяем устройство
    device = (
        db.query(Device)
        .filter(Device.device_id == id, Device.user_id == user.id)
        .first()
    )

    if not device:
        raise HTTPException(status_code=403, detail="Unknown device")

    if device.status != "active":
        raise HTTPException(status_code=403, detail="Device not active")

    # 3. Проверяем файл
    file = (
        db.query(File)
        .filter(File.file_id == file_id, File.user_id == user.id)
        .first()
    )

    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    # 4. Проверяем существование файла на диске
    file_path = file.url
    if not os.path.exists(file_path):
        raise HTTPException(status_code=500, detail="File missing on server")

    # 5. Отдаём файл
    return FileResponse(
        path=file_path,
        media_type="application/octet-stream",
        filename=os.path.basename(file_path),
    )


# ============== WEB UI LOGIC ==============

templates = Jinja2Templates(directory="templates")

@app.get("/web/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/web/login")
def login_submit(request: Request, token: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.token == token).first()
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Неверный токен"})
    
    response = RedirectResponse(url="/web/dashboard", status_code=303)
    response.set_cookie(key="user_token", value=token)
    return response

@app.get("/web/logout")
def logout():
    response = RedirectResponse(url="/web/login")
    response.delete_cookie("user_token")
    return response

# Зависимость для получения текущего пользователя из Cookie
def get_current_web_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("user_token")
    if not token:
        return None
    user = db.query(User).filter(User.token == token).first()
    return user

@app.get("/web/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request, 
    user: User = Depends(get_current_web_user), 
    db: Session = Depends(get_db)
):
    if not user:
        return RedirectResponse(url="/web/login")
    
    # Загружаем данные только для ЭТОГО пользователя
    devices = db.query(Device).filter(Device.user_id == user.id).all()
    files = db.query(File).filter(File.user_id == user.id).all()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "devices": devices,
        "files": files
    })

@app.post("/web/device/action")
def device_action(
    request: Request,
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

@app.post("/web/file/delete")
def web_delete_file(
    file_id: str = Form(...),
    user: User = Depends(get_current_web_user),
    db: Session = Depends(get_db)
):
    if not user:
        return RedirectResponse(url="/web/login", status_code=303)

    # Используем уже существующую логику удаления, но адаптируем под Web
    # Прямой вызов логики из delete_file_endpoint был бы сложен из-за Depends, 
    # поэтому дублируем логику очистки (или выносим в сервисный слой в идеале)
    
    file = db.query(File).filter(File.file_id == file_id, File.user_id == user.id).first()
    if file:
        if file.url and os.path.exists(file.url):
            try:
                os.remove(file.url)
            except:
                pass # Логируем ошибку в реальном приложении
        db.delete(file)
        db.commit()

    return RedirectResponse(url="/web/dashboard", status_code=303)

@app.post("/web/file/upload")
def web_upload_file(
    description: str = Form(...),
    file: UploadFile = FastAPIFile(...),
    user: User = Depends(get_current_web_user),
    db: Session = Depends(get_db)
):
    if not user:
        return RedirectResponse(url="/web/login", status_code=303)
    
    # Логика загрузки (аналогична существующему API, но привязана к Web User)
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

@app.get("/web/stream/{file_id}")
def stream_video(
    file_id: str,
    user: User = Depends(get_current_web_user),
    db: Session = Depends(get_db)
):
    """
    Специальный эндпоинт для просмотра видео в браузере админа.
    Использует авторизацию через Cookie.
    """
    if not user:
        # Если сессия истекла, вернем 403, видео не загрузится
        raise HTTPException(status_code=403, detail="Not authenticated")

    # Ищем файл, принадлежащий этому админу
    file = db.query(File).filter(File.file_id == file_id, File.user_id == user.id).first()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    if not os.path.exists(file.url):
        raise HTTPException(status_code=404, detail="File missing on disk")

    return FileResponse(
        path=file.url,
        media_type="video/mp4",
        filename=os.path.basename(file.url)
    )