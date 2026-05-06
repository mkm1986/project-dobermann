import os
import io
import json
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google.oauth2.credentials import Credentials

PASTA_ID      = "161T-JwbL9a2kLozkzlrH_b5LfJSawile"
ARQUIVOS      = ["apostas.db", "cache_odds.json"]

def autenticar():
    token_json = os.environ.get("GOOGLE_TOKEN")
    if token_json:
        info = json.loads(token_json)
    else:
        with open("token_drive.json") as f:
            info = json.load(f)

    creds = Credentials(
        token         = info.get("token"),
        refresh_token = info.get("refresh_token"),
        token_uri     = info.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id     = info.get("client_id"),
        client_secret = info.get("client_secret"),
        scopes        = info.get("scopes"),
    )
    return build("drive", "v3", credentials=creds)

def buscar_arquivo_no_drive(service, nome):
    resultado = service.files().list(
        q=f"name='{nome}' and '{PASTA_ID}' in parents and trashed=false",
        fields="files(id, name, modifiedTime)"
    ).execute()
    arquivos = resultado.get("files", [])
    return arquivos[0] if arquivos else None

def baixar_arquivo(service, nome):
    arquivo = buscar_arquivo_no_drive(service, nome)
    if not arquivo:
        print(f"📭 {nome} não encontrado no Drive.")
        return False

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

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "subir":
        sincronizar_depois()
    else:
        sincronizar_antes()