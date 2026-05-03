import sqlite3
import config

conn = sqlite3.connect(config.DATABASE_PATH)
c = conn.cursor()

print("=== DATA MAIS RECENTE POR LIGA ===")
c.execute("""
    SELECT liga_nome, MAX(data) as ultima_data, COUNT(*) as jogos_2026
    FROM partidas
    WHERE temporada = '2026'
    GROUP BY liga_nome
    ORDER BY ultima_data DESC
""")
for r in c.fetchall():
    print(f"{r[0]:<30} | Último jogo: {r[1]} | Jogos em 2026: {r[2]}")

conn.close()