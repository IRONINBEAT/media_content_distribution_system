import os
import shutil
import uuid
import zlib
import time
import secrets
import json
import re
from typing import List
from datetime import datetime
from passlib.context import CryptContext

from fastapi import (
    APIRouter,
    Depends,
    File as FastAPIFile,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import get_db
from models import Device, DeviceFileSettings, File, User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter()

templates = Jinja2Templates(directory="templates")
UPLOAD_DIR = "uploads/media"

ALLOWED_EXTENSIONS = {
    "mp4": ("video", "video/mp4"),
    "png": ("image", "image/png"),
    "jpg": ("image", "image/jpeg"),
    "jpeg": ("image", "image/jpeg"),
    "pdf": ("pdf", "application/pdf"),
}


def get_file_meta(filename: str):
    """Возвращает (file_type, mime_type) по расширению файла."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Недопустимый тип файла. Разрешены: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    return ALLOWED_EXTENSIONS[ext]


def parse_pdf_page_durations(raw_value: str):
    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        return []
    return []


def get_default_duration(file_obj: File):
    if file_obj.file_type == "image":
        return 5
    return None


def estimate_pdf_page_count(file_path: str):
    """
    Lightweight PDF page count without external dependencies.
    """
    if not os.path.exists(file_path):
        return 1
    try:
        with open(file_path, "rb") as pdf_file:
            content = pdf_file.read()

        # Heuristic 1: explicit /Count in /Pages tree nodes.
        text = content.decode("latin-1", errors="ignore")
        count_matches = re.findall(r"/Count\s+(\d+)", text)
        count_from_tree = max((int(value) for value in count_matches), default=0)

        # Heuristic 2: number of page objects. Avoid matching /Type /Pages.
        page_objects = len(re.findall(r"/Type\s*/Page(?!s)\b", text))

        estimated = max(count_from_tree, page_objects, 1)
        return estimated
    except OSError:
        return 1


# ============== Helpful Functions ==============


# Вспомогательная функция для проверки прав
def require_role(user: User, allowed_roles: list):
    if not user or user.role not in allowed_roles:
        raise HTTPException(status_code=403,
                            detail="Доступ запрещен: недостаточно прав")


def generate_crc32_filename(original_name: str) -> str:
    timestamp = str(time.time()).encode('utf-8')
    crc = zlib.crc32(timestamp) & 0xffffffff
    ext = original_name.split('.')[-1] if '.' in original_name else 'mp4'
    return f"{format(crc, 'X')}.{ext}"


def get_current_web_user(request: Request, db: Session = Depends(get_db)):
    """Получение текущего пользователя по cookie."""
    token = request.cookies.get("user_token")
    if not token:
        return None
    user = db.query(User).filter(User.token == token).first()
    return user


# ============== Public Endpoints ==============


@router.get("/web/login", response_class=HTMLResponse)
def login_page(request: Request):
    # Добавляем user=None в словарь контекста
    return templates.TemplateResponse("login.html", {
        "request": request,
        "user": None
    })


@router.post("/web/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == username).first()

    if not user or not pwd_context.verify(password, user.hashed_password):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Неверный логин или пароль",
             "user": None},
        )

    response = RedirectResponse(url="/web/dashboard", status_code=303)
    response.set_cookie(key="user_token", value=user.token)
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
    db: Session = Depends(get_db),
):
    if not user:
        return RedirectResponse(url="/web/login")

    devices = (
        db.query(Device)
        .filter(Device.user_id == user.id)
        .order_by(desc(Device.created_at))
        .all()
    )
    files = db.query(File).filter(File.user_id == user.id).all()
    device_file_settings_map = {}
    settings_rows = (
        db.query(DeviceFileSettings)
        .join(Device, Device.id == DeviceFileSettings.device_id)
        .join(File, File.id == DeviceFileSettings.file_id)
        .filter(Device.user_id == user.id, File.user_id == user.id)
        .all()
    )
    for row in settings_rows:
        key = f"{row.device_id}:{row.file_id}"
        device_file_settings_map[key] = {
            "duration_seconds": row.duration_seconds,
            "pdf_page_durations": parse_pdf_page_durations(row.pdf_page_durations_json),
        }

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "devices": devices,
            "files": files,
            "device_file_settings_map": device_file_settings_map,
            "now": datetime.now()
        },
    )


@router.post("/web/device/action")
def device_action(
    device_id: int = Form(...),
    action: str = Form(...),
    user: User = Depends(get_current_web_user),
    db: Session = Depends(get_db),
):
    if not user:
        return RedirectResponse(url="/web/login", status_code=303)
    require_role(user, ["admin", "operator"])
    device = (
        db.query(Device)
        .filter(Device.id == device_id, Device.user_id == user.id)
        .first()
    )
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
    db: Session = Depends(get_db),
):
    if not user:
        return RedirectResponse(url="/web/login", status_code=303)
    require_role(user, ["admin", "operator", "video_uploader"])

    file_type, _ = get_file_meta(file.filename)
    file_id = uuid.uuid4().hex
    new_filename = generate_crc32_filename(file.filename)
    file_path = os.path.join(UPLOAD_DIR, new_filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    db_file = File(
        file_id=file_id,
        url=file_path,
        description=description,
        file_type=file_type,
        user_id=user.id,
    )
    db.add(db_file)
    db.commit()

    return RedirectResponse(url="/web/dashboard", status_code=303)


@router.post("/web/file/delete")
def web_delete_file(
    file_id: str = Form(...),
    user: User = Depends(get_current_web_user),
    db: Session = Depends(get_db),
):
    if not user:
        return RedirectResponse(url="/web/login", status_code=303)
    require_role(user, ["admin", "operator", "video_uploader"])
    file = (
        db.query(File)
        .filter(File.file_id == file_id, File.user_id == user.id)
        .first()
    )
    if file:
        if file.url and os.path.exists(file.url):
            try:
                os.remove(file.url)
            except OSError:
                pass
        db.delete(file)
        db.commit()

    return RedirectResponse(url="/web/dashboard", status_code=303)


@router.get("/web/stream/{file_id}")
def serve_file(
    file_id: str,
    user: User = Depends(get_current_web_user),
    db: Session = Depends(get_db),
):
    if not user:
        raise HTTPException(status_code=403, detail="Not authenticated")

    file = (
        db.query(File)
        .filter(File.file_id == file_id, File.user_id == user.id)
        .first()
    )

    if not file or not os.path.exists(file.url):
        raise HTTPException(status_code=404, detail="File not found")

    ext = file.url.rsplit(".", 1)[-1].lower() if "." in file.url else ""
    _, mime_type = ALLOWED_EXTENSIONS.get(ext, ("video", "video/mp4"))

    return FileResponse(
        path=file.url,
        media_type=mime_type,
        filename=os.path.basename(file.url),
    )


@router.post("/web/user/refresh-token")
def refresh_user_token(user: User = Depends(get_current_web_user),
                       db: Session = Depends(get_db)):
    if not user:
        return RedirectResponse(url="/web/login", status_code=303)

    # 1. Сохраняем старый токен
    user.old_token = user.token
    # 2. Генерируем новый
    new_token = secrets.token_urlsafe(48)
    user.token = new_token
    user.token_changed_at = datetime.utcnow()

    # 3. Сбрасываем флаг синхронизации для ВСЕХ устройств пользователя
    db.query(Device).filter(Device.user_id == user.id).update({
        "token_synced": False
        })

    db.commit()

    response = RedirectResponse(url="/web/dashboard", status_code=303)
    response.set_cookie(key="user_token", value=new_token)
    return response


@router.post("/web/user/update-timeout")
def update_timeout(
    request: Request,
    timeout: int = Form(...),
    db: Session = Depends(get_db)
):
    user = get_current_web_user(request, db)
    if user:
        user.heartbeat_timeout = timeout
        db.commit()
    return RedirectResponse(url="/web/dashboard", status_code=303)


# 1. Страница списка пользователей (только для admin)
@router.get("/web/admin/users", response_class=HTMLResponse)
def admin_users_page(request: Request,
                     user: User = Depends(get_current_web_user),
                     db: Session = Depends(get_db)):

    if not user:
        return RedirectResponse(url="/web/login", status_code=303)
    require_role(user, ["admin"])

    users = db.query(User).all()
    return templates.TemplateResponse("admin_users.html", {
        "request": request,
        "user": user,
        "all_users": users
    })


# 2. Создание пользователя
@router.post("/web/admin/user/create")
def admin_create_user(
    full_name: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),  # Новый пароль
    role: str = Form(...),
    user: User = Depends(get_current_web_user),
    db: Session = Depends(get_db)
):
    require_role(user, ["admin"])

    if len(password) < 6:
        raise HTTPException(status_code=400,
                            detail="Пароль должен быть не менее 6 символов")

    new_user = User(
        full_name=full_name,
        username=username,
        role=role,
        hashed_password=pwd_context.hash(password),
        token=secrets.token_urlsafe(32)
    )
    db.add(new_user)
    db.commit()
    return RedirectResponse(url="/web/admin/users", status_code=303)


# 3. Удаление пользователя
@router.post("/web/admin/user/delete")
def admin_delete_user(
    user_id: int = Form(...),
    user: User = Depends(get_current_web_user),
    db: Session = Depends(get_db)
):
    require_role(user, ["admin"])
    target_user = db.query(User).filter(User.id == user_id).first()
    if target_user and target_user.id != user.id:  # Нельзя удалить самого себя
        db.delete(target_user)
        db.commit()
    return RedirectResponse(url="/web/admin/users", status_code=303)


@router.post("/web/admin/user/edit")
def admin_edit_user(
    user_id: int = Form(...),
    password: str = Form(None),
    full_name: str = Form(...),
    username: str = Form(...),
    role: str = Form(...),
    user: User = Depends(get_current_web_user),
    db: Session = Depends(get_db)
):
    require_role(user, ["admin"])

    target_user = db.query(User).filter(User.id == user_id).first()
    if password:
        target_user.hashed_password = pwd_context.hash(password)
    if not target_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    target_user.full_name = full_name
    target_user.username = username
    target_user.role = role

    db.commit()
    return RedirectResponse(url="/web/admin/users", status_code=303)


@router.post("/web/device/update-playlist")
def update_device_playlist(
    device_id: int = Form(...),
    # FastAPI принимает список значений
    # с одним именем ключа из формы (checkbox)
    selected_files: List[int] = Form([]),
    user: User = Depends(get_current_web_user),
    db: Session = Depends(get_db),
):
    if not user:
        return RedirectResponse(url="/web/login", status_code=303)

    # 1. Ищем устройство
    device = db.query(Device).filter(Device.id == device_id,
                                     Device.user_id == user.id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Устройство не найдено")

    files_to_assign = db.query(File).filter(
        File.id.in_(selected_files),
        File.user_id == user.id
    ).all()

    selected_file_ids = {file_obj.id for file_obj in files_to_assign}
    existing_settings = (
        db.query(DeviceFileSettings)
        .filter(DeviceFileSettings.device_id == device.id)
        .all()
    )
    for setting_row in existing_settings:
        if setting_row.file_id not in selected_file_ids:
            db.delete(setting_row)

    existing_by_file_id = {row.file_id: row for row in existing_settings}
    for index, file_obj in enumerate(files_to_assign):
        if file_obj.id in existing_by_file_id:
            existing_by_file_id[file_obj.id].sort_order = index
            continue
        db.add(
            DeviceFileSettings(
                device_id=device.id,
                file_id=file_obj.id,
                duration_seconds=get_default_duration(file_obj),
                sort_order=index,
            )
        )

    db.commit()

    return RedirectResponse(url="/web/dashboard", status_code=303)


@router.post("/web/file/update-devices")
def update_file_devices(
    file_id: int = Form(...),
    # Список ID устройств из чекбоксов
    selected_devices: List[int] = Form([]),
    user: User = Depends(get_current_web_user),
    db: Session = Depends(get_db),
):
    if not user:
        return RedirectResponse(url="/web/login", status_code=303)

    # 1. Ищем файл
    file_obj = db.query(File).filter(File.id == file_id, File.user_id == user.id).first()
    if not file_obj:
        raise HTTPException(status_code=404, detail="Файл не найден")

    devices_to_assign = db.query(Device).filter(
        Device.id.in_(selected_devices),
        Device.user_id == user.id
    ).all()

    selected_device_ids = {device.id for device in devices_to_assign}
    existing_settings = (
        db.query(DeviceFileSettings)
        .filter(DeviceFileSettings.file_id == file_obj.id)
        .all()
    )
    for setting_row in existing_settings:
        if setting_row.device_id not in selected_device_ids:
            db.delete(setting_row)

    existing_by_device_id = {row.device_id: row for row in existing_settings}
    for device in devices_to_assign:
        if device.id in existing_by_device_id:
            continue
        db.add(
            DeviceFileSettings(
                device_id=device.id,
                file_id=file_obj.id,
                duration_seconds=get_default_duration(file_obj),
            )
        )
    db.commit()

    return RedirectResponse(url="/web/dashboard", status_code=303)


@router.get("/web/device/file-settings/{device_id}/{file_id}")
def get_device_file_settings(
    device_id: int,
    file_id: int,
    user: User = Depends(get_current_web_user),
    db: Session = Depends(get_db),
):
    if not user:
        raise HTTPException(status_code=403, detail="Not authenticated")

    device = db.query(Device).filter(Device.id == device_id, Device.user_id == user.id).first()
    file_obj = db.query(File).filter(File.id == file_id, File.user_id == user.id).first()
    if not device or not file_obj:
        raise HTTPException(status_code=404, detail="Устройство или файл не найден")

    setting_row = db.query(DeviceFileSettings).filter(
        DeviceFileSettings.device_id == device.id,
        DeviceFileSettings.file_id == file_obj.id,
    ).first()

    if not setting_row:
        setting_row = DeviceFileSettings(
            device_id=device.id,
            file_id=file_obj.id,
            duration_seconds=get_default_duration(file_obj),
            pdf_page_durations_json=None,
        )
        db.add(setting_row)
        db.commit()

    payload = {
        "device_id": device.id,
        "file_id": file_obj.id,
        "file_type": file_obj.file_type,
        "duration_seconds": setting_row.duration_seconds,
        "pdf_page_durations": parse_pdf_page_durations(setting_row.pdf_page_durations_json),
        "stream_url": f"/web/stream/{file_obj.file_id}",
    }
    return JSONResponse(payload)


@router.get("/web/file/{file_id}/pdf-preview")
def get_pdf_preview_config(
    file_id: int,
    user: User = Depends(get_current_web_user),
    db: Session = Depends(get_db),
):
    if not user:
        raise HTTPException(status_code=403, detail="Not authenticated")

    file_obj = db.query(File).filter(File.id == file_id, File.user_id == user.id).first()
    if not file_obj:
        raise HTTPException(status_code=404, detail="Файл не найден")
    if file_obj.file_type != "pdf":
        raise HTTPException(status_code=400, detail="Preview доступен только для PDF")

    return JSONResponse({
        "file_id": file_obj.id,
        "page_count": estimate_pdf_page_count(file_obj.url),
    })


@router.post("/web/device/file-settings")
def update_device_file_settings(
    device_id: int = Form(...),
    file_id: int = Form(...),
    duration_seconds: int = Form(None),
    pdf_page_durations_json: str = Form(None),
    user: User = Depends(get_current_web_user),
    db: Session = Depends(get_db),
):
    if not user:
        return RedirectResponse(url="/web/login", status_code=303)

    device = db.query(Device).filter(Device.id == device_id, Device.user_id == user.id).first()
    file_obj = db.query(File).filter(File.id == file_id, File.user_id == user.id).first()
    if not device or not file_obj:
        raise HTTPException(status_code=404, detail="Устройство или файл не найден")

    if duration_seconds is not None and duration_seconds <= 0:
        raise HTTPException(status_code=400, detail="Длительность должна быть больше 0")

    parsed_pdf_durations = parse_pdf_page_durations(pdf_page_durations_json)
    if file_obj.file_type == "pdf" and parsed_pdf_durations:
        for item in parsed_pdf_durations:
            if not isinstance(item, dict):
                raise HTTPException(status_code=400, detail="Некорректный формат PDF страниц")
            page_number = item.get("page")
            page_duration = item.get("duration")
            if not isinstance(page_number, int) or page_number < 1:
                raise HTTPException(status_code=400, detail="Некорректный номер страницы")
            if not isinstance(page_duration, int) or page_duration <= 0:
                raise HTTPException(status_code=400, detail="Некорректная длительность страницы")

    setting_row = db.query(DeviceFileSettings).filter(
        DeviceFileSettings.device_id == device.id,
        DeviceFileSettings.file_id == file_obj.id,
    ).first()
    if not setting_row:
        setting_row = DeviceFileSettings(
            device_id=device.id,
            file_id=file_obj.id,
            sort_order=0,
        )
        db.add(setting_row)

    if file_obj.file_type == "pdf":
        setting_row.duration_seconds = None
        setting_row.pdf_page_durations_json = json.dumps(parsed_pdf_durations) if parsed_pdf_durations else None
    else:
        if duration_seconds is None:
            duration_seconds = get_default_duration(file_obj)
        setting_row.duration_seconds = duration_seconds
        setting_row.pdf_page_durations_json = None

    db.commit()
    return RedirectResponse(url="/web/dashboard", status_code=303)