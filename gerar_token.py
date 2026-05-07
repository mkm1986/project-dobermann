from google_auth_oauthlib.flow import InstalledAppFlow
import json

SCOPES = ["https://www.googleapis.com/auth/drive"]
ARQUIVO_SECRET = "client_secret_265189955400-drdkvkvq8npg8i9i4tq77uqs9m43fqaq.apps.googleusercontent.com.json"

flow = InstalledAppFlow.from_client_secrets_file(ARQUIVO_SECRET, SCOPES)
creds = flow.run_local_server(port=0)

# Salva o token
token = {
    "token":         creds.token,
    "refresh_token": creds.refresh_token,
    "token_uri":     creds.token_uri,
    "client_id":     creds.client_id,
    "client_secret": creds.client_secret,
    "scopes":        creds.scopes,
}

with open("token_drive.json", "w") as f:
    json.dump(token, f, indent=2)

print("✅ Token salvo em token_drive.json")
print(f"Refresh token: {creds.refresh_token[:20]}...")