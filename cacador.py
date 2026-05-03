import requests
import config
import modelo

def calcular_kelly(prob_vitoria, odd, fracao_kelly):
    """Calcula a porcentagem da banca a ser apostada usando o Critério de Kelly."""
    prob_derrota = 1 - prob_vitoria
    lucro_potencial = odd - 1
    # Fórmula de Kelly: (bp - q) / b
    kelly_puro = ((lucro_potencial * prob_vitoria) - prob_derrota) / lucro_potencial
    # Retorna o Kelly ajustado (ex: 1/4 Kelly) ou 0 se for negativo (sem valor)
    return max(0, kelly_puro * fracao_kelly)

def cacar_apostas():
    print("⏳ Carregando o cérebro e treinando o modelo com dados históricos...")
    elos = modelo.treinar_modelo()
    print("\n🔍 Cérebro carregado! Buscando jogos e odds ao vivo na The Odds API...\n")

    # Vamos buscar os próximos jogos de futebol. 
    # Usamos regions=eu (Europa) e bookmakers específicos para poupar sua cota de dados.
    url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/"
    parametros = {
        "apiKey": config.ODDS_API_KEY,
        "regions": "eu", # Foca na Europa/Nórdicas
        "markets": "h2h", # Moneyline (Vitória/Empate/Derrota)
        "bookmakers": "pinnacle,betano" # Puxa a casa Sharp e uma casa Soft
    }

    resposta = requests.get(url, params=parametros)
    
    if resposta.status_code != 200:
        print(f"🚨 Erro na API: {resposta.status_code} - {resposta.text}")
        return

    jogos = resposta.json()
    apostas_encontradas = 0

    print("🎯 ANALISANDO OPORTUNIDADES (+EV) NOS UNDERDOGS...\n")
    print("-" * 60)

    for jogo in jogos:
        time_casa = jogo.get("home_team")
        time_fora = jogo.get("away_team")

        # Verifica se os dois times existem no nosso banco de dados treinado
        if time_casa not in elos or time_fora not in elos:
            print(f"⚠️ IGNORADO (Nome não encontrado): {time_casa} x {time_fora}")
            continue
        else:
            print(f"✅ ANALISANDO: {time_casa} x {time_fora}")

        # Calcula a probabilidade real baseada no nosso modelo ELO
        prob_casa_modelo = modelo.probabilidade_esperada(elos[time_casa], elos[time_fora])
        prob_fora_modelo = modelo.probabilidade_esperada(elos[time_fora], elos[time_casa])

        # Procura as odds da Pinnacle e da Betano neste jogo
        odd_pinnacle_fora = 0
        odd_betano_fora = 0

        for bookie in jogo.get("bookmakers", []):
            nome_bookie = bookie["key"]
            # Acessa o mercado h2h (Moneyline)
            for mercado in bookie.get("markets", []):
                if mercado["key"] == "h2h":
                    # Procura a odd do time de fora (geralmente o underdog em ligas menores, mas testaremos ambos)
                    for opcao in mercado.get("outcomes", []):
                        if opcao["name"] == time_fora:
                            if nome_bookie == "pinnacle": odd_pinnacle_fora = opcao["price"]
                            if nome_bookie == "betano": odd_betano_fora = opcao["price"]

        # Aplica nossos filtros do config.py (Apenas Underdogs na Betano)
        if odd_betano_fora >= config.MIN_ODD_ML and odd_betano_fora <= config.MAX_ODD:
            
            # Filtro de Valor (O Edge)
            # Valor Esperado (EV) = Probabilidade * Odd - 1. Se > 0, tem valor.
            ev_fora = (prob_fora_modelo * odd_betano_fora) - 1
            
            if ev_fora >= config.MIN_EDGE:
                
                # Validação Sharp (A Betano está pagando mais que a Pinnacle?)
                if odd_pinnacle_fora > 0 and odd_betano_fora > odd_pinnacle_fora:
                    
                    sugestao_banca = calcular_kelly(prob_fora_modelo, odd_betano_fora, config.KELLY_FRACAO)
                    
                    if sugestao_banca > 0:
                        apostas_encontradas += 1
                        print(f"🚨 SINAL DE ENTRADA: {time_casa} x {time_fora}")
                        print(f"   Aposta: Vitória do {time_fora} (Underdog)")
                        print(f"   Probabilidade do Modelo: {prob_fora_modelo * 100:.1f}%")
                        print(f"   Odd Pinnacle (Sharp): {odd_pinnacle_fora}")
                        print(f"   Odd Betano (Soft): {odd_betano_fora}")
                        print(f"   Valor Esperado (Edge): {ev_fora * 100:.1f}%")
                        print(f"   Gestão: Apostar {sugestao_banca * 100:.2f}% da Banca")
                        print("-" * 60)

    if apostas_encontradas == 0:
        print("Nenhuma aposta de valor (+EV) encontrada nos underdogs no momento.")
        print("Mantenha a disciplina. Não force apostas!")

if __name__ == "__main__":
    cacar_apostas()