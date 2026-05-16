import sqlite3
import datetime
import config
import modelo
import odds_client
import notificador

def calcular_kelly(prob_vitoria, odd):
    fracao          = config.KELLY_FRACAO_ALTA if odd >= 3.00 else config.KELLY_FRACAO_BAIXA
    prob_derrota    = 1 - prob_vitoria
    lucro_potencial = odd - 1
    kelly_puro      = ((lucro_potencial * prob_vitoria) - prob_derrota) / lucro_potencial
    return max(0, kelly_puro * fracao)

def aplicar_teto(valor):
    """Aplica teto e mínimo de segurança à aposta."""
    teto = min(config.MAX_APOSTA_VALOR,
               config.MAX_APOSTA_PERCENTUAL * config.BANCA_ATUAL)
    return max(config.MIN_APOSTA_VALOR, min(valor, teto))

def get_min_edge(liga):
    liga_lower = liga.lower()
    obscuras = ["cup", "copa", "pokal", "ykkonen", "esiliiga", "2nd", "3rd",
                "2. liga", "3. liga", "1. deild", "fnl", "superettan",
                "divize", "danmarksserien", "1. division", "1st division"]
    if any(p in liga_lower for p in obscuras):
        return config.MIN_EDGE_OBSCURO
    return config.MIN_EDGE_PRINCIPAL

def e_time_reserva(nome):
    """Detecta se o time é reserva/filial pelo nome."""
    indicadores = [" 2", " ii", " b ", " b)", "(b)", "reserva",
                   "filial", "talang", "akatemia", "academy"]
    nome_lower = nome.lower()
    return any(ind in nome_lower for ind in indicadores)

def rodar_paper_betting():
    conn = sqlite3.connect(config.DATABASE_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS paper_bets (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            data_registro  TEXT,
            data_jogo      TEXT,
            time_casa      TEXT,
            time_fora      TEXT,
            aposta_em      TEXT,
            odd_aposta     REAL,
            prob_modelo    REAL,
            valor_aposta   REAL,
            status         TEXT DEFAULT 'Pendente',
            lucro          REAL DEFAULT 0.0,
            event_id       TEXT,
            liga           TEXT,
            bookmaker      TEXT
        )
    """)
    conn.commit()

    print("🧠 Treinando modelo ELO + Dixon-Coles...")
    elos, jogos_por_time, rho = modelo.treinar_modelo()
    print()

    print("📡 Buscando value bets (Betano BR + Bet365)...")
    sinais = odds_client.buscar_value_bets()
    print(f"   {len(sinais)} sinais nas ligas alvo\n")

    if not sinais:
        print("😴 Nenhum sinal encontrado nas ligas alvo no momento.")
        notificador.notificar_resumo(0, 0)
        conn.close()
        return

    apostas_salvas    = 0
    apostas_ignoradas = 0

    print("🔍 ANALISANDO SINAIS:\n" + "-" * 55)

    for s in sinais:
        home      = s["home"]
        away      = s["away"]
        liga      = s["liga"]
        bet_side  = s["bet_side"]
        odd       = s["odd"]
        ev_api    = s["ev_api"]
        event_id  = str(s["event_id"])
        data      = s["data"]
        bookmaker = s["bookmaker"]

        print(f"⚽ {home} x {away}")
        print(f"   Liga:     {liga}")
        print(f"   Aposta:   {bet_side} @ {odd:.2f} | EV API: {ev_api:.2%} | {bookmaker}")

        # ── FILTRO 1: Odd mínima ──────────────────────────────
        # Garante que apenas odds acima do mínimo configurado entram,
        # independente do que a API retornar.
        if odd < config.MIN_ODD_ML:
            print(f"   ❌ Odd {odd:.2f} abaixo do mínimo ({config.MIN_ODD_ML:.2f})\n")
            apostas_ignoradas += 1
            continue

        # ── FILTRO 2: Anti-duplicata por jogo ────────────────
        # Bloqueia qualquer nova aposta no mesmo jogo (home x away),
        # independente do event_id ou do lado (home/away).
        # Isso evita apostar nas duas pontas do mesmo jogo.
        c.execute("""
            SELECT id FROM paper_bets
            WHERE time_casa=? AND time_fora=? AND status='Pendente'
        """, (home, away))
        if c.fetchone():
            print(f"   ⏭️  Jogo já registrado (anti-duplicata)\n")
            continue

        # Verifica também pelo event_id como segunda camada
        c.execute("""
            SELECT id FROM paper_bets
            WHERE event_id=? AND status='Pendente'
        """, (event_id,))
        if c.fetchone():
            print(f"   ⏭️  Já registrada (event_id)\n")
            continue

        # Detecta se é time reserva
        aposta_time = home if bet_side == "home" else away
        is_reserva  = e_time_reserva(aposta_time)

        # Valida com Dixon-Coles
        prob_modelo   = None
        time_casa_elo = None
        time_fora_elo = None

        if not is_reserva:
            for nome in elos:
                if nome.lower() in home.lower() or home.lower() in nome.lower():
                    time_casa_elo = nome
                if nome.lower() in away.lower() or away.lower() in nome.lower():
                    time_fora_elo = nome

        if time_casa_elo and time_fora_elo and not is_reserva:
            jogos_c = jogos_por_time.get(time_casa_elo, 0)
            jogos_f = jogos_por_time.get(time_fora_elo, 0)

            if jogos_c >= config.MIN_JOGOS_HISTORICO and jogos_f >= config.MIN_JOGOS_HISTORICO:
                p_casa, p_emp, p_fora = modelo.probabilidade_jogo(
                    elos[time_casa_elo], elos[time_fora_elo], rho
                )
                if bet_side == "home":   prob_modelo = p_casa
                elif bet_side == "draw": prob_modelo = p_emp
                elif bet_side == "away": prob_modelo = p_fora

                ev_modelo = (prob_modelo * odd) - 1
                print(f"   🧠 Modelo: P={prob_modelo:.1%} | EV modelo: {ev_modelo:.2%}")

                min_ev = get_min_edge(liga)
                if ev_modelo < min_ev:
                    print(f"   ❌ Modelo discorda (EV={ev_modelo:.2%} < {min_ev:.0%})\n")
                    apostas_ignoradas += 1
                    continue
            else:
                print(f"   ⚠️  Histórico insuficiente — confiando só na API")
        else:
            if is_reserva:
                print(f"   ⚠️  Time reserva detectado — usando só EV da API")
            else:
                print(f"   ⚠️  Times não encontrados no ELO — confiando só na API")

        # Calcula valor com Kelly dinâmico
        if prob_modelo and not is_reserva:
            valor = round(calcular_kelly(prob_modelo, odd) * config.BANCA_ATUAL, 2)
        else:
            prob_implicita = 1 / odd
            prob_real      = prob_implicita * (1 + ev_api)
            valor          = round(calcular_kelly(prob_real, odd) * config.BANCA_ATUAL, 2)

        # Aplica teto de segurança
        valor_original = valor
        valor          = round(aplicar_teto(valor), 2)
        if valor < valor_original:
            print(f"   🔒 Teto aplicado: R$ {valor_original:.2f} → R$ {valor:.2f}")

        if valor <= 0:
            print(f"   ❌ Kelly = zero\n")
            apostas_ignoradas += 1
            continue

        if bet_side == "home":   aposta_em = home
        elif bet_side == "away": aposta_em = away
        else:                    aposta_em = "Empate"

        hoje = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("""
            INSERT INTO paper_bets
            (data_registro, data_jogo, time_casa, time_fora,
             aposta_em, odd_aposta, prob_modelo, valor_aposta,
             event_id, liga, bookmaker)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (hoje, data, home, away,
              aposta_em, odd, prob_modelo, valor,
              event_id, liga, bookmaker))

        apostas_salvas += 1
        print(f"   🚨 SINAL SALVO: {aposta_em} @ {odd:.2f} | R$ {valor:.2f}")
        print(f"   🔗 {s['href']}\n")
        notificador.notificar_sinal(s, valor)

    conn.commit()
    conn.close()

    print("-" * 55)
    print(f"✅ {apostas_salvas} aposta(s) salva(s) | {apostas_ignoradas} ignorada(s)")
    notificador.notificar_resumo(apostas_salvas, apostas_ignoradas)

if __name__ == "__main__":
    rodar_paper_betting()
