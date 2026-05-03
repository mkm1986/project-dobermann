import sqlite3
import math
from scipy.optimize import minimize
from scipy.stats import poisson
import numpy as np
import config

# =============================================================
# PARÂMETROS ELO
# =============================================================
K_BASE         = 20
HOME_ADVANTAGE = 80
ELO_INICIAL    = 1500
FATOR_REGRESSAO = 0.3

# =============================================================
# ELO — funções base
# =============================================================

def probabilidade_esperada(elo_a, elo_b):
    return 1 / (1 + math.pow(10, (elo_b - elo_a) / 400))

def multiplicador_margem_vitoria(gols_casa, gols_fora):
    diferenca = abs(gols_casa - gols_fora)
    if diferenca <= 1:   return 1.0
    elif diferenca == 2: return 1.5
    else:                return (11 + diferenca) / 8.0

def regredir_para_media(elos):
    for time in elos:
        elos[time] = elos[time] + FATOR_REGRESSAO * (ELO_INICIAL - elos[time])
    return elos

# =============================================================
# DIXON-COLES — funções
# =============================================================

def tau(x, y, lambda_h, lambda_a, rho):
    """Fator de correção Dixon-Coles para placares baixos."""
    if x == 0 and y == 0:
        return 1 - lambda_h * lambda_a * rho
    elif x == 0 and y == 1:
        return 1 + lambda_h * rho
    elif x == 1 and y == 0:
        return 1 + lambda_a * rho
    elif x == 1 and y == 1:
        return 1 - rho
    else:
        return 1.0

def probabilidade_placar(x, y, lambda_h, lambda_a, rho):
    """Probabilidade de um placar específico x x y."""
    prob = (poisson.pmf(x, lambda_h) *
            poisson.pmf(y, lambda_a) *
            tau(x, y, lambda_h, lambda_a, rho))
    return max(prob, 1e-10)

def calcular_probabilidades_dc(lambda_h, lambda_a, rho, max_gols=8):
    """
    Calcula P(vitória casa), P(empate), P(vitória fora)
    somando a matriz de placares até max_gols.
    """
    p_casa = p_emp = p_fora = 0.0
    for x in range(max_gols + 1):
        for y in range(max_gols + 1):
            p = probabilidade_placar(x, y, lambda_h, lambda_a, rho)
            if x > y:   p_casa += p
            elif x == y: p_emp  += p
            else:        p_fora += p
    total = p_casa + p_emp + p_fora
    return p_casa / total, p_emp / total, p_fora / total

def neg_log_likelihood(params, jogos):
    """Função de custo para otimização dos parâmetros Dixon-Coles."""
    rho = params[0]
    if rho < -1 or rho > 1:
        return 1e10

    total = 0.0
    for lambda_h, lambda_a, gols_c, gols_f in jogos:
        p = probabilidade_placar(gols_c, gols_f, lambda_h, lambda_a, rho)
        total -= math.log(max(p, 1e-10))
    return total

def calibrar_rho(jogos_dc):
    """Otimiza o parâmetro rho com os dados históricos."""
    resultado = minimize(
        neg_log_likelihood,
        x0=[0.0],
        args=(jogos_dc,),
        method="Nelder-Mead",
        options={"maxiter": 1000}
    )
    return resultado.x[0]

# =============================================================
# TREINAMENTO COMPLETO
# =============================================================

def treinar_modelo():
    conn = sqlite3.connect(config.DATABASE_PATH)
    c = conn.cursor()

    c.execute("""
        SELECT temporada, liga_nome, time_casa, time_fora,
               gols_casa, gols_fora
        FROM partidas
        ORDER BY temporada ASC, id ASC
    """)
    jogos = c.fetchall()
    conn.close()

    elos          = {}
    jogos_por_time = {}
    temporada_atual = None

    # Dados para calibrar Dixon-Coles
    jogos_dc = []

    print(f"🧠 Treinamento ELO + Dixon-Coles em {len(jogos)} partidas...")

    for temporada, liga, time_casa, time_fora, gols_casa, gols_fora in jogos:

        if temporada != temporada_atual:
            if temporada_atual is not None:
                elos = regredir_para_media(elos)
            temporada_atual = temporada
            jogos_por_time  = {}

        if time_casa not in elos:       elos[time_casa] = ELO_INICIAL
        if time_casa not in jogos_por_time: jogos_por_time[time_casa] = 0
        if time_fora not in elos:       elos[time_fora] = ELO_INICIAL
        if time_fora not in jogos_por_time: jogos_por_time[time_fora] = 0

        elo_c = elos[time_casa]
        elo_f = elos[time_fora]
        elo_c_ajustado = elo_c + HOME_ADVANTAGE

        # Gols esperados para Dixon-Coles
        # Usamos o ELO para estimar λ (força ofensiva relativa)
        forca_relativa_c = probabilidade_esperada(elo_c_ajustado, elo_f)
        forca_relativa_f = probabilidade_esperada(elo_f, elo_c_ajustado)

        # Média de gols do banco como base
        MEDIA_GOLS = 1.35
        lambda_h = MEDIA_GOLS * 2 * forca_relativa_c
        lambda_a = MEDIA_GOLS * 2 * forca_relativa_f

        jogos_dc.append((lambda_h, lambda_a, gols_casa, gols_fora))

        # Atualização ELO
        if gols_casa > gols_fora:   res_c, res_f = 1, 0
        elif gols_casa < gols_fora: res_c, res_f = 0, 1
        else:                        res_c, res_f = 0.5, 0.5

        exp_c = probabilidade_esperada(elo_c_ajustado, elo_f)
        exp_f = probabilidade_esperada(elo_f, elo_c_ajustado)
        mov   = multiplicador_margem_vitoria(gols_casa, gols_fora)

        elos[time_casa] = elo_c + (K_BASE * mov * (res_c - exp_c))
        elos[time_fora] = elo_f + (K_BASE * mov * (res_f - exp_f))
        jogos_por_time[time_casa] += 1
        jogos_por_time[time_fora] += 1

    # Calibra rho com todos os dados históricos
    print("⚙️  Calibrando parâmetro rho (Dixon-Coles)...")
    rho = calibrar_rho(jogos_dc)
    print(f"✅ rho calibrado: {rho:.4f}")

    print("\n🏆 TOP 10 (ELO com reset por temporada):")
    print("-" * 45)
    times_ordenados = sorted(elos.items(), key=lambda x: x[1], reverse=True)
    for i in range(min(10, len(times_ordenados))):
        time, pontuacao = times_ordenados[i]
        jogos_t = jogos_por_time.get(time, 0)
        print(f"{i+1}º | {time.ljust(20)} | Força: {pontuacao:.2f} | Jogos: {jogos_t}")

    return elos, jogos_por_time, rho

def probabilidade_jogo(elo_casa, elo_fora, rho, home_advantage=HOME_ADVANTAGE):
    """
    Calcula P(vitória casa), P(empate), P(vitória fora)
    usando Dixon-Coles calibrado.
    """
    elo_c_ajustado = elo_casa + home_advantage
    fc = probabilidade_esperada(elo_c_ajustado, elo_fora)
    ff = probabilidade_esperada(elo_fora, elo_c_ajustado)

    MEDIA_GOLS = 1.35
    lambda_h = MEDIA_GOLS * 2 * fc
    lambda_a = MEDIA_GOLS * 2 * ff

    return calcular_probabilidades_dc(lambda_h, lambda_a, rho)

if __name__ == "__main__":
    elos, jogos_por_time, rho = treinar_modelo()
    print(f"\nrho final: {rho:.4f}")