import requests
import config

BASE = "https://api.odds-api.io/v3"

BOOKMAKERS = ["Betano BR", "Bet365"]

LIGAS_ALVO = [
    "norway", "sweden", "denmark", "finland",
    "iceland", "ireland", "estonia",
    "czech", "slovakia", "latvia", "lithuania",
]

LIGAS_EXCLUIR = [
    "u19", "u18", "u17", "u16", "u15",
    "u-19", "u-18", "u-17",
    "under 19", "under 18", "under 17",
    "under-19", "under-18", "under-17",
    "youth", "juvenil",
]

LIGAS_OBSCURAS_NOMES = [
    "cup", "copa", "pokal", "karis", "ykkonen", "esiliiga",
    "2nd division", "3rd division", "2. liga", "3. liga",
    "1. deild", "fnl", "superettan", "divize", "danmarksserien",
    "1. division", "1st division"
]

LIGAS_PRINCIPAIS_NOMES = [
    "eliteserien", "allsvenskan", "superliga", "veikkausliiga",
    "premier division", "besta deild", "meistriliiga",
    "czech liga", "premiership"
]

def get_max_odd(liga):
    if any(p in liga.lower() for p in LIGAS_OBSCURAS_NOMES):
        return config.MAX_ODD_OBSCURO
    return config.MAX_ODD_PRINCIPAL

def get_min_odd(liga):
    if any(p in liga.lower() for p in LIGAS_PRINCIPAIS_NOMES):
        return config.MIN_ODD_PRINCIPAL
    return config.MIN_ODD_OBSCURO

def buscar_value_bets(min_ev=None):
    if min_ev is None:
        min_ev = config.MIN_EDGE_PRINCIPAL

    todos_sinais = []

    for bookmaker in BOOKMAKERS:
        try:
            resp = requests.get(f"{BASE}/value-bets", params={
                "apiKey":              config.ODDS_API_IO_KEY,
                "bookmaker":           bookmaker,
                "includeEventDetails": "true",
                "sport":               "football",
            }, timeout=15)

            if resp.status_code != 200:
                print(f"⚠️ Erro {bookmaker} ({resp.status_code}): {resp.text}")
                continue

            dados = resp.json()
            if not isinstance(dados, list):
                print(f"⚠️ Resposta inesperada {bookmaker}: {dados}")
                continue

            for bet in dados:
                ev_raw = bet.get("expectedValue", 0)
                ev = (ev_raw / 100) - 1

                if ev < min_ev or ev > config.MAX_EV:
                    continue

                evento = bet.get("event", {})
                liga = evento.get("league", "")
                sport = evento.get("sport", "").lower()

                if sport != "football":
                    continue
                if not any(pais in liga.lower() for pais in LIGAS_ALVO):
                    continue
                if any(ex in liga.lower() for ex in LIGAS_EXCLUIR):
                    continue

                bet_side = bet.get("betSide")
                market = bet.get("market", {})
                odds_bm = bet.get("bookmakerOdds", {})
                odd = float(odds_bm.get(bet_side, 0) or 0)

                if odd < get_min_odd(liga) or odd > get_max_odd(liga):
                    continue

                todos_sinais.append({
                    "event_id":  bet.get("eventId"),
                    "home":      evento.get("home"),
                    "away":      evento.get("away"),
                    "liga":      liga,
                    "data":      evento.get("date"),
                    "bet_side":  bet_side,
                    "odd":       odd,
                    "ev_api":    ev,
                    "market":    market.get("name"),
                    "href":      odds_bm.get("href", ""),
                    "bookmaker": bookmaker,
                })

        except Exception as e:
            print(f"⚠️ Erro ao buscar {bookmaker}: {e}")
            continue

    vistos = {}
    for s in todos_sinais:
        chave = f"{s['event_id']}-{s['bet_side']}"
        if chave not in vistos or s["odd"] > vistos[chave]["odd"]:
            vistos[chave] = s

    return list(vistos.values())

def buscar_resultado(event_id):
    """
    Tenta buscar resultado em duas fontes:
    1. /events/{id} — evento ainda disponível
    2. /historical/odds — fallback para eventos expirados
    """
    # Tentativa 1: evento ainda na API
    try:
        resp = requests.get(f"{BASE}/events/{event_id}", params={
            "apiKey": config.ODDS_API_IO_KEY,
        }, timeout=15)

        if resp.status_code == 200:
            dados = resp.json()
            status = dados.get("status", "")
            if status in ("finished", "completed", "settled"):
                scores = dados.get("scores", {})
                fulltime = scores.get("periods", {}).get("fulltime", {})
                if fulltime:
                    gc = fulltime.get("home")
                    gf = fulltime.get("away")
                else:
                    gc = scores.get("home")
                    gf = scores.get("away")
                if gc is not None and gf is not None:
                    return int(gc), int(gf)

    except Exception as e:
        print(f"⚠️ Erro /events: {e}")

# Tentativa 2: historical/odds como fallback
    try:
        resp2 = requests.get(f"{BASE}/historical/odds", params={
            "apiKey":     config.ODDS_API_IO_KEY,
            "eventId":    str(event_id),
            "bookmakers": "Bet365",
        }, timeout=15)

        if resp2.status_code == 200:
            dados2 = resp2.json()
            scores = dados2.get("scores", {})
            if scores:
                fulltime = scores.get("periods", {}).get("fulltime", {})
                if fulltime:
                    gc = fulltime.get("home")
                    gf = fulltime.get("away")
                else:
                    gc = scores.get("home")
                    gf = scores.get("away")
                if gc is not None and gf is not None:
                    return int(gc), int(gf)

    except Exception as e:
        print(f"⚠️ Erro /historical/odds: {e}")

    # Retorna None — o liquidar.py decide se é expirado baseado na data
    return None