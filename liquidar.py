import sqlite3
import datetime
import config
import odds_client
import notificador

def liquidar_apostas():
    conn = sqlite3.connect(config.DATABASE_PATH)
    c = conn.cursor()

    c.execute("""
        SELECT id, event_id, time_casa, time_fora, aposta_em,
               odd_aposta, valor_aposta, data_jogo
        FROM paper_bets
        WHERE status = 'Pendente' AND event_id IS NOT NULL
    """)
    pendentes = c.fetchall()

    if not pendentes:
        print("📭 Nenhuma aposta pendente com event_id para liquidar.")
        conn.close()
        return

    print(f"🔄 Verificando resultados para {len(pendentes)} apostas...\n")
    liquidadas    = 0
    nao_finalizadas = 0

    for id_db, event_id, casa, fora, aposta_em, odd, valor, data in pendentes:
        resultado = odds_client.buscar_resultado(event_id)

        if resultado is None:
            print(f"⏳ Ainda não finalizado: {casa} x {fora}")
            nao_finalizadas += 1
            continue

        if resultado == "expirado":
            print(f"⚠️  EXPIRADO: {casa} x {fora} — liquidar manualmente")
            nao_finalizadas += 1
            continue

        gols_casa, gols_fora = resultado

        if gols_casa > gols_fora:    vencedor = casa
        elif gols_fora > gols_casa:  vencedor = fora
        else:                         vencedor = "Empate"

        if aposta_em == vencedor:
            status = "Ganhou"
            lucro  = round(valor * (odd - 1), 2)
        else:
            status = "Perdeu"
            lucro  = round(-valor, 2)

        c.execute("""
            UPDATE paper_bets
            SET status = ?, lucro = ?
            WHERE id = ?
        """, (status, lucro, id_db))

        icone = "✅" if status == "Ganhou" else "❌"
        print(f"{icone} {casa} {gols_casa}x{gols_fora} {fora}")
        print(f"   Aposta: {aposta_em} → {status} | R$ {lucro:+.2f}\n")
        notificador.notificar_liquidacao(casa, fora, gols_casa, gols_fora, aposta_em, status, lucro)
        liquidadas += 1

    conn.commit()
    conn.close()

    print("-" * 45)
    print(f"✅ {liquidadas} liquidada(s) | ⏳ {nao_finalizadas} ainda em andamento")

if __name__ == "__main__":
    liquidar_apostas()