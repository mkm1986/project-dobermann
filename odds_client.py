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
    "u19", "u18", "u17", "u16", "u15",
    "u-19", "u-18", "u-17",
    "under 19", "under 18", "under 17",
    "under-19", "under-18", "under-17",
    "youth", "juvenil",
    "women", "feminino", "femenino",
    "kvinde", "damer", "naiset",
    "toppserien", "damallsvenskan",
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

# ─────────────────────────────────────────────
# MAPEAMENTO LIGA → KEY DA THE ODDS API
#
# Chave: fragmento do nome da liga como aparece no banco (campo liga)
# Valor: key da The Odds API para o endpoint /scores
#
# IMPORTANTE: 1 request por aposta em vez de varrer todas as 20+ ligas.
# Se a liga não estiver aqui, cai direto para o fallback odds-api.io.
# ─────────────────────────────────────────────

MAPA_LIGA_KEY = {
    # Noruega
    "norway - eliteserien":           "soccer_norway_eliteserien",
    "norway - 1st division":          "soccer_norway_1st_division",
    "norway - 1. divisjon":           "soccer_norway_1st_division",
    # Suécia
    "sweden - allsvenskan":           "soccer_sweden_allsvenskan",
    "sweden - superettan":            "soccer_sweden_superettan",
    # Dinamarca
    "denmark - superliga":            "soccer_denmark_superliga",
    "denmark - 1st division":         "soccer_denmark_1st_division",
    "denmark - 1. division":          "soccer_denmark_1st_division",
    # Finlândia
    "finland - veikkausliiga":        "soccer_finland_veikkausliiga",
    "finland - ykkonen":              "soccer_finland_ykkonen",
    # Islândia
    "iceland - besta deild":          "soccer_iceland_premier_division",
    "iceland - premier division":     "soccer_iceland_premier_division",
    "iceland - urvalsdeild":          "soccer_iceland_premier_division",
    # Irlanda
    "ireland - premier division":     "soccer_ireland_premier_division",
    # Escócia
    "scotland - premiership":         "soccer_scotland_premier_league",
    "scotland - championship":        "soccer_scotland_championship",
    "scotland - league one":          "soccer_scotland_league1",
    "scotland - league 1":            "soccer_scotland_league1",
    # Irlanda do Norte
    "northern ireland - premiership": "soccer_northern_ireland_premier_league",
    # País de Gales
    "wales - cymru premier":          "soccer_wales_premier_league",
    # Tcheca
    "czechia - fortuna liga":         "soccer_czech_republic_fl",
    "czechia - fnl":                  "soccer_czech_republic_fnl",
    "czech republic - fortuna liga":  "soccer_czech_republic_fl",
    # Eslováquia
    "slovakia - superliga":           "soccer_slovakia_superliga",
    # Estônia
    "estonia - meistriliiga":         "soccer_estonia_meistriliiga",
    "estonia - premium liiga":        "soccer_estonia_meistriliiga",
    # Romênia
    "romania - superliga":            "soccer_romania_1",
    # EUA
    "usa - usl championship":         "soccer_usa_usl_championship",
    "usa - usl league one":           "soccer_usa_usl_leagueone",
    # Canadá
    "canada - canadian premier league": "soccer_canada_premier_league",
    "canada - canadian championship":   "soccer_canada_mls",
}

# Lista completa para fallback de value bets
LIGAS_THE_ODDS_API = list(set(MAPA_LIGA_KEY.values()))


def _resolver_key_liga(liga_nome):
    """
    Resolve o key da The Odds API a partir do nome da liga salvo no banco.
    Tenta match exato primeiro, depois parcial.
    Retorna o key ou None se não encontrado.
    """
    if not liga_nome:
        return None

    liga_lower = liga_nome.lower().strip()

    # Match exato
    if liga_lower in MAPA_LIGA_KEY:
        return MAPA_LIGA_KEY[liga_lower]

    # Match parcial — procura fragmento do mapa dentro do nome da liga
    for fragmento, key in MAPA_LIGA_KEY.items():
        if fragmento in liga_lower or liga_lower in fragmento:
            return key

    return None  # Liga não mapeada — vai para fallback odds-api.io


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
# ESTRATÉGIA DE CUSTO:
#   • Antes: varrendo 20+ ligas por aposta = 20+ requests por aposta
#   • Agora: 1 request por aposta usando mapeamento liga → key
#   • Se liga não está no mapa: cai para odds-api.io (fallback)
#

def buscar_resultado_the_odds_api(home, away, data_jogo_str, liga_nome=None):
    """
    Busca placar via The Odds API — endpoint /scores.
    Usa mapeamento liga→key para fazer apenas 1 request por aposta.
    Retorna (gols_casa, gols_fora) ou None.
    """
    # Resolve qual liga consultar — 1 request apenas
    liga_key = _resolver_key_liga(liga_nome)

    if not liga_key:
        # Liga não mapeada — não tem cobertura na The Odds API
        return None

    home_lower = home.lower()
    away_lower = away.lower()
    data_str   = data_jogo_str[:10] if data_jogo_str else ""

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
            print(f"   ⚠️ The Odds API: chave inválida ou sem requests restantes")
            return None

        if resp.status_code == 422:
            print(f"   ⚠️ The Odds API: liga '{liga_key}' não reconhecida")
            return None

        if resp.status_code != 200:
            return None

        eventos = resp.json()
        if not isinstance(eventos, list) or not eventos:
            return None

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

    return None


def buscar_resultado_odds_api_io(event_id):
    """
    Fallback: busca resultado via odds-api.io.
    Usado quando The Odds API não cobre a liga ou está sem requests.
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


def buscar_resultado(event_id, home=None, away=None, data_jogo_str=None, liga_nome=None):
    """
    Ponto de entrada para busca de resultado.

    Estratégia de custo mínimo:
      1. The Odds API /scores — 1 request por aposta (via mapeamento liga→key)
      2. odds-api.io /events  — fallback, só se liga não mapeada ou API sem cota
    """
    # Tentativa 1: The Odds API — 1 request, custo zero da cota principal
    if home and away and liga_nome:
        resultado = buscar_resultado_the_odds_api(home, away, data_jogo_str or "", liga_nome)
        if resultado is not None:
            return resultado

    # Tentativa 2: odds-api.io — fallback
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
