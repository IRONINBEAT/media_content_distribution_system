import os
import shutil
import uuid
from typing import List

from fastapi import (
    Depends,
    FastAPI,
    File as FastAPIFile,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Device, File, User
from web_routes import router as web_router

UPLOAD_DIR = "uploads/videos"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="Media-Content Distribution System API")

app.include_router(web_router, include_in_schema=False)

app.mount("/static", StaticFiles(directory="static"), name="static")

# ============== Schemas ==============


class NewDeviceRequest(BaseModel):
    token: str
    id: str  # уникальный ID устройства
    description: str


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
        "message": (
            "Добро пожаловать в API системы распространения "
            "мультимедийного контента!"
        )
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
    # 1. Ищем файл в БД по file_id
    file = db.query(File).filter(File.file_id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    # 2. Удаляем файл с диска
    file_path = file.url
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete file from disk: {exc}",
            ) from exc

    # 3. Удаляем запись из БД
    db.delete(file)
    db.commit()

    return {"result": "deleted", "file_id": file.file_id}


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
    Добавление устройства в личный кабинет
    """
    # Проверяем пользователя по токену
    user = db.query(User).filter(User.token == data.token).first()
    if not user:
        return {"success": False, "message": "Invalid token"}

    # Проверяем наличие устройства с таким ID в кабинете
    existing_device = (
        db.query(Device)
        .filter(Device.device_id == data.id, Device.user_id == user.id)
        .first()
    )

    if existing_device:
        return {
            "success": False,
            "message": "такой deviceID уже существует",
        }

    # Добавляем новое устройство со статусом "unverified"
    new_device = Device(
        device_id=data.id,
        description=data.description,
        status="unverified",
        user_id=user.id,
    )
    db.add(new_device)
    db.commit()

    return {"success": True, "message": "Запрос на добавление отправлен"}


@app.post("/check-videos")
def check_videos(data: CheckVideosRequest, db: Session = Depends(get_db)):
    """
    Проверка актуальности списка видео на устройстве
    """
    # Проверяем пользователя по токену
    user = db.query(User).filter(User.token == data.token).first()
    if not user:
        return {"success": False, "message": "Invalid token"}

    # Проверяем наличие и статус устройства
    device = (
        db.query(Device)
        .filter(Device.device_id == data.id, Device.user_id == user.id)
        .first()
    )

    if not device:
        return {"success": False, "message": "Неизвестное устройство"}

    if device.status != "active":
        return {
            "success": False,
            "message": "Устройство не активировано или заблокировано",
        }

    # Получаем список видео пользователя
    server_files = db.query(File).filter(File.user_id == user.id).all()
    server_file_ids = {file.file_id for file in server_files}
    client_file_ids = set(data.videos)

    # Сравниваем списки
    if server_file_ids == client_file_ids:
        return {
            "success": True,
            "actual": True,
            "message": "Список актуален",
        }

    # Формируем актуальный список видео
    videos_response = [
        {"id": file.file_id, "url": file.url} for file in server_files
    ]

    return {
        "success": True,
        "actual": False,
        "message": "Список не актуален",
        "videos": videos_response,
    }


@app.get("/download/{file_id}")
def download_file(
    file_id: str,
    token: str,
    id: str,
    db: Session = Depends(get_db),
):
    """
    Скачивание медиафайла устройством
    """

    # 1. Проверяем пользователя
    user = db.query(User).filter(User.token == token).first()
    if not user:
        raise HTTPException(status_code=403, detail="Invalid token")

    # 2. Проверяем устройство
    device = (
        db.query(Device)
        .filter(Device.device_id == id, Device.user_id == user.id)
        .first()
    )

    if not device:
        raise HTTPException(status_code=403, detail="Unknown device")

    if device.status != "active":
        raise HTTPException(status_code=403, detail="Device not active")

    # 3. Проверяем файл
    file = (
        db.query(File)
        .filter(File.file_id == file_id, File.user_id == user.id)
        .first()
    )

    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    # 4. Проверяем существование файла на диске
    file_path = file.url
    if not os.path.exists(file_path):
        raise HTTPException(status_code=500, detail="File missing on server")

    # 5. Отдаём файл
    return FileResponse(
        path=file_path,
        media_type="application/octet-stream",
        filename=os.path.basename(file_path),
    )
