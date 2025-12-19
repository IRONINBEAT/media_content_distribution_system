from sqlalchemy import Column, ForeignKey, Integer, String, DateTime
from sqlalchemy.orm import relationship

from database import Base


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

    devices = relationship("Device", back_populates="user")
    files = relationship("File", back_populates="user")


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True)
    device_id = Column(String, unique=True)
    description = Column(String)
    status = Column(String)  # "unverified" / "active" / "blocked"
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="devices")


class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True)
    file_id = Column(String, unique=True)
    url = Column(String)
    description = Column(String)
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="files")
