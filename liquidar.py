"""
liquidar.py — Liquidação automática de apostas
Project Dobermann

Melhorias desta versão:
  • Filtro de horário: só consulta apostas cujo jogo já terminou
    (data_jogo + 105 min de tolerância para tempo extra + delay da API)
  • Resultados via The Odds API /scores (grátis, sem custo de cota)
  • odds-api.io só como fallback para ligas fora da cobertura da The Odds API
  • Jogos 2+ dias sem resultado = alerta de liga sem cobertura → liquidar manualmente
  • Zero requests desperdiçadas em jogos que ainda não começaram
"""

import sqlite3
import datetime
import config
import odds_client
import notificador

# 90 min de jogo + 15 min de tolerância para prorrogação e delay da API
TOLERANCIA_MINUTOS = 105


def jogo_provavelmente_terminou(data_jogo_str):
    """
    Retorna True se o jogo provavelmente já terminou.
    Lógica: horário do jogo + TOLERANCIA_MINUTOS < agora (UTC).
    Se não conseguir parsear a data, libera a consulta por precaução.
    """
    if not data_jogo_str or data_jogo_str == "Manual":
        return True

    agora   = datetime.datetime.now(datetime.timezone.utc)
    dt_jogo = None

    # fromisoformat entende ISO 8601 completo — normaliza o 'Z' para '+00:00'
    data_normalizada = data_jogo_str.strip().replace("Z", "+00:00")
    try:
        dt_jogo = datetime.datetime.fromisoformat(data_normalizada)
        if dt_jogo.tzinfo is None:
            dt_jogo = dt_jogo.replace(tzinfo=datetime.timezone.utc)
    except ValueError:
        # Fallback: tenta só a parte da data
        try:
            dt_jogo = datetime.datetime.strptime(data_jogo_str[:10], "%Y-%m-%d")
            dt_jogo = dt_jogo.replace(hour=23, minute=59, tzinfo=datetime.timezone.utc)
        except ValueError:
            pass

    if dt_jogo is None:
        print(f"   ⚠️  Formato de data não reconhecido: '{data_jogo_str}' — consultando mesmo assim")
        return True

    termino_estimado = dt_jogo + datetime.timedelta(minutes=TOLERANCIA_MINUTOS)
    return agora >= termino_estimado


def liquidar_apostas():
    conn = sqlite3.connect(config.DATABASE_PATH)
    c = conn.cursor()

    # Garante que a tabela existe
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

    c.execute("""
        SELECT id, event_id, time_casa, time_fora, aposta_em,
               odd_aposta, valor_aposta, data_jogo, liga
        FROM paper_bets
        WHERE status = 'Pendente'
        ORDER BY data_jogo ASC
    """)
    todas_pendentes = c.fetchall()

    if not todas_pendentes:
        print("📭 Nenhuma aposta pendente para liquidar.")
        conn.close()
        return

    # ── Separa quem já terminou de quem ainda não começou ──
    aptas      = []   # jogo já terminou — consulta resultado
    muito_cedo = []   # jogo ainda não terminou — não gasta request

    for row in todas_pendentes:
        id_db, event_id, casa, fora, aposta_em, odd, valor, data_jogo, liga = row
        if jogo_provavelmente_terminou(data_jogo):
            aptas.append(row)
        else:
            muito_cedo.append(row)

    if muito_cedo:
        print(f"⏰ {len(muito_cedo)} aposta(s) ignorada(s) — jogo ainda não terminou:")
        for row in muito_cedo:
            _, _, casa, fora, _, _, _, data_jogo, _ = row
            print(f"   • {casa} x {fora} | Início: {data_jogo}")
        print()

    if not aptas:
        print("📭 Nenhuma aposta elegível para liquidação agora.")
        conn.close()
        return

    print(f"🔄 Verificando resultados para {len(aptas)} aposta(s)...\n")

    liquidadas      = 0
    nao_finalizadas = 0

    for id_db, event_id, casa, fora, aposta_em, odd, valor, data_jogo, liga in aptas:

        # Apostas sem event_id só podem ser liquidadas manualmente
        if not event_id:
            print(f"✍️  Sem event_id: {casa} x {fora} — liquidar manualmente")
            nao_finalizadas += 1
            continue

        resultado = odds_client.buscar_resultado(event_id, home=casa, away=fora, data_jogo_str=data_jogo)

        if resultado is None:
            # Calcula quantos dias se passaram desde o jogo
            try:
                dt_jogo = datetime.datetime.fromisoformat(
                    data_jogo.strip().replace("Z", "+00:00")
                )
                dias_passados = (datetime.datetime.now(datetime.timezone.utc) - dt_jogo).days
            except Exception:
                dias_passados = 0

            if dias_passados >= 2:
                # Liga sem cobertura nas APIs — sinaliza para liquidação manual
                liga_nome = liga if liga else "liga desconhecida"
                print(f"🚨 Sem cobertura ({dias_passados}d): {casa} x {fora} [{liga_nome}] — liquidar manualmente")
            else:
                print(f"⏳ Ainda não disponível: {casa} x {fora}")

            nao_finalizadas += 1
            continue

        if resultado == "expirado":
            print(f"⚠️  Expirado: {casa} x {fora} — liquidar manualmente")
            nao_finalizadas += 1
            continue

        gols_casa, gols_fora = resultado

        if gols_casa > gols_fora:    vencedor = casa
        elif gols_fora > gols_casa:  vencedor = fora
        else:                        vencedor = "Empate"

        apostou_venceu = (
            aposta_em == vencedor or
            (vencedor != "Empate" and aposta_em.lower() in vencedor.lower()) or
            (vencedor != "Empate" and vencedor.lower() in aposta_em.lower())
        )

        status = "Ganhou" if apostou_venceu else "Perdeu"
        lucro  = round(valor * (odd - 1), 2) if status == "Ganhou" else round(-valor, 2)

        c.execute(
            "UPDATE paper_bets SET status=?, lucro=? WHERE id=?",
            (status, lucro, id_db)
        )

        icone = "✅" if status == "Ganhou" else "❌"
        print(f"{icone} {casa} {gols_casa}x{gols_fora} {fora}")
        print(f"   Aposta: {aposta_em} → {status} | R$ {lucro:+.2f}\n")
        notificador.notificar_liquidacao(casa, fora, gols_casa, gols_fora, aposta_em, status, lucro)
        liquidadas += 1

    conn.commit()
    conn.close()

    print("-" * 45)
    print(f"✅ {liquidadas} liquidada(s) | ⏳ {nao_finalizadas} aguardando/manual")

if __name__ == "__main__":
    liquidar_apostas()
