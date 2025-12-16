from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
from database import SessionLocal
from models import User, Device, File
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Media-Content Distribution System API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
def delete_file(file_id: int, db: Session = Depends(get_db)):
    file = db.query(File).filter(File.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    db.delete(file)
    db.commit()
    return {"status": "deleted"}

# ============== Public Endpoints (V3) ==============

@app.post("/newdevice")
def add_device(data: NewDeviceRequest, db: Session = Depends(get_db)):
    """
    Добавление устройства в личный кабинет
    """
    # Проверяем пользователя по токену
    user = db.query(User).filter(User.token == data.token).first()
    if not user:
        return {
            "success": False,
            "message": "Invalid token"
        }
    
    # Проверяем наличие устройства с таким ID в кабинете
    existing_device = db.query(Device).filter(
        Device.device_id == data.id,
        Device.user_id == user.id
    ).first()
    
    if existing_device:
        return {
            "success": False,
            "message": f"deviceID уже существует"
        }
    
    # Добавляем новое устройство со статусом "unverified"
    new_device = Device(
        device_id=data.id,
        description="",
        status="unverified",
        user_id=user.id
    )
    db.add(new_device)
    db.commit()
    
    return {
        "success": True,
        "message": "Запрос на добавление отправлен"
    }

@app.post("/check-videos")
def check_videos(data: CheckVideosRequest, db: Session = Depends(get_db)):
    """
    Проверка актуальности списка видео на устройстве
    """
    # Проверяем пользователя по токену
    user = db.query(User).filter(User.token == data.token).first()
    if not user:
        return {
            "success": False,
            "message": "Invalid token"
        }
    
    # Проверяем наличие и статус устройства
    device = db.query(Device).filter(
        Device.device_id == data.id,
        Device.user_id == user.id
    ).first()
    
    if not device:
        return {
            "success": False,
            "message": "Неизвестное устройство"
        }
    
    if device.status != "active":
        return {
            "success": False,
            "message": "Устройство не активно"
        }
    
    # Получаем список видео пользователя
    server_files = db.query(File).filter(File.user_id == user.id).all()
    server_file_ids = {f.file_id for f in server_files}
    client_file_ids = set(data.videos)
    
    # Сравниваем списки
    if server_file_ids == client_file_ids:
        return {
            "success": True,
            "actual": True,
            "message": "Список актуален"
        }
    
    # Формируем актуальный список видео
    videos_response = [
        {"id": f.file_id, "url": f.url}
        for f in server_files
    ]
    
    return {
        "success": True,
        "actual": False,
        "message": "Список не актуален",
        "videos": videos_response
    }