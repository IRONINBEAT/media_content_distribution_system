import os
import shutil
import uuid
import secrets
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
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models import Device, File, User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter()

templates = Jinja2Templates(directory="templates")
UPLOAD_DIR = "uploads/videos"


def get_current_web_user(request: Request, db: Session = Depends(get_db)):
    """Получение текущего пользователя по cookie."""
    token = request.cookies.get("user_token")
    if not token:
        return None
    user = db.query(User).filter(User.token == token).first()
    return user


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
            {"request": request, "error": "Неверный логин или пароль", "user": None},
        )

    response = RedirectResponse(url="/web/dashboard", status_code=303)
    response.set_cookie(key="user_token", value=user.token) # Используем токен как сессию
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

    devices = db.query(Device).filter(Device.user_id == user.id).all()
    files = db.query(File).filter(File.user_id == user.id).all()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "devices": devices,
            "files": files,
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
def stream_video(
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

    return FileResponse(
        path=file.url,
        media_type="video/mp4",
        filename=os.path.basename(file.url),
    )


@router.post("/web/user/refresh-token")
def refresh_user_token(user: User = Depends(get_current_web_user), db: Session = Depends(get_db)):
    if not user:
        return RedirectResponse(url="/web/login", status_code=303)

    # 1. Сохраняем старый токен
    user.old_token = user.token
    # 2. Генерируем новый
    new_token = secrets.token_urlsafe(48)
    user.token = new_token
    user.token_changed_at = datetime.utcnow()

    # 3. Сбрасываем флаг синхронизации для ВСЕХ устройств пользователя
    db.query(Device).filter(Device.user_id == user.id).update({"token_synced": False})

    db.commit()

    response = RedirectResponse(url="/web/dashboard", status_code=303)
    response.set_cookie(key="user_token", value=new_token)
    return response

# Вспомогательная функция для проверки прав
def require_role(user: User, allowed_roles: list):
    if not user or user.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Доступ запрещен: недостаточно прав")

# 1. Страница списка пользователей (только для admin)
@router.get("/web/admin/users", response_class=HTMLResponse)
def admin_users_page(request: Request, user: User = Depends(get_current_web_user), db: Session = Depends(get_db)):
    if not user: return RedirectResponse(url="/web/login", status_code=303)
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
    password: str = Form(...), # Новый пароль
    role: str = Form(...),
    user: User = Depends(get_current_web_user),
    db: Session = Depends(get_db)
):
    require_role(user, ["admin"])
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
    if target_user and target_user.id != user.id: # Нельзя удалить самого себя
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