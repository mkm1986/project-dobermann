import sqlite3
import config
import datetime

def registrar_entrada_manual():
    print("📝 --- REGISTRO DE APOSTA MANUAL ---")
    casa = input("Time da Casa: ").strip()
    fora = input("Time de Fora: ").strip()
    aposta_em = input(f"Apostar em quem? ({casa} / {fora} / Empate): ").strip()
    odd = float(input("Qual a Odd que você encontrou?: "))
    valor = float(input("Valor da aposta (R$): "))
    
    hoje = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = sqlite3.connect(config.DATABASE_PATH)
    c = conn.cursor()
    
    c.execute("""
        INSERT INTO paper_bets 
        (data_registro, data_jogo, time_casa, time_fora, aposta_em, odd_aposta, prob_modelo, valor_aposta, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (hoje, "Manual", casa, fora, aposta_em, odd, 0.0, valor, "Pendente"))
    
    conn.commit()
    conn.close()
    print(f"\n✅ Aposta em '{aposta_em}' registrada com sucesso!")

if __name__ == "__main__":
    registrar_entrada_manual()