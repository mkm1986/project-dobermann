import os
import io
import json
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google.oauth2.credentials import Credentials

PASTA_ID      = "161T-JwbL9a2kLozkzlrH_b5LfJSawile"
ARQUIVO_DB    = "apostas.db"
NOME_DB_DRIVE = "apostas.db"

def autenticar():
    # GitHub Actions — usa variável de ambiente
    token_json = os.environ.get("GOOGLE_TOKEN")
    if token_json:
        info = json.loads(token_json)
    else:
        # PC local — usa arquivo
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

def buscar_arquivo_no_drive(service):
    resultado = service.files().list(
        q=f"name='{NOME_DB_DRIVE}' and '{PASTA_ID}' in parents and trashed=false",
        fields="files(id, name, modifiedTime)"
    ).execute()
    arquivos = resultado.get("files", [])
    return arquivos[0] if arquivos else None

def baixar_banco(service):
    arquivo = buscar_arquivo_no_drive(service)
    if not arquivo:
        print("📭 Nenhum banco encontrado no Drive — iniciando do zero.")
        return False

    request    = service.files().get_media(fileId=arquivo["id"])
    buffer     = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    with open(ARQUIVO_DB, "wb") as f:
        f.write(buffer.getvalue())

    print(f"✅ Banco baixado do Drive ({arquivo['modifiedTime']})")
    return True

def subir_banco(service):
    if not os.path.exists(ARQUIVO_DB):
        print("⚠️ Banco local não encontrado.")
        return False

    arquivo_existente = buscar_arquivo_no_drive(service)
    media = MediaFileUpload(ARQUIVO_DB, mimetype="application/octet-stream")

    if arquivo_existente:
        service.files().update(
            fileId     = arquivo_existente["id"],
            media_body = media
        ).execute()
        print("✅ Banco atualizado no Drive.")
    else:
        metadata = {"name": NOME_DB_DRIVE, "parents": [PASTA_ID]}
        service.files().create(
            body       = metadata,
            media_body = media,
            fields     = "id"
        ).execute()
        print("✅ Banco criado no Drive.")
    return True

def sincronizar_antes():
    print("🔄 Sincronizando banco do Drive...")
    service = autenticar()
    baixar_banco(service)

def sincronizar_depois():
    print("🔄 Salvando banco no Drive...")
    service = autenticar()
    subir_banco(service)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "subir":
        sincronizar_depois()
    else:
        sincronizar_antes()