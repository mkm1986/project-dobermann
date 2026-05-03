import requests
import config

BASE = "https://api.odds-api.io/v3"

LIGAS_ALVO = [
    "norway", "sweden", "denmark", "finland",
    "iceland", "ireland", "estonia",
    "czech", "slovakia"
]

for bookmaker in ["Betano BR", "Bet365"]:
    resp = requests.get(f"{BASE}/value-bets", params={
        "apiKey":              config.ODDS_API_IO_KEY,
        "bookmaker":           bookmaker,
        "includeEventDetails": "true",
        "sport":               "football",
    }, timeout=15)

    dados = resp.json()
    if not isinstance(dados, list):
        print(f"{bookmaker}: Erro — {dados}")
        continue

    sinais = []
    for bet in dados:
        evento = bet.get("event", {})
        liga   = evento.get("league", "").lower()
        if any(p in liga for p in LIGAS_ALVO):
            ev = (bet.get("expectedValue", 0) / 100) - 1
            sinais.append({
                "jogo": f"{evento.get('home')} x {evento.get('away')}",
                "liga": evento.get("league"),
                "ev":   ev,
                "odd":  bet.get("bookmakerOdds", {}).get(bet.get("betSide"), 0)
            })

    print(f"\n{'='*50}")
    print(f"{bookmaker}: {len(sinais)} sinais nas ligas alvo")
    for s in sinais[:5]:
        print(f"  {s['jogo']}")
        print(f"  Liga: {s['liga']} | Odd: {s['odd']} | EV: {s['ev']:.2%}")