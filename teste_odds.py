import requests
import config

BASE = "https://api.odds-api.io/v3"

resp = requests.get(f"{BASE}/leagues", params={
    "apiKey": config.ODDS_API_IO_KEY,
    "sport":  "football",
    "all":    "true",
}, timeout=15)

ligas = resp.json()

PAISES_ALVO = [
    "romania", "serbia", "georgia", "faroe",
    "gibraltar", "moldova", "san marino", "andorra", "kosovo"
]

print("Ligas disponíveis nos países alvo:\n")
for liga in ligas:
    nome = liga.get("name", "")
    slug = liga.get("slug", "")
    if any(p in nome.lower() for p in PAISES_ALVO):
        print(f"  {nome} | slug: {slug}")