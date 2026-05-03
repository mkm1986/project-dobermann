import sqlite3
import config
import modelo

def calcular_kelly(prob_vitoria, odd, fracao_kelly):
    prob_derrota = 1 - prob_vitoria
    lucro_potencial = odd - 1
    kelly_puro = ((lucro_potencial * prob_vitoria) - prob_derrota) / lucro_potencial
    return max(0, kelly_puro * fracao_kelly)

def executar_backtest_v2():
    conn = sqlite3.connect(config.DATABASE_PATH)
    c = conn.cursor()

    # Puxamos agora as Odds Máximas (Max) e Médias (Avg) do mercado
    c.execute("""
        SELECT liga_nome, time_casa, time_fora, gols_casa, gols_fora, 
               odd_max_casa, odd_max_fora, odd_pin_casa, odd_pin_fora 
        FROM partidas 
        ORDER BY id ASC
    """)
    jogos = c.fetchall()

    elos = {}
    jogos_disputados = {}

    banca_inicial = 1000.0
    banca_atual = banca_inicial
    total_apostas = 0
    vitorias = 0
    soma_odds_pagas = 0

    print(f"🔬 BACKTESTING V2: Simulando caça às melhores Odds do mercado...")
    
    for liga, casa, fora, gols_c, gols_f, max_c, max_f, pin_c, pin_f in jogos:
        # Inicialização de ELO
        if casa not in elos: elos[casa] = 1500; jogos_disputados[casa] = 0
        if fora not in elos: elos[fora] = 1500; jogos_disputados[fora] = 0

        elo_c = elos[casa]
        elo_f = elos[fora]

        # SÓ APOSTA SE TIVERMOS DADOS E HISTÓRICO MÍNIMO
        if jogos_disputados[casa] >= config.MIN_JOGOS_HISTORICO and jogos_disputados[fora] >= config.MIN_JOGOS_HISTORICO:
            
            # Focaremos na Zebra de Fora (Underdog) usando as Odds Máximas
            if max_f and pin_f:
                # Probabilidade do modelo (com bônus de casa)
                prob_f_modelo = modelo.probabilidade_esperada(elo_f, elo_c + modelo.HOME_ADVANTAGE)
                
                # Se a odd máxima for de Underdog e tiver valor (+EV)
                if config.MIN_ODD_ML <= max_f <= config.MAX_ODD:
                    ev_f = (prob_f_modelo * max_f) - 1
                    
                    if ev_f >= 0.02: # Baixamos a exigência para 2% de vantagem (Edge)
                        aposta_k = calcular_kelly(prob_f_modelo, max_f, config.KELLY_FRACAO)
                        
                        if aposta_k > 0:
                            valor = 10.0  # Aposta Fixa de R$ 10 em todas as entradas!
                            banca_atual -= valor
                            total_apostas += 1
                            soma_odds_pagas += max_f
                            
                            if gols_f > gols_c:
                                banca_atual += (valor * max_f)
                                vitorias += 1

        # ATUALIZAÇÃO DO ELO (Pós-Jogo)
        exp_c = modelo.probabilidade_esperada(elo_c + modelo.HOME_ADVANTAGE, elo_f)
        exp_f = modelo.probabilidade_esperada(elo_f, elo_c + modelo.HOME_ADVANTAGE)
        res_c, res_f = (1, 0) if gols_c > gols_f else (0, 1) if gols_f > gols_c else (0.5, 0.5)
        mov = modelo.multiplicador_margem_vitoria(gols_c, gols_f)
        
        elos[casa] = elo_c + (modelo.K_BASE * mov * (res_c - exp_c))
        elos[fora] = elo_f + (modelo.K_BASE * mov * (res_f - exp_f))
        jogos_disputados[casa] += 1
        jogos_disputados[fora] += 1

    conn.close()

    # RELATÓRIO FINAL
    print("-" * 45)
    print(f"Entradas: {total_apostas}")
    if total_apostas > 0:
        print(f"Taxa de Acerto: {(vitorias/total_apostas)*100:.2f}%")
        print(f"Odd Média das Entradas: {soma_odds_pagas/total_apostas:.2f}")
    print(f"Banca Final: R$ {banca_atual:.2f}")
    print(f"ROI: {((banca_atual - banca_inicial)/banca_inicial)*100:.2f}%")

if __name__ == "__main__":
    executar_backtest_v2()