import requests
import sqlite3
import csv
import config

BASE_NEW = "https://www.football-data.co.uk/new"

LIGAS_NEW = {
    "NOR": "Eliteserien (Noruega)",
    "SWE": "Allsvenskan (Suecia)",
    "DNK": "Superliga (Dinamarca)",
    "FIN": "Veikkausliiga (Finlandia)",
    "IRL": "League of Ireland",
    "ISL": "Urvalsdeild (Islandia)",
    "USA": "USL (EUA)",
}

def criar_banco():
    conn = sqlite3.connect(config.DATABASE_PATH)
    c = conn.cursor()
    # Adicionadas as 3 colunas odd_max
    c.execute("""
        CREATE TABLE IF NOT EXISTS partidas (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            liga_cod       TEXT,
            liga_nome      TEXT,
            temporada      TEXT,
            data           TEXT,
            time_casa      TEXT,
            time_fora      TEXT,
            gols_casa      INTEGER,
            gols_fora      INTEGER,
            odd_b365_casa  REAL,
            odd_b365_emp   REAL,
            odd_b365_fora  REAL,
            odd_pin_casa   REAL,
            odd_pin_emp    REAL,
            odd_pin_fora   REAL,
            odd_max_casa   REAL,
            odd_max_emp    REAL,
            odd_max_fora   REAL,
            UNIQUE(liga_cod, data, time_casa, time_fora)
        )
    """)
    conn.commit()
    conn.close()
    print("Banco pronto.")

def parse_csv(conteudo):
    texto = conteudo.decode("utf-8-sig", errors="ignore")
    linhas = [l for l in texto.splitlines() if l.strip()]
    return list(csv.DictReader(linhas))

def salvar(rows, liga_cod, liga_nome, temporada):
    TIMES_MLS = [
        "Inter Miami", "Vancouver Whitecaps", "LA Galaxy", "Seattle Sounders",
        "Portland Timbers", "Atlanta United", "NYCFC", "New England Revolution",
        "Philadelphia Union", "Columbus Crew", "Toronto FC", "CF Montreal",
        "New York Red Bulls", "DC United", "Orlando City", "FC Cincinnati",
        "Minnesota United", "Colorado Rapids", "Real Salt Lake", "FC Dallas",
        "Houston Dynamo", "Sporting KC", "Chicago Fire", "San Jose Earthquakes",
        "Nashville SC", "Austin FC", "Charlotte FC", "St. Louis City"
    ]
    conn = sqlite3.connect(config.DATABASE_PATH)
    c = conn.cursor()
    ok = 0
    for r in rows:
        try:
            gc_raw = r.get("FTHG") or r.get("HG", "")
            gf_raw = r.get("FTAG") or r.get("AG", "")
            if not gc_raw or not gf_raw:
                continue
            data = r.get("Date", "")
            casa = (r.get("HomeTeam") or r.get("Home", "")).strip()
            fora = (r.get("AwayTeam") or r.get("Away", "")).strip()
            temp = r.get("Season") or temporada
            if not casa or not fora or not data:
                continue
            if casa in TIMES_MLS or fora in TIMES_MLS:
                continue
            gc = int(float(gc_raw))
            gf = int(float(gf_raw))

            def f(k):
                v = r.get(k, "")
                return float(v) if v and v.strip() else None

            pinh  = f("PSCH")   or f("PSH")
            pind  = f("PSCD")   or f("PSD")
            pina  = f("PSCA")   or f("PSA")
            b365h = f("B365CH") or f("B365H")
            b365d = f("B365CD") or f("B365D")
            b365a = f("B365CA") or f("B365A")
            maxh  = f("MaxCH")  or f("MaxH")
            maxd  = f("MaxCD")  or f("MaxD")
            maxa  = f("MaxCA")  or f("MaxA")

            c.execute("""
                INSERT OR IGNORE INTO partidas
                (liga_cod, liga_nome, temporada, data,
                 time_casa, time_fora, gols_casa, gols_fora,
                 odd_b365_casa, odd_b365_emp, odd_b365_fora,
                 odd_pin_casa, odd_pin_emp, odd_pin_fora,
                 odd_max_casa, odd_max_emp, odd_max_fora)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (liga_cod, liga_nome, temp, data,
                  casa, fora, gc, gf,
                  b365h, b365d, b365a,
                  pinh, pind, pina,
                  maxh, maxd, maxa))
            ok += 1
        except Exception as e:
            print(f"\n🚨 ERRO DETECTADO: {e}")
            print(f"DADOS DA LINHA: {r}")
            continue
    conn.commit()
    conn.close()
    return ok

def coletar_tudo():
    criar_banco()
    total = 0
    for cod, nome in LIGAS_NEW.items():
        url = f"{BASE_NEW}/{cod}.csv"
        print(f"Baixando {nome}...")
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            print(f"  Erro {resp.status_code}")
            continue
        rows = parse_csv(resp.content)
        n = salvar(rows, cod, nome, "todas")
        print(f"  {n} partidas salvas.")
        total += n

    print(f"\nFootball-data.co.uk: {total} partidas.")
    print("\nColetando dados recentes via odds-api.io...")
    coletar_odds_api(dias=30)

    print(f"\nColeta finalizada.")

# Slugs das ligas obscuras não cobertas pelo football-data.co.uk
LIGAS_ODDS_API = [
    "norway-eliteserien",
    "norway-1st-division",
    "sweden-allsvenskan",
    "sweden-superettan",
    "denmark-superliga",
    "denmark-1-division",
    "finland-veikkausliiga",
    "finland-ykkonen",
    "iceland-besta-deild",
    "iceland-1-deild",
    "iceland-2-deild",
    "ireland-premier-division",
    "ireland-first-division",
    "estonia-premium-liiga",
    "estonia-esiliiga",
    "latvia-virsliga",
    "latvia-1liga",
    "lithuania-a-lyga",
    "lithuania-1-lyga",
    "slovakia-superliga",
    "slovakia-2-liga",
    "slovakia-3-liga",
    "czechia-1-liga",
    "czechia-fnl",
    "norway-nm-cup",
    "finland-suomen-cup",
    "sweden-svenska-cup",
    "denmark-dbu-pokalen",
    "iceland-cup",
    "ireland-fai-cup",
    "slovakia-slovensky-pohar",
    "czechia-cup",
]

def coletar_odds_api(dias=30):
    """Coleta resultados recentes via odds-api.io para ligas obscuras."""
    from datetime import datetime, timedelta, timezone
    import config as cfg

    criar_banco()

    hoje = datetime.now(timezone.utc)
    de   = (hoje - timedelta(days=dias)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ate  = hoje.strftime("%Y-%m-%dT%H:%M:%SZ")

    total = 0
    for slug in LIGAS_ODDS_API:
        resp = requests.get(
            "https://api.odds-api.io/v3/historical/events",
            params={
                "apiKey": cfg.ODDS_API_IO_KEY,
                "sport":  "football",
                "league": slug,
                "from":   de,
                "to":     ate,
            },
            timeout=15
        )

        if resp.status_code != 200:
            continue

        eventos = resp.json()
        if not isinstance(eventos, list) or not eventos:
            continue

        conn = sqlite3.connect(cfg.DATABASE_PATH)
        c = conn.cursor()
        inseridos = 0

        for ev in eventos:
            scores = ev.get("scores", {})
            ft = scores.get("periods", {}).get("fulltime", {})
            gc = ft.get("home") if ft else scores.get("home")
            gf = ft.get("away") if ft else scores.get("away")

            if gc is None or gf is None:
                continue

            liga_info = ev.get("league", {})
            liga_nome = liga_info.get("name", slug)
            data      = ev.get("date", "")[:10]
            casa      = ev.get("home", "")
            fora      = ev.get("away", "")
            temporada = data[:4]

            try:
                c.execute("""
                    INSERT OR IGNORE INTO partidas
                    (liga_cod, liga_nome, temporada, data,
                     time_casa, time_fora, gols_casa, gols_fora)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (slug, liga_nome, temporada, data,
                      casa, fora, int(gc), int(gf)))
                inseridos += 1
            except Exception:
                continue

        conn.commit()
        conn.close()

        if inseridos > 0:
            print(f"  ✅ {liga_nome}: {inseridos} partidas salvas")
        total += inseridos

    print(f"\nOdds-API: {total} partidas salvas no total.")
    return total

if __name__ == "__main__":
    coletar_tudo()