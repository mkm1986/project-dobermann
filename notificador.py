import requests
import config

def enviar(mensagem):
    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text":    mensagem,
        "parse_mode": "HTML"
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 429:
            # Rate limit — aguarda e tenta novamente
            import time
            retry = resp.json().get("parameters", {}).get("retry_after", 5)
            print(f"⚠️ Rate limit Telegram — aguardando {retry}s")
            time.sleep(retry + 1)
            resp = requests.post(url, json=payload, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        print(f"⚠️ Erro ao enviar notificação: {e}")
        return False

def notificar_sinal(sinal, valor):
    msg = (
        f"🚨 <b>SINAL ENCONTRADO</b>\n\n"
        f"⚽ {sinal['home']} x {sinal['away']}\n"
        f"🏆 {sinal['liga']}\n"
        f"📊 Aposta: <b>{sinal['bet_side']}</b> @ <b>{sinal['odd']:.2f}</b>\n"
        f"📈 EV: <b>{sinal['ev_api']:.2%}</b>\n"
        f"💰 Valor sugerido: <b>R$ {valor:.2f}</b>\n"
        f"🔗 <a href='{sinal['href']}'>Abrir aposta</a>"
    )
    return enviar(msg)

def notificar_resumo(apostas_salvas, apostas_ignoradas):
    if apostas_salvas == 0:
        msg = "😴 <b>Nenhum sinal encontrado</b> nas ligas alvo no momento."
    else:
        msg = (
            f"✅ <b>Resumo da caçada</b>\n\n"
            f"🎯 {apostas_salvas} sinal(is) encontrado(s)\n"
            f"❌ {apostas_ignoradas} ignorado(s)\n\n"
            f"Verifique os links e faça as entradas!"
        )
    return enviar(msg)

def notificar_liquidacao(casa, fora, gc, gf, aposta_em, status, lucro):
    icone = "✅" if status == "Ganhou" else "❌"
    msg = (
        f"{icone} <b>Aposta liquidada</b>\n\n"
        f"⚽ {casa} {gc}x{gf} {fora}\n"
        f"📊 Apostou em: <b>{aposta_em}</b>\n"
        f"💰 Resultado: <b>R$ {lucro:+.2f}</b>"
    )
    return enviar(msg)

if __name__ == "__main__":
    ok = enviar("🤖 Bot de apostas conectado com sucesso!")
    print("✅ Mensagem enviada!" if ok else "❌ Erro ao enviar")