from database import Base, engine, SessionLocal
from models import User, Device, File
from passlib.context import CryptContext

# Создаем таблицы (если они еще не созданы)
Base.metadata.create_all(bind=engine)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

db = SessionLocal()

# 1. Создаем пользователя
user = User(
    full_name="Иванов Иван Иванович",
    username="admin",
    role="admin",
    hashed_password=pwd_context.hash("pass"),
    token="c!k<!&UDFzv)DEo?%2iqG9zzTQr@(+ITYcl)Lfs!j7ND#j(T97Wgh)N00x1MuiJF",
    old_token=None,
    token_changed_at=None
)

# 2. Создаем устройство
device = Device(
    device_id="NSTU_OrangePI2302",
    status="active",
    user=user
)

# 3. Создаем файлы с начальными настройками длительности
# Для видео meta_info содержит общую длину, duration_config — сколько проигрывать.
# Для фото meta_info пустой, duration_config — время показа.
files = [
    File(
        file_id="f50adaff2e84489797bfc5140a4cc4a6",
        description="Рекламный ролик (Видео)",
        url="uploads/media/video1.mp4",
        file_type="video",
        # Настройки длительности
        meta_info={"total_duration": 30.0}, 
        duration_config={"duration": 30.0},
        user=user
    ),
    File(
        file_id="494b976ce33649bc8d4e86a11680d114",
        description="Информационный баннер (Фото)",
        url="uploads/media/banner.jpg",
        file_type="image",
        # Для фото мета-информация не критична, ставим дефолт 5 сек
        meta_info={},
        duration_config={"duration": 5.0},
        user=user
    ),
    File(
        file_id="bb1152efbc824dc1b941203ceaacd24e",
        description="Презентация PDF",
        url="uploads/media/doc.pdf",
        file_type="pdf",
        # Для PDF указываем количество страниц и тайминг для каждой
        meta_info={"page_count": 3},
        duration_config={"pages": [10.0, 15.0, 10.0]},
        user=user
    ),
]

# Добавляем всё в сессию
db.add(user)
db.add(device)
db.add_all(files)

# Привязываем файлы к устройству (чтобы они сразу отображались в плейлисте)
device.files = files

db.commit()
db.close()

print("База данных успешно инициализирована.")