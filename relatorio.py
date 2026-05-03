import sqlite3
import config

def calcular_metricas(apostas):
    total = len(apostas)
    if total == 0:
        return 0, 0, 0, 0.0, 0.0, 0.0, 0.0
        
    vitorias = sum(1 for a in apostas if a['status'] == 'Ganhou')
    derrotas = sum(1 for a in apostas if a['status'] == 'Perdeu')
    investido = sum(a['valor'] for a in apostas)
    lucro = sum(a['lucro'] for a in apostas)
    
    win_rate = (vitorias / total) * 100 if total > 0 else 0
    roi = (lucro / investido) * 100 if investido > 0 else 0
    
    return total, vitorias, derrotas, investido, lucro, win_rate, roi

def gerar_relatorio():
    conn = sqlite3.connect(config.DATABASE_PATH)
    c = conn.cursor()
    
    c.execute("""
        SELECT id, time_casa, time_fora, aposta_em, odd_aposta, valor_aposta, status, lucro, data_jogo 
        FROM paper_bets 
        WHERE status != 'Pendente' 
        ORDER BY id DESC
    """)
    resultados = c.fetchall()
    
    if not resultados:
        print("📭 Nenhuma aposta foi liquidada (finalizada) ainda.")
        conn.close()
        return

    apostas_modelo = []
    apostas_manuais = []
    
    for linha in resultados:
        id_db, casa, fora, aposta, odd, valor, status, lucro, data_jogo = linha
        
        aposta_dict = {
            'id': id_db, 'casa': casa, 'fora': fora, 'aposta': aposta,
            'odd': odd, 'valor': valor, 'status': status, 'lucro': lucro,
            'origem': '🧠 Você' if data_jogo == 'Manual' else '🤖 Robô'
        }
        
        if data_jogo == 'Manual':
            apostas_manuais.append(aposta_dict)
        else:
            apostas_modelo.append(aposta_dict)

    # Calculando as métricas para cada grupo
    t_mod, v_mod, d_mod, inv_mod, luc_mod, wr_mod, roi_mod = calcular_metricas(apostas_modelo)
    t_man, v_man, d_man, inv_man, luc_man, wr_man, roi_man = calcular_metricas(apostas_manuais)
    t_ger, v_ger, d_ger, inv_ger, luc_ger, wr_ger, roi_ger = calcular_metricas(apostas_modelo + apostas_manuais)

    print("\n" + "="*55)
    print("📈 DASHBOARD DE PERFORMANCE (PAPER BETTING) 📈")
    print("="*55)

    # --- BLOCO 1: O ROBÔ ---
    print("\n🤖 PERFORMANCE DO MODELO QUANTITATIVO")
    print("-" * 55)
    if t_mod > 0:
        print(f"Apostas Finalizadas : {t_mod}")
        print(f"Placar              : {v_mod} ✅ / {d_mod} ❌ (Win Rate: {wr_mod:.1f}%)")
        lucro_str = f"+ R$ {luc_mod:.2f}" if luc_mod >= 0 else f"- R$ {abs(luc_mod):.2f}"
        print(f"Lucro Líquido       : {lucro_str}")
        print(f"ROI (Retorno)       : {roi_mod:.2f}%")
    else:
        print("Ainda não há apostas liquidadas para o Modelo.")

    # --- BLOCO 2: VOCÊ ---
    print("\n🧠 PERFORMANCE MANUAL (SUAS LEITURAS)")
    print("-" * 55)
    if t_man > 0:
        print(f"Apostas Finalizadas : {t_man}")
        print(f"Placar              : {v_man} ✅ / {d_man} ❌ (Win Rate: {wr_man:.1f}%)")
        lucro_str = f"+ R$ {luc_man:.2f}" if luc_man >= 0 else f"- R$ {abs(luc_man):.2f}"
        print(f"Lucro Líquido       : {lucro_str}")
        print(f"ROI (Retorno)       : {roi_man:.2f}%")
    else:
        print("Ainda não há apostas manuais liquidadas.")

    # --- BLOCO 3: GERAL ---
    print("\n🌍 PERFORMANCE GERAL (CONSOLIDADO)")
    print("-" * 55)
    print(f"Total de Apostas    : {t_ger}")
    lucro_str = f"+ R$ {luc_ger:.2f}" if luc_ger >= 0 else f"- R$ {abs(luc_ger):.2f}"
    print(f"LUCRO TOTAL         : {lucro_str}")
    print(f"ROI GERAL           : {roi_ger:.2f}%\n")
    print("="*55)

    # --- HISTÓRICO ---
    print("\n📝 HISTÓRICO RECENTE (Últimas 10 liquidadas):")
    todas_apostas = apostas_manuais + apostas_modelo
    # Reordenando por ID decrescente para pegar as mais recentes no geral
    todas_apostas.sort(key=lambda x: x['id'], reverse=True)
    
    for u in todas_apostas[:10]:
        icone = "✅" if u['status'] == 'Ganhou' else "❌"
        sinal_lucro = "+" if u['lucro'] > 0 else ""
        print(f"{icone} {u['origem']} | ID {u['id']:<2} | {u['casa']} x {u['fora']} -> R$ {sinal_lucro}{u['lucro']:.2f}")
        
    conn.close()

if __name__ == "__main__":
    gerar_relatorio()