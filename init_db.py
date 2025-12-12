from database import Base, engine, SessionLocal
from models import User, Device, File

Base.metadata.create_all(bind=engine)

db = SessionLocal()

user = User(
    full_name="Иванов Иван Иванович",
    username="admin",
    token="ADMIN_TOKEN"
)

device = Device(
    description="Orange Pi в холле",
    status="active",
    user=user
)

files = [
    File(description="Рекламный ролик", filename="video_001.mp4", user=user),
    File(description="Информационный баннер", filename="video_003.mp4", user=user)
]

db.add(user)
db.add(device)
db.add_all(files)
db.commit()
db.close()

print("База данных инициализирована")