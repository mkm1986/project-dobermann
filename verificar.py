import sqlite3
import config

def verificar_ligas():
    # Conecta ao banco de dados
    conn = sqlite3.connect(config.DATABASE_PATH)
    c = conn.cursor()

    # Pede para o banco agrupar os jogos pelo nome da liga e contar
    c.execute("""
        SELECT liga_nome, COUNT(*) as total_jogos 
        FROM partidas 
        GROUP BY liga_nome
        ORDER BY total_jogos DESC
    """)
    
    resultados = c.fetchall()

    print("\n📊 RESUMO DO BANCO DE DADOS:")
    print("-" * 45)
    total_geral = 0
    for liga, total in resultados:
        print(f"Liga: {liga.ljust(25)} | Jogos salvas: {total}")
        total_geral += total
    
    print("-" * 45)
    print(f"TOTAL GERAL DE JOGOS: {total_geral}\n")

    conn.close()

if __name__ == "__main__":
    verificar_ligas()