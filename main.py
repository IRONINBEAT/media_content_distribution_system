from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List

from database import SessionLocal
from models import User, Device, File

from pydantic import BaseModel

app = FastAPI(title="Media-Content Distribution System API")

# --------------------
# Dependency
# --------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --------------------
# Schemas
# --------------------

class VerifyRequest(BaseModel):
    token: str      # токен пользователя
    device_id: int 

class ContentCheckRequest(BaseModel):
    device_id: int
    files: List[str]

class UserCreate(BaseModel):
    full_name: str
    username: str
    token: str

class DeviceCreate(BaseModel):
    description: str
    status: str
    user_id: int

class DeviceStatusUpdate(BaseModel):
    status: str

class FileCreate(BaseModel):
    description: str
    filename: str
    user_id: int

class DeviceRegisterRequest(BaseModel):
    token: str                 
    description: str           

# --------------------
# Endpoints
# --------------------

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


@app.patch("/api/admin/devices/{device_id}")
def update_device_status(
    device_id: int,
    data: DeviceStatusUpdate,
    db: Session = Depends(get_db)
):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    old_status = device.status

    if old_status == data.status:
        return {
            "status": "unsuccessful",
            "message": "Device status was not changed"
        }

    device.status = data.status
    db.commit()

    return {
        "status": "successful",
        "old_status": old_status,
        "new_status": data.status
    }


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



@app.post("/api/device/verify")
def verify_device(data: VerifyRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.token == data.token).first()
    if not user:
        raise HTTPException(status_code=403, detail="Invalid user token")

    device = (
        db.query(Device)
        .filter(
            Device.id == data.device_id,
            Device.user_id == user.id
        )
        .first()
    )

    if not device:
        raise HTTPException(
            status_code=403,
            detail="Device does not belong to this user"
        )

    if device.status != "active":
        raise HTTPException(
            status_code=403,
            detail="Device blocked or inactive"
        )

    return {
        "status": "ok",
        "device_id": device.id
    }


@app.post("/api/content/check")
def check_content(data: ContentCheckRequest, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == data.device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    server_files = {f.filename for f in device.user.files}
    client_files = set(data.files)

    return {
        "actual": server_files == client_files,
        "to_download": list(server_files - client_files),
        "to_delete": list(client_files - server_files)
    }

@app.post("/api/device/register")
def register_device(
    data: DeviceRegisterRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.token == data.token).first()
    if not user:
        raise HTTPException(
            status_code=403,
            detail="Invalid user token"
        )

    device = Device(
        description=data.description,
        status="active",
        user_id=user.id
    )

    db.add(device)
    db.commit()
    db.refresh(device)

    return {
        "result": "registered",
        "device_id": device.id,
        "device_status": device.status,
        "user_id": user.id
    }