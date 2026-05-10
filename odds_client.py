import requests
import config
import time
import json
import os

# ─────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────

BASE_ODDS_API_IO  = "https://api.odds-api.io/v3"
BASE_THE_ODDS_API = "https://api.the-odds-api.com/v4"

BOOKMAKERS = ["Betfair Sportsbook", "Bet365"]

LIGAS_ALVO = [
    "norway", "sweden", "denmark", "finland", "iceland",
    "ireland", "northern ireland", "wales", "scotland",
    "estonia", "latvia", "lithuania",
    "czech", "slovakia", "belgium", "switzerland",
    "romania", "serbia", "georgia", "faroe",
    "gibraltar", "moldova", "kosovo", "andorra", "san marino",
    "usa", "canada",
    "australia - capital npl",
    "australia - northern nsw",
    "australia - northern territory",
    "australia - nsw",
    "australia - queensland",
    "australia - south australia",
    "australia - tasmania",
    "australia - victoria",
    "australia - western australia",
    "australia - australia cup",
]

LIGAS_EXCLUIR = [
    # Categorias de idade
    "u19", "u18", "u17", "u16", "u15",
    "u-19", "u-18", "u-17", "u21", "u-21",
    "under 19", "under 18", "under 17", "under 21",
    "youth", "juvenil",
    # Feminino
    "women", "feminino", "femenino",
    "kvinde", "damer", "naiset",
    "kansallinen liiga",
    "toppserien", "damallsvenskan",
    # Reservas e amadores
    "amateur", "reserves", "reservas",
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

# Ligas da The Odds API — usadas para buscar RESULTADOS (scores endpoint, gratuito)
# e também como fallback de value bets quando odds-api.io falhar.
# IMPORTANTE: os event_ids do banco são da odds-api.io e NÃO batem com os IDs
# da The Odds API. Por isso buscamos por nome de time + data, não por ID.
LIGAS_THE_ODDS_API = [
    # Nórdicas
    "soccer_norway_eliteserien",
    "soccer_norway_1st_division",
    "soccer_sweden_allsvenskan",
    "soccer_sweden_superettan",
    "soccer_denmark_superliga",
    "soccer_denmark_1st_division",
    "soccer_finland_veikkausliiga",
    "soccer_finland_ykkonen",
    "soccer_iceland_premier_division",
    # Ilhas Britânicas
    "soccer_ireland_premier_division",
    "soccer_scotland_premier_league",
    "soccer_scotland_championship",
    "soccer_scotland_league1",
    "soccer_northern_ireland_premier_league",
    "soccer_wales_premier_league",
    # Centro-Europa
    "soccer_czech_republic_fl",
    "soccer_czech_republic_fnl",
    "soccer_slovakia_superliga",
    # Bálticas
    "soccer_estonia_meistriliiga",
    # Américas
    "soccer_usa_usl_championship",
    "soccer_usa_usl_leagueone",
    "soccer_canada_premier_league",
    "soccer_canada_mls",
    # Romênia
    "soccer_romania_1",
]

# ─────────────────────────────────────────────
# CACHE (55 min — só para value bets)
# ─────────────────────────────────────────────

CACHE_FILE     = "cache_odds.json"
CACHE_VALIDADE = 55 * 60
_cache         = {}

def _carregar_cache():
    global _cache
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                dados = json.load(f)
            if time.time() - dados.get("timestamp", 0) < CACHE_VALIDADE:
                _cache = dados
                return True
        except:
            pass
    return False

def _salvar_cache(chave, valor):
    global _cache
    _cache[chave]       = valor
    _cache["timestamp"] = time.time()
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(_cache, f)
    except:
        pass

def _cache_valido(chave):
    if not _cache:
        _carregar_cache()
    ts = _cache.get("timestamp", 0)
    return chave in _cache and time.time() - ts < CACHE_VALIDADE

# ─────────────────────────────────────────────
# HELPERS DE ODDS
# ─────────────────────────────────────────────

def get_max_odd(liga):
    if any(p in liga.lower() for p in LIGAS_OBSCURAS_NOMES):
        return config.MAX_ODD_OBSCURO
    return config.MAX_ODD_PRINCIPAL

def get_min_odd(liga):
    if any(p in liga.lower() for p in LIGAS_PRINCIPAIS_NOMES):
        return config.MIN_ODD_PRINCIPAL
    return config.MIN_ODD_OBSCURO

# ─────────────────────────────────────────────
# BUSCA DE RESULTADOS — The Odds API (fonte primária)
# ─────────────────────────────────────────────
#
# POR QUE The Odds API aqui?
#   • 500 requests/mês praticamente sem uso
#   • odds-api.io é limitada a 100/hora — reservada para value bets
#   • The Odds API tem endpoint /scores gratuito — perfeito para liquidação
#
# POR QUE buscar por nome e não por event_id?
#   • Os event_ids no banco são da odds-api.io (ex: 70674924)
#   • A The Odds API usa UUIDs próprios (ex: a1b2c3d4e5f6...)
#   • São sistemas diferentes — IDs não são compatíveis
#   • Solução: match fuzzy por nome do time + data do jogo
#

def buscar_resultado_the_odds_api(home, away, data_jogo_str):
    """
    Busca placar via The Odds API — endpoint /scores.
    Faz match por nome dos times pois os event_ids não são compatíveis.
    Retorna (gols_casa, gols_fora) ou None.
    """
    home_lower = home.lower()
    away_lower = away.lower()
    data_str   = data_jogo_str[:10] if data_jogo_str else ""

    for liga_key in LIGAS_THE_ODDS_API:
        try:
            resp = requests.get(
                f"{BASE_THE_ODDS_API}/sports/{liga_key}/scores/",
                params={
                    "apiKey":   config.ODDS_API_KEY,
                    "daysFrom": 3,
                },
                timeout=15
            )

            if resp.status_code == 401:
                print(f"   ⚠️ The Odds API: chave inválida")
                return None

            if resp.status_code != 200:
                continue

            eventos = resp.json()
            if not isinstance(eventos, list) or not eventos:
                continue

            for ev in eventos:
                ev_home = ev.get("home_team", "").lower()
                ev_away = ev.get("away_team", "").lower()
                ev_data = ev.get("commence_time", "")[:10]

                # Filtra por data
                if data_str and ev_data != data_str:
                    continue

                # Match fuzzy por nome
                home_match = (home_lower in ev_home or ev_home in home_lower)
                away_match = (away_lower in ev_away or ev_away in away_lower)

                if not (home_match and away_match):
                    continue

                # Encontrou — verifica se terminou
                if not ev.get("completed", False):
                    return None

                scores = ev.get("scores")
                if not scores:
                    return None

                gc = gf = None
                for s in scores:
                    s_name = s.get("name", "").lower()
                    if s_name in ev_home or ev_home in s_name:
                        gc = s.get("score")
                    elif s_name in ev_away or ev_away in s_name:
                        gf = s.get("score")

                if gc is not None and gf is not None:
                    return int(gc), int(gf)

        except Exception as e:
            print(f"   ⚠️ Erro The Odds API scores ({liga_key}): {e}")
            continue

    return None


def buscar_resultado_odds_api_io(event_id):
    """
    Fallback: busca resultado via odds-api.io.
    Usado apenas quando The Odds API não cobre a liga.
    Consome cota — usar com parcimônia.
    """
    try:
        resp = requests.get(
            f"{BASE_ODDS_API_IO}/events/{event_id}",
            params={"apiKey": config.ODDS_API_IO_KEY},
            timeout=15
        )

        if resp.status_code == 200:
            dados  = resp.json()
            status = dados.get("status", "")

            if status in ("finished", "completed", "settled"):
                scores   = dados.get("scores", {})
                periods  = scores.get("periods", {})
                fulltime = periods.get("fulltime", {})

                if not fulltime:
                    print(f"   ⚠️ Placar parcial — aguardando fulltime")
                    return None

                gc = fulltime.get("home")
                gf = fulltime.get("away")
                if gc is not None and gf is not None:
                    return int(gc), int(gf)

            return None

    except Exception as e:
        print(f"   ⚠️ Erro odds-api.io /events: {e}")

    # Segunda tentativa: historical/odds
    try:
        resp2 = requests.get(
            f"{BASE_ODDS_API_IO}/historical/odds",
            params={
                "apiKey":     config.ODDS_API_IO_KEY,
                "eventId":    str(event_id),
                "bookmakers": "Bet365",
            },
            timeout=15
        )

        if resp2.status_code == 200:
            dados2   = resp2.json()
            scores   = dados2.get("scores", {})
            if scores:
                periods  = scores.get("periods", {})
                fulltime = periods.get("fulltime", {})

                if not fulltime:
                    return None

                gc = fulltime.get("home")
                gf = fulltime.get("away")
                if gc is not None and gf is not None:
                    return int(gc), int(gf)

    except Exception as e:
        print(f"   ⚠️ Erro odds-api.io /historical/odds: {e}")

    return None


def buscar_resultado(event_id, home=None, away=None, data_jogo_str=None):
    """
    Ponto de entrada para busca de resultado.

    Estratégia:
      1. The Odds API /scores (grátis) — busca por nome de time
      2. odds-api.io /events (fallback, consome cota) — busca por event_id
    """
    # Tentativa 1: The Odds API por nome de time (grátis)
    if home and away:
        resultado = buscar_resultado_the_odds_api(home, away, data_jogo_str or "")
        if resultado is not None:
            return resultado

    # Tentativa 2: odds-api.io por event_id (fallback)
    print(f"   🔄 The Odds API não encontrou — tentando odds-api.io...")
    return buscar_resultado_odds_api_io(event_id)


# ─────────────────────────────────────────────
# VALUE BETS — fallback via The Odds API
# ─────────────────────────────────────────────

def buscar_value_bets_fallback(min_ev=None):
    """Fallback usando The Odds API quando odds-api.io estiver indisponível."""
    if min_ev is None:
        min_ev = config.MIN_EDGE_PRINCIPAL

    sinais = []

    for liga_key in LIGAS_THE_ODDS_API:
        try:
            resp = requests.get(
                f"{BASE_THE_ODDS_API}/sports/{liga_key}/odds/",
                params={
                    "apiKey":     config.ODDS_API_KEY,
                    "regions":    "eu",
                    "markets":    "h2h",
                    "bookmakers": "pinnacle,betano,bet365",
                },
                timeout=15
            )

            if resp.status_code != 200:
                continue

            jogos = resp.json()

            for jogo in jogos:
                home     = jogo.get("home_team")
                away     = jogo.get("away_team")
                data     = jogo.get("commence_time")
                event_id = jogo.get("id")

                odd_pinnacle = {"home": 0, "away": 0, "draw": 0}
                odds_softs   = {}

                for bookie in jogo.get("bookmakers", []):
                    key = bookie["key"]
                    for market in bookie.get("markets", []):
                        if market["key"] != "h2h":
                            continue
                        for outcome in market.get("outcomes", []):
                            nome = outcome["name"]
                            odd  = outcome["price"]
                            side = "home" if nome == home else "away" if nome == away else "draw"
                            if key == "pinnacle":
                                odd_pinnacle[side] = odd
                            elif key in ("betano", "bet365"):
                                if key not in odds_softs:
                                    odds_softs[key] = {}
                                odds_softs[key][side] = odd

                for side in ("home", "away"):
                    odd_pin = odd_pinnacle.get(side, 0)
                    if not odd_pin:
                        continue

                    prob_pin = 1 / odd_pin

                    for bookie_key, odds_bm in odds_softs.items():
                        odd_soft = odds_bm.get(side, 0)
                        if not odd_soft:
                            continue

                        ev = (prob_pin * odd_soft) - 1

                        if ev < min_ev or ev > config.MAX_EV:
                            continue

                        liga_nome = liga_key.replace("soccer_", "").replace("_", " ").title()

                        if odd_soft < get_min_odd(liga_nome) or odd_soft > get_max_odd(liga_nome):
                            continue

                        bookmaker = "Betano BR" if bookie_key == "betano" else "Bet365"

                        sinais.append({
                            "event_id":  event_id,
                            "home":      home,
                            "away":      away,
                            "liga":      liga_nome,
                            "data":      data,
                            "bet_side":  side,
                            "odd":       odd_soft,
                            "ev_api":    ev,
                            "market":    "ML",
                            "href":      "",
                            "bookmaker": bookmaker,
                        })

        except Exception as e:
            print(f"⚠️ Erro fallback {liga_key}: {e}")
            continue

    vistos = {}
    for s in sinais:
        chave = f"{s['event_id']}-{s['bet_side']}"
        if chave not in vistos or s["odd"] > vistos[chave]["odd"]:
            vistos[chave] = s

    return list(vistos.values())


# ─────────────────────────────────────────────
# VALUE BETS — fonte principal (odds-api.io)
# ─────────────────────────────────────────────

def buscar_value_bets(min_ev=None):
    if min_ev is None:
        min_ev = config.MIN_EDGE_PRINCIPAL

    _carregar_cache()
    todos_sinais = []
    erros_429    = 0

    for bookmaker in BOOKMAKERS:
        chave_cache = f"value_bets_{bookmaker}"

        if _cache_valido(chave_cache):
            print(f"   📦 Cache válido para {bookmaker} — sem request")
            todos_sinais.extend(_cache.get(chave_cache, []))
            continue

        try:
            resp = requests.get(f"{BASE_ODDS_API_IO}/value-bets", params={
                "apiKey":              config.ODDS_API_IO_KEY,
                "bookmaker":           bookmaker,
                "includeEventDetails": "true",
                "sport":               "football",
            }, timeout=15)

            if resp.status_code == 429:
                print(f"⚠️ Erro {bookmaker} (429): {resp.text}")
                erros_429 += 1
                continue

            if resp.status_code != 200:
                print(f"⚠️ Erro {bookmaker} ({resp.status_code}): {resp.text}")
                continue

            dados = resp.json()
            if not isinstance(dados, list):
                print(f"⚠️ Resposta inesperada {bookmaker}: {dados}")
                continue

            sinais_bm = []
            for bet in dados:
                ev_raw = bet.get("expectedValue", 0)
                ev     = (ev_raw / 100) - 1

                if ev < min_ev or ev > config.MAX_EV:
                    continue

                evento = bet.get("event", {})
                liga   = evento.get("league", "")
                sport  = evento.get("sport", "").lower()

                if sport != "football":
                    continue
                if not any(pais in liga.lower() for pais in LIGAS_ALVO):
                    continue
                if any(ex in liga.lower() for ex in LIGAS_EXCLUIR):
                    continue

                bet_side    = bet.get("betSide")
                market      = bet.get("market", {})
                market_name = market.get("name", "")

                if market_name not in ("ML", "1X2", ""):
                    continue

                if bet_side == "draw":
                    continue

                odds_bm = bet.get("bookmakerOdds", {})
                odd     = float(odds_bm.get(bet_side, 0) or 0)

                if odd < get_min_odd(liga) or odd > get_max_odd(liga):
                    continue

                sinais_bm.append({
                    "event_id":  bet.get("eventId"),
                    "home":      evento.get("home"),
                    "away":      evento.get("away"),
                    "liga":      liga,
                    "data":      evento.get("date"),
                    "bet_side":  bet_side,
                    "odd":       odd,
                    "ev_api":    ev,
                    "market":    market_name,
                    "href":      odds_bm.get("href", ""),
                    "bookmaker": bookmaker,
                })

            _salvar_cache(chave_cache, sinais_bm)
            todos_sinais.extend(sinais_bm)

        except Exception as e:
            print(f"⚠️ Erro ao buscar {bookmaker}: {e}")
            continue

    if erros_429 == len(BOOKMAKERS) and not todos_sinais:
        print("   🔄 odds-api.io indisponível — usando The Odds API como fallback...")
        return buscar_value_bets_fallback(min_ev)

    vistos = {}
    for s in todos_sinais:
        chave = f"{s['event_id']}-{s['bet_side']}"
        if chave not in vistos or s["odd"] > vistos[chave]["odd"]:
            vistos[chave] = s

    return list(vistos.values())
