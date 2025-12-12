from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    full_name = Column(String)
    username = Column(String, unique=True)
    token = Column(String, unique=True)

    devices = relationship("Device", back_populates="user")
    files = relationship("File", back_populates="user")


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True)
    description = Column(String)
    status = Column(String)  # unverified / active / blocked

    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="devices")


class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True)
    description = Column(String)
    filename = Column(String)

    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="files")