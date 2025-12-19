from database import Base, engine, SessionLocal
from models import User, Device, File
from passlib.context import CryptContext

Base.metadata.create_all(bind=engine)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

db = SessionLocal()

user = User(
    full_name="Иванов Иван Иванович",
    username="admin",
    role="admin",
    hashed_password=pwd_context.hash("pass"),
    token="c!k<!&UDFzv)DEo?%2iqG9zzTQr@(+ITYcl)Lfs!j7ND#j(T97Wgh)N00x1MuiJF",
    old_token=None,
    token_changed_at=None
)

device = Device(
    device_id="0325a6d6c4ce407289aaffcb37fdfa85",
    description="Orange Pi в холле",
    status="active",
    user=user
)

files = [
    File(
        file_id="f50adaff2e84489797bfc5140a4cc4a6",
        description="Рекламный ролик",
        url="uploads/videos/1765163232670-315058419.mp4",
        user=user
    ),
    File(
        file_id="494b976ce33649bc8d4e86a11680d114",
        description="Информационный баннер",
        url="uploads/videos/1765263237670-315038419.mp4",
        user=user
    ),
    File(
        file_id="bb1152efbc824dc1b941203ceaacd24e",
        description="Дополнительный ролик",
        url="uploads/videos/1865167232670-315008489.mp4",
        user=user
    ),
]


db.add(user)
db.add(device)
db.add_all(files)
db.commit()
db.close()

print("База данных инициализирована")
