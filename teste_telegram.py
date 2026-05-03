import requests

TOKEN = "8248812028:AAE8MW2CGtL8vYUuBW6sM2b7vi_viXchVp8"

resp = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates")
dados = resp.json()
print(dados)