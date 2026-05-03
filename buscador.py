import requests
import sqlite3
import config

BASE = "https://api.odds-api.io/v3"

def buscar_time(nome):
    """Busca um time pelo nome na API e retorna o ID e nome oficial."""
    resp = requests.get(f"{BASE}/events/search", params={
        "apiKey": config.ODDS_API_IO_KEY,
        "query":  nome,
        "sport":  "football",
    }, timeout=15)

    if resp.status_code != 200:
        return None

    dados = resp.json()
    if not isinstance(dados, list) or not dados:
        return None

    return dados

def encontrar_event_id(home, away):
    """
    Busca o event_id de um jogo pelo nome dos times.
    Retorna o event_id ou None.
    """
    resp = requests.get(f"{BASE}/events/search", params={
        "apiKey": config.ODDS_API_IO_KEY,
        "query":  f"{home} {away}",
        "sport":  "football",
    }, timeout=15)

    if resp.status_code != 200:
        return None

    dados = resp.json()
    if not isinstance(dados, list) or not dados:
        return None

    for ev in dados:
        h = ev.get("home", "").lower()
        a = ev.get("away", "").lower()
        if home.lower() in h or h in home.lower():
            if away.lower() in a or a in away.lower():
                return ev.get("id")

    return None

def mapear_nome_elo(nome_api, elos):
    """
    Tenta encontrar o nome equivalente no banco ELO
    para um time retornado pela API.
    Primeiro tenta match direto, depois fuzzy, depois busca na API.
    """
    # Match direto
    if nome_api in elos:
        return nome_api

    # Fuzzy match
    nome_lower = nome_api.lower()
    for nome_elo in elos:
        if nome_lower in nome_elo.lower() or nome_elo.lower() in nome_lower:
            return nome_elo

    return None

if __name__ == "__main__":
    # Testa a busca de evento
    print("=== TESTE DE BUSCA DE EVENTOS ===\n")

    testes = [
        ("Viking FK", "Rosenborg BK"),
        ("Bodø/Glimt", "Molde FK"),
        ("Djurgardens IF", "Hammarby IF"),
    ]

    for home, away in testes:
        print(f"Buscando: {home} x {away}")
        resp = requests.get(f"{BASE}/events/search", params={
            "apiKey": config.ODDS_API_IO_KEY,
            "query":  f"{home} {away}",
            "sport":  "football",
        }, timeout=15)

        dados = resp.json()
        if isinstance(dados, list) and dados:
            for ev in dados[:2]:
                print(f"  ✅ {ev.get('home')} x {ev.get('away')} | ID: {ev.get('id')} | {ev.get('league', {}).get('name')}")
        else:
            print(f"  ❌ Não encontrado: {dados}")
        print()