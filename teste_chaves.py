import requests
import config

print("=" * 45)
print("VERIFICANDO CHAVES DE API")
print("=" * 45)

# Teste 1: The Odds API
print("\n1. The Odds API...")
resp = requests.get(
    "https://api.the-odds-api.com/v4/sports",
    params={"apiKey": config.ODDS_API_KEY}
)
if resp.status_code == 200:
    print("   ✅ Chave válida!")
    print(f"   Requisições restantes: {resp.headers.get('x-requests-remaining', 'N/A')}")
else:
    print(f"   ❌ Erro {resp.status_code}: {resp.text}")

# Teste 2: odds-api.io
print("\n2. odds-api.io...")
resp = requests.get(
    "https://api.odds-api.io/v3/sports",
    params={"apiKey": config.ODDS_API_IO_KEY}
)
if resp.status_code == 200:
    print("   ✅ Chave válida!")
    sports = resp.json()
    print(f"   Esportes disponíveis: {len(sports)}")
else:
    print(f"   ❌ Erro {resp.status_code}: {resp.text}")

print("\n" + "=" * 45)