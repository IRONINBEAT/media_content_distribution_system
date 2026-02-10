import os
import shutil
import uuid
from typing import List, Optional
from datetime import datetime
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
from pydantic import BaseModel, Field
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
    token: str = Field(
        ...,
        description="Персональный токен пользователя",
    )
    id: str = Field(
        ...,
        description="Уникальный аппаратный ID регистрируемого устройства",
    )
    description: str = Field(
        ...,
        description="Краткое описание (например, 'Экран в холле')",
    )


class NewDeviceResponse(BaseModel):
    success: bool = Field(..., description="Флаг успешности операции")
    message: str = Field(
        ...,
        description="Информационное сообщение или описание ошибки",
    )


class HeartbeatRequest(BaseModel):
    token: str
    id: str


class CheckVideosRequest(BaseModel):
    token: str = Field(..., description="Актуальный токен доступа")
    id: str = Field(..., description="ID устройства, выполняющего проверку")
    videos: List[str] = Field(
        ...,
        description=(
            "Список ID файлов, которые уже скачаны на устройство"
        ),
    )


class VideoItem(BaseModel):
    id: str = Field(..., description="Уникальный ID файла в системе")
    url: str = Field(..., description="Путь для скачивания файла")


class CheckVideosResponse(BaseModel):
    answer: bool   # Меняем success на answer
    status: int    # Добавляем поле статуса (204, 205 и т.д.)
    message: str
    videos: Optional[List[dict]] = None


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


class TokenSyncRequest(BaseModel):
    token: str = Field(
        ...,
        description=(
            "Токен, который сейчас сохранен на устройстве "
            "(мог стать устаревшим)"
        ),
    )
    id: str = Field(..., description="ID устройства")


class TokenSyncResponse(BaseModel):
    success: bool = Field(
        ...,
        description="Удалось ли сопоставить устройство и токен",
    )
    status: str | None = Field(
        None,
        description=(
            "Статус: 'actual' (токен верный) или 'updated' "
            "(выдан новый токен)"
        ),
    )
    new_token: str | None = Field(
        None,
        description=(
            "Новый токен (передается только при смене ключа "
            "в течение 5-минутного окна)"
        ),
    )
    message: str | None = Field(
        None,
        description="Описание причины отказа",
    )


# ============== Admin Endpoints ==============


@app.get("/", include_in_schema=False)
def greetings():
    return {
        "message": (
            "Добро пожаловать в API системы распространения "
            "мультимедийного контента!"
        )
    }


@app.get("/api/admin/users", include_in_schema=False)
def get_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return users


@app.get("/api/admin/users/{user_id}", include_in_schema=False)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.post("/api/admin/users", include_in_schema=False)
def create_user(data: UserCreate, db: Session = Depends(get_db)):
    user = User(**data.dict())
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.delete("/api/admin/users/{user_id}", include_in_schema=False)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"status": "deleted"}


@app.get("/api/admin/devices", include_in_schema=False)
def get_devices(db: Session = Depends(get_db)):
    return db.query(Device).all()


@app.get(
    "/api/admin/users/{user_id}/devices",
    include_in_schema=False,
)
def get_user_devices(user_id: int, db: Session = Depends(get_db)):
    return db.query(Device).filter(Device.user_id == user_id).all()


@app.post("/api/admin/devices", include_in_schema=False)
def create_device(data: DeviceCreate, db: Session = Depends(get_db)):
    device = Device(**data.dict())
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


@app.delete("/api/admin/devices/{device_id}", include_in_schema=False)
def delete_device(device_id: int, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    db.delete(device)
    db.commit()
    return {"status": "deleted"}


@app.get("/api/admin/files", include_in_schema=False)
def get_files(db: Session = Depends(get_db)):
    return db.query(File).all()


@app.get(
    "/api/admin/users/{user_id}/files",
    include_in_schema=False,
)
def get_user_files(user_id: int, db: Session = Depends(get_db)):
    return db.query(File).filter(File.user_id == user_id).all()


@app.post("/api/admin/files", include_in_schema=False)
def create_file(data: FileCreate, db: Session = Depends(get_db)):
    file_obj = File(**data.dict())
    db.add(file_obj)
    db.commit()
    db.refresh(file_obj)
    return file_obj


@app.delete("/api/admin/files/{file_id}", include_in_schema=False)
def delete_file(file_id: str, db: Session = Depends(get_db)):
    file_obj = db.query(File).filter(File.file_id == file_id).first()
    if not file_obj:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = file_obj.url
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete file from disk: {exc}",
            ) from exc

    db.delete(file_obj)
    db.commit()

    return {"result": "deleted", "file_id": file_obj.file_id}


@app.post("/api/admin/files/upload", include_in_schema=False)
def upload_file(
    user_id: int = Form(...),
    description: str = Form(""),
    file: UploadFile = FastAPIFile(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

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
    db.refresh(db_file)

    return {"result": "uploaded", "file_id": file_id, "path": file_path}


# ============== Public Endpoints (V3) ==============


@app.post(
    "/api/sync-token",
    response_model=TokenSyncResponse,
    summary="Синхронизация токена",
    tags=["Auth"],
)
def sync_token(data: TokenSyncRequest, db: Session = Depends(get_db)):
    # 1. Сначала проверяем, является ли токен АКТУАЛЬНЫМ (п.1)
    current_user = db.query(User).filter(User.token == data.token).first()

    if current_user:
        # Токен верный. Проверяем, привязано ли
        # устройство к этому пользователю (п.2)
        device = db.query(Device).filter(
            Device.device_id == data.id,
            Device.user_id == current_user.id
        ).first()

        if not device:
            return {
                "success": False,
                "message": "Неизвестное устройство для данного токена"
            }

        # Устройство найдено, токен актуален
        return {
            "success": True,
            "status": "actual",
            "message": "Токен актуален"
        }

    # 2. Если токен не актуален, проверяем, является ли он СТАРЫМ (п.3 и п.4)
    old_user = db.query(User).filter(User.old_token == data.token).first()

    if old_user:
        # Токен найден как старый. Проверяем устройство.
        device = db.query(Device).filter(
            Device.device_id == data.id,
            Device.user_id == old_user.id
        ).first()

        if not device:
            return {
                "success": False,
                "message": "Для данного токена неизвестное устройство"
            }

        # Устройство найдено. Проверяем, был ли уже использован
        # этот старый токен (п.3 vs п.4)
        if not device.token_synced:
            # Это ПЕРВЫЙ запрос на синхронизацию с этим старым токеном.
            # Обновляем статус устройства и выдаем новый токен.
            device.token_synced = True
            db.commit()

            return {
                "success": True,
                "status": "updated",
                "new_token": old_user.token,
                "message": "Токен обновлен"
            }
        else:
            # Запрос НЕ первый. Устройство уже получило новый токен ранее.
            return {
                "success": False,
                "message": "Текущий токен недействителен (уже был обновлен)"
            }

    # 3. Токен не найден ни как текущий, ни как старый
    return {
        "success": False,
        "message": "Неверный токен"
    }


@app.post(
    "/api/newdevice",
    response_model=NewDeviceResponse,
    summary="Регистрация нового устройства",
    tags=["Devices"],
)
def add_device(data: NewDeviceRequest, db: Session = Depends(get_db)):
    """
    Первичная регистрация устройства в системе.

    Устройство отправляет свой уникальный ID и токен владельца.
    После вызова устройство появится в админ-панели со статусом
    'unverified' (ожидает подтверждения администратором).
    """
    user = db.query(User).filter(User.token == data.token).first()
    if not user:
        return {"success": False, "message": "Invalid token"}

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

    new_device = Device(
        device_id=data.id,
        description=data.description,
        status="unverified",
        user_id=user.id,
    )
    db.add(new_device)
    db.commit()

    return {"success": True, "message": "Запрос на добавление отправлен"}


@app.post("/api/heartbeat",
          summary="Приветствие устройства ",
          tags=["Devices"])
def heartbeat(data: HeartbeatRequest, db: Session = Depends(get_db)):
    # 1. Проверка токена
    user = db.query(User).filter(User.token == data.token).first()
    if not user:
        return None

    # 2. Поиск устройства
    device = db.query(Device).filter(Device.device_id == data.id,
                                     Device.user_id == user.id).first()

    if not device:
        # Устройство отсутствует — добавляем как новое
        new_device = Device(
            device_id=data.id,
            description="Новое устройство",
            status="unverified",  # Статус "Новое"
            user_id=user.id,
            last_heartbeat=datetime.now()
        )
        db.add(new_device)
        db.commit()
        return {"answer": True, "status": 401, "message": "Unauthorized"}

    # Обновляем время активности
    device.last_heartbeat = datetime.now()
    db.commit()

    # 3. Проверка статусов
    if device.status == "blocked":
        return {"answer": True, "status": 403, "message": "Forbidden"}

    if device.status == "active":  # Соответствует "200 OK"
        return {"answer": True, "status": 200, "message": "OK"}

    return {"answer": True, "status": 401, "message": "Unauthorized"}


@app.post(
    "/api/check-videos",
    response_model=CheckVideosResponse,
    summary="Проверка актуальности контента",
    tags=["Content"],
)
def check_videos(data: CheckVideosRequest, db: Session = Depends(get_db)):
    """
    Синхронизация плейлиста.

    Устройство передает список ID файлов, которые у него есть.
    Если списки совпадают, actual=True.
    Если есть различия, actual=False и полный актуальный список
    ссылок в поле videos.
    """
    user = db.query(User).filter(User.token == data.token).first()
    if not user:
        return {"success": False, "message": "Invalid token"}

    device = (
        db.query(Device)
        .filter(Device.device_id == data.id, Device.user_id == user.id)
        .first()
    )

    if not device or device.status == "unverified":
        return {"answer": True, "status": 401, "message": "Unauthorized"}
    if device.status == "blocked":
        return {"answer": True, "status": 403, "message": "Forbidden"}

    # Если статус active (200 OK), проверяем контент
    server_files = device.files

    server_file_ids = [f.file_id for f in server_files]

    # Сравниваем списки
    if set(server_file_ids) == set(data.videos):
        return {"answer": True, "status": 204, "message": "No Content"}
    else:
        videos_data = [
            {"id": f.file_id, "url": f"{f.url}"}
            for f in server_files
        ]
        return {
            "answer": True,
            "status": 205,
            "message": "Reset Content",
            "videos": videos_data
        }


@app.get(
    "/api/download/{file_id}",
    summary="Скачивание файла",
    tags=["Content"],
)
def download_file(
    file_id: str,
    token: str,
    id: str,  # noqa: A002
    db: Session = Depends(get_db),
):
    """
    Загрузка медиафайла.

    Возвращает бинарный поток файла (application/octet-stream).
    Требует передачи ID файла, токена и ID устройства.
    """
    user = db.query(User).filter(User.token == token).first()
    if not user:
        raise HTTPException(status_code=403, detail="Invalid token")

    device = (
        db.query(Device)
        .filter(Device.device_id == id, Device.user_id == user.id)
        .first()
    )

    if not device:
        raise HTTPException(status_code=403, detail="Unknown device")

    if device.status != "active":
        raise HTTPException(status_code=403, detail="Device not active")

    file_obj = (
        db.query(File)
        .filter(File.file_id == file_id, File.user_id == user.id)
        .first()
    )

    if not file_obj:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = file_obj.url
    if not os.path.exists(file_path):
        raise HTTPException(status_code=500, detail="File missing on server")

    return FileResponse(
        path=file_path,
        media_type="application/octet-stream",
        filename=os.path.basename(file_path),
    )
