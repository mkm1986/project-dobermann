import sqlite3
import config

conn = sqlite3.connect(config.DATABASE_PATH)
c = conn.cursor()

# Remove duplicatas mantendo apenas o registro mais antigo por event_id
c.execute("""
    DELETE FROM paper_bets
    WHERE id NOT IN (
        SELECT MIN(id)
        FROM paper_bets
        GROUP BY event_id
    )
    AND status = 'Pendente'
""")

removidos = c.rowcount
conn.commit()
print(f"✅ {removidos} duplicatas removidas.")

c.execute("SELECT COUNT(*) FROM paper_bets WHERE status = 'Pendente'")
print(f"Apostas pendentes restantes: {c.fetchone()[0]}")
conn.close()