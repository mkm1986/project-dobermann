import os
import io
import json
import time
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google.oauth2 import service_account

PASTA_ID = "161T-JwbL9a2kLozkzlrH_b5LfJSawile"
ARQUIVOS = ["apostas.db", "cache_odds.json"]
SCOPES   = ["https://www.googleapis.com/auth/drive"]

def autenticar():
    """
    Autentica via Service Account.
    Lê o arquivo service_account.json gerado pelo workflow
    ou disponível localmente.
    """
    with open("service_account.json") as f:
        info = json.load(f)

    creds = service_account.Credentials.from_service_account_info(
        info, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)

def buscar_arquivo_no_drive(service, nome):
    resultado = service.files().list(
        q=f"name='{nome}' and '{PASTA_ID}' in parents and trashed=false",
        fields="files(id, name, modifiedTime)"
    ).execute()
    arquivos = resultado.get("files", [])
    return arquivos[0] if arquivos else None

def baixar_arquivo(service, nome, forcar=False):
    arquivo = buscar_arquivo_no_drive(service, nome)
    if not arquivo:
        print(f"📭 {nome} não encontrado no Drive.")
        return False

    if not forcar and os.path.exists(nome):
        from datetime import datetime, timezone
        modified_drive = arquivo.get("modifiedTime", "")
        modified_local = os.path.getmtime(nome)
        try:
            dt_drive = datetime.fromisoformat(
                modified_drive.replace("Z", "+00:00")
            ).timestamp()
            if modified_local >= dt_drive:
                print(f"⏭️  {nome} local é mais recente — mantendo versão local.")
                return False
        except:
            pass

    request    = service.files().get_media(fileId=arquivo["id"])
    buffer     = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    with open(nome, "wb") as f:
        f.write(buffer.getvalue())

    print(f"✅ {nome} baixado do Drive.")
    return True

def subir_arquivo(service, nome):
    if not os.path.exists(nome):
        print(f"⚠️ {nome} não encontrado localmente.")
        return False

    arquivo_existente = buscar_arquivo_no_drive(service, nome)
    media = MediaFileUpload(nome, mimetype="application/octet-stream")

    if arquivo_existente:
        service.files().update(
            fileId     = arquivo_existente["id"],
            media_body = media
        ).execute()
    else:
        metadata = {"name": nome, "parents": [PASTA_ID]}
        service.files().create(
            body       = metadata,
            media_body = media,
            fields     = "id"
        ).execute()

    print(f"✅ {nome} salvo no Drive.")
    return True

def sincronizar_antes():
    print("🔄 Sincronizando arquivos do Drive...")
    service = autenticar()
    for nome in ARQUIVOS:
        baixar_arquivo(service, nome)

def sincronizar_depois():
    print("🔄 Salvando arquivos no Drive...")
    service = autenticar()
    for nome in ARQUIVOS:
        subir_arquivo(service, nome)

def sincronizar_forcar_download():
    print("🔄 Forçando download do Drive...")
    service = autenticar()
    for nome in ARQUIVOS:
        baixar_arquivo(service, nome, forcar=True)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "subir":
            sincronizar_depois()
        elif sys.argv[1] == "forcar":
            sincronizar_forcar_download()
    else:
        sincronizar_antes()
