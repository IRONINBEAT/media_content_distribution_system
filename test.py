import requests

url = "http://127.0.0.1:8000/download/34eb390f068840f9b402c2079857f28d"
params = {
    "token": "c!k<!&UDFzv)DEo?%2iqG9zzTQr@(+ITYcl)Lfs!j7ND#j(T97Wgh)N00x1MuiJF",
    "id": "NewDeviceID"
}

response = requests.get(url, params=params, stream=True)

if response.status_code == 200:
    with open("IMG_тестовый.mp4", "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
