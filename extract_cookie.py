import base64
import json
import subprocess
from pathlib import Path

# run opendevbrowser cookie-list
result = subprocess.run(
    [
        "npx",
        "opendevbrowser",
        "cookie-list",
        "--session-id",
        "37dabd73-5c30-40d3-bd68-6d5b17327082",
        "--url",
        "https://mobbin.com",
        "--output-format",
        "json",
    ],
    capture_output=True,
    text=True,
)
data = json.loads(result.stdout)
cookies = data.get("data", {}).get("cookies", [])

auth_token_0 = next((c["value"] for c in cookies if c["name"] == "sb-ujasntkfphywizsdaapi-auth-token.0"), None)
auth_token_1 = next((c["value"] for c in cookies if c["name"] == "sb-ujasntkfphywizsdaapi-auth-token.1"), None)

if auth_token_0 and auth_token_1:
    combined = auth_token_0.replace("base64-", "") + auth_token_1
    try:
        decoded = base64.b64decode(combined).decode("utf-8")
        token_data = json.loads(decoded)
        access_token = token_data.get("access_token")

        if access_token:
            AUTH_FILE = Path("/home/ubuntu/.local/share/opencode/mcp-auth.json")
            if AUTH_FILE.exists():
                auth_data = json.loads(AUTH_FILE.read_text())
            else:
                auth_data = {"mobbin": {"tokens": {}}}

            auth_data["mobbin"]["tokens"]["accessToken"] = access_token
            AUTH_FILE.write_text(json.dumps(auth_data, indent=2))
            print("Successfully extracted JWT from OpenDevBrowser and updated mcp-auth.json!")
    except Exception as e:
        print(f"Error decoding: {e}")

elif next((c for c in cookies if c["name"] == "mobbin_jwt"), None):
    jwt = next(c["value"] for c in cookies if c["name"] == "mobbin_jwt")
    AUTH_FILE = Path("/home/ubuntu/.local/share/opencode/mcp-auth.json")
    if AUTH_FILE.exists():
        auth_data = json.loads(AUTH_FILE.read_text())
    else:
        auth_data = {"mobbin": {"tokens": {}}}

    auth_data["mobbin"]["tokens"]["accessToken"] = jwt
    AUTH_FILE.write_text(json.dumps(auth_data, indent=2))
    print("Successfully extracted mobbin_jwt from OpenDevBrowser and updated mcp-auth.json!")
else:
    print("Could not find auth cookies. Please log in on the browser.")
