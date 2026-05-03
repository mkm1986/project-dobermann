import sqlite3
import config

def buscar_nome_real():
    conn = sqlite3.connect(config.DATABASE_PATH)
    c = conn.cursor()
    
    # Pega todos os times únicos que já jogaram em casa no nosso banco
    c.execute("SELECT DISTINCT time_casa FROM partidas ORDER BY time_casa")
    times_banco = [linha[0] for linha in c.fetchall()]
    
    conn.close()
    
    print("🔍 INVESTIGADOR DE TIMES 🔍")
    print("Digite parte do nome de um time para ver como ele está no banco.")
    print("Digite 'sair' para encerrar.\n")
    
    while True:
        busca = input("Nome do time: ").strip()
        if busca.lower() == 'sair':
            break
            
        encontrados = [t for t in times_banco if busca.lower() in t.lower()]
        
        if encontrados:
            print(f"✅ Encontrados no banco: {encontrados}\n")
        else:
            print("❌ Nenhum time encontrado com esse nome (Pode ser time recém-promovido).\n")

if __name__ == "__main__":
    buscar_nome_real()