import requests
import time
from datetime import datetime

def send_heartbeat():
    url = "http://217.71.129.139:6012/api/heartbeat"
    payload = {
        "token": "c!k<!&UDFzv)DEo?%2iqG9zzTQr@(+ITYcl)Lfs!j7ND#j(T97Wgh)N00x1MuiJF",
        "id": "newDeviceOnLadder"
    }

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Запуск воркера...")

    while True:
        try:
            # Отправляем POST запрос
            response = requests.post(url, json=payload, timeout=10)
            
            # Проверяем статус ответа
            if response.status_code == 200:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Heartbeat отправлен успешно: {response.json()}")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Ошибка сервера: {response.status_code}")
        
        except requests.exceptions.RequestException as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Ошибка сети: {e}")

        # Ждем 55 секунд
        time.sleep(55)

if __name__ == "__main__":
    send_heartbeat()