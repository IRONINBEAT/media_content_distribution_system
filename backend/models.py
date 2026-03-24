from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
    DateTime,
    Boolean,
    Text,
)
from sqlalchemy.orm import relationship

from database import Base
from datetime import datetime


class DeviceFileSettings(Base):
    __tablename__ = "device_file_settings"

    device_id = Column(Integer, ForeignKey("devices.id"), primary_key=True)
    file_id = Column(Integer, ForeignKey("files.id"), primary_key=True)
    duration_seconds = Column(Integer, nullable=True)
    pdf_page_durations_json = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)

    device = relationship("Device", back_populates="device_file_settings")
    file = relationship("File", back_populates="device_file_settings")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    full_name = Column(String)
    username = Column(String, unique=True)
    hashed_password = Column(String)
    token = Column(String, unique=True)

    # admin, operator, video_uploader
    role = Column(String, default="video_uploader")
    old_token = Column(String, nullable=True)
    token_changed_at = Column(DateTime, nullable=True)
    heartbeat_timeout = Column(Integer, default=60)

    devices = relationship("Device", back_populates="user")
    files = relationship("File", back_populates="user")


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True)
    device_id = Column(String, unique=True)
    status = Column(String)  # "unverified" / "active" / "blocked"
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="devices")
    token_synced = Column(Boolean, default=True)
    last_heartbeat = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    device_file_settings = relationship(
        "DeviceFileSettings",
        back_populates="device",
        cascade="all, delete-orphan"
    )
    files = relationship(
        "File",
        secondary="device_file_settings",
        viewonly=True,
    )


class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True)
    file_id = Column(String, unique=True)
    url = Column(String)
    description = Column(String)
    # "video" | "image" | "pdf"
    file_type = Column(String, default="video")
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="files")

    device_file_settings = relationship(
        "DeviceFileSettings",
        back_populates="file",
        cascade="all, delete-orphan"
    )
    devices = relationship(
        "Device",
        secondary="device_file_settings",
        viewonly=True,
    )