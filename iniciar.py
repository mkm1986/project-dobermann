import os
import sys
import subprocess

def limpar_tela():
    os.system('cls' if os.name == 'nt' else 'clear')

def rodar(script):
    subprocess.run([sys.executable, script])

def fluxo_diario():
    limpar_tela()
    print("=" * 65)
    print(" 🌅 FLUXO DIÁRIO AUTOMÁTICO")
    print("=" * 65)
    print("\nEssa rotina executa em sequência:")
    print("  1. Atualiza banco de dados (coletor.py)")
    print("  2. Liquida apostas anteriores (liquidar.py)")
    print("  3. Caça novas apostas do dia (paper.py)")
    print("  4. Exibe relatório de performance (relatorio.py)")
    print()
    confirma = input("Iniciar fluxo diário? (S/N): ").strip().upper()
    if confirma != 'S':
        return

    limpar_tela()
    print("=" * 65)
    print("PASSO 1/4 — Atualizando banco de dados...")
    print("=" * 65)
    rodar("coletor.py")
    input("\n✅ Banco atualizado. Pressione [ENTER] para continuar...")

    limpar_tela()
    print("=" * 65)
    print("PASSO 2/4 — Liquidando apostas anteriores...")
    print("=" * 65)
    rodar("liquidar.py")
    input("\n✅ Liquidação concluída. Pressione [ENTER] para continuar...")

    limpar_tela()
    print("=" * 65)
    print("PASSO 3/4 — Caçando apostas do dia...")
    print("=" * 65)
    rodar("paper.py")
    input("\n✅ Caça concluída. Pressione [ENTER] para continuar...")

    limpar_tela()
    print("=" * 65)
    print("PASSO 4/4 — Relatório de performance...")
    print("=" * 65)
    rodar("relatorio.py")
    input("\n✅ Relatório gerado. Pressione [ENTER] para voltar ao menu...")

def painel_de_controle():
    while True:
        limpar_tela()
        print("=" * 65)
        print(" 🚀 PAINEL DE CONTROLE - FUNDO QUANTITATIVO DE APOSTAS 🚀")
        print("=" * 65)
        print()
        print(" [1] 🌅 FLUXO DIÁRIO (Recomendado — roda tudo em sequência)")
        print()
        print(" [2] 🤖 Caçar apostas agora (paper.py)")
        print(" [3] 🔄 Liquidar resultados (liquidar.py)")
        print(" [4] ✍️  Liquidar manualmente (liquidar_manual.py)")
        print(" [5] 📈 Ver relatório (relatorio.py)")
        print(" [6] 📋 Ver pendentes (ver_pendentes.py)")
        print(" [7] 🔄 Atualizar banco (coletor.py)")
        print(" [8] 🔍 Investigar time (investigar.py)")
        print(" [9] 📝 Registrar aposta manual (registrar_manual.py)")
        print()
        print(" [0] ❌ Sair")
        print("-" * 65)

        opcao = input("👉 Digite o número da opção: ").strip()

        acoes = {
            '1': fluxo_diario,
            '2': lambda: rodar("paper.py"),
            '3': lambda: rodar("liquidar.py"),
            '4': lambda: rodar("liquidar_manual.py"),
            '5': lambda: rodar("relatorio.py"),
            '6': lambda: rodar("ver_pendentes.py"),
            '7': lambda: rodar("coletor.py"),
            '8': lambda: rodar("investigar.py"),
            '9': lambda: rodar("registrar_manual.py"),
        }

        if opcao == '0':
            limpar_tela()
            print("🏁 Sistema encerrado. Até a próxima sessão!")
            break
        elif opcao in acoes:
            if opcao != '1':
                limpar_tela()
                acoes[opcao]()
                input("\nVoltar ao menu? Pressione [ENTER]...")
            else:
                acoes[opcao]()
        else:
            print("\n⚠️ Opção inválida!")
            input("Pressione [ENTER] para continuar...")

if __name__ == "__main__":
    try:
        painel_de_controle()
    except KeyboardInterrupt:
        print("\n\n🏁 Sistema encerrado.")