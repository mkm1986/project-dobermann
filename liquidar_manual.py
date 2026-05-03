import sqlite3
import config

def liquidar_na_mao():
    conn = sqlite3.connect(config.DATABASE_PATH)
    c = conn.cursor()
    
    while True:
        # Puxa os pendentes atualizados a cada rodada
        c.execute("SELECT id, time_casa, time_fora, aposta_em, valor_aposta, odd_aposta FROM paper_bets WHERE status = 'Pendente'")
        pendentes = c.fetchall()
        
        if not pendentes:
            print("\n🎉 Todas as apostas foram liquidadas! Não há mais pendências.")
            break

        print("\n" + "="*45)
        print("📋 APOSTAS PENDENTES:")
        for p in pendentes:
            print(f"ID: {p[0]:<3} | {p[1]} x {p[2]} | Aposta: {p[3]}")
            
        print("-" * 45)
        
        try:
            escolha_id = int(input("\nDigite o ID para liquidar (ou 0 para sair): "))
            
            if escolha_id == 0:
                print("Saindo do liquidador manual...")
                break
            
            # Acha a aposta escolhida na lista atual
            aposta_alvo = next((p for p in pendentes if p[0] == escolha_id), None)
            
            if not aposta_alvo:
                print("❌ ID não encontrado. Tente novamente.")
                continue
                
            resultado = input("A aposta foi G (Ganhou) ou P (Perdeu)? ").strip().upper()
            
            valor = aposta_alvo[4]
            odd = aposta_alvo[5]
            
            if resultado == 'G':
                lucro = valor * (odd - 1)
                status = "Ganhou"
            elif resultado == 'P':
                lucro = -valor
                status = "Perdeu"
            else:
                print("❌ Opção inválida. Digite apenas G ou P.")
                continue

            # Confirmação antes de salvar
            print(f"\n⚠️  CONFIRMAR: Aposta {escolha_id} → {status} | Lucro: R$ {lucro:.2f}")
            confirma = input("Confirma? (S/N): ").strip().upper()
            if confirma != 'S':
                print("↩️  Cancelado — nenhuma alteração feita.")
                continue

            c.execute("UPDATE paper_bets SET status = ?, lucro = ? WHERE id = ?", (status, lucro, escolha_id))
            conn.commit()
            print(f"✅ Aposta {escolha_id} atualizada para {status}! Lucro: R$ {lucro:.2f}")
            
        except ValueError:
            print("❌ Digite apenas números válidos para o ID.")
            
    conn.close()

if __name__ == "__main__":
    liquidar_na_mao()