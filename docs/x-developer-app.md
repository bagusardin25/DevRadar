# X (Twitter) Developer App — field values for this repo

Use these URLs when configuring the X Developer Portal app for **local** DevRadar / xurl MCP.

**Repository:** https://github.com/bagusardin25/DevRadar

| Field | Value |
|---|---|
| **Callback URI / Redirect URL** | `http://127.0.0.1:8080/callback` |
| **Website URL** | `https://github.com/bagusardin25/DevRadar` |
| **Organization name** | `DevRadar` |
| **Organization URL** | `https://github.com/bagusardin25/DevRadar` |
| **Terms of Service** | `https://github.com/bagusardin25/DevRadar/blob/main/docs/terms.md` |
| **Privacy Policy** | `https://github.com/bagusardin25/DevRadar/blob/main/docs/privacy.md` |

### Notes

- Do **not** use `localhost` in Callback; use `127.0.0.1`.  
- No production deploy is required for these GitHub HTTPS links.  
- After save: enable OAuth 2.0, copy **Client ID / Client Secret**, set user env `X_CLIENT_ID` / `X_CLIENT_SECRET`, and optionally `REDIRECT_URI=http://127.0.0.1:8080/callback`.  
- App-only **Bearer Token** → `X_BEARER_TOKEN` in local `backend/.env` (never commit).  
- Never paste secrets into git or chat.

See also: [manual X collection](./manual-x-collection.md) (on `backend` branch until merged).
