import sqlite3
import config

def listar_pendentes():
    conn = sqlite3.connect(config.DATABASE_PATH)
    c = conn.cursor()
    
    c.execute("SELECT id, time_casa, time_fora, aposta_em, data_jogo FROM paper_bets WHERE status = 'Pendente'")
    pendentes = c.fetchall()
    
    print(f"📋 VOCÊ TEM {len(pendentes)} APOSTAS PENDENTES:\n")
    print(f"{'ID':<4} | {'CASA':<15} x {'FORA':<15} | {'APOSTA EM':<15} | {'DATA/HORA'}")
    print("-" * 75)
    
    for p in pendentes:
        id_db, casa, fora, aposta_em, data = p
        print(f"{id_db:<4} | {casa:<15} x {fora:<15} | {aposta_em:<15} | {data}")
        
    conn.close()

if __name__ == "__main__":
    listar_pendentes()