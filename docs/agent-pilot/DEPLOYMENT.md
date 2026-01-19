# Axis Deal Engine - Private Cloud Deployment

Railway deployment guide for the invite-only agent pilot.

---

## Environment Variables

Configure these in Railway's **Variables** tab:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PRODUCTION` | No | Auto-detected | Set to `true` to force production mode |
| `ALLOWED_ORIGINS` | Recommended | None | Comma-separated list of allowed CORS origins (e.g., `https://your-app.up.railway.app`) |
| `DEBUG` | No | `false` | Debug mode. **Ignored in production** |
| `INVITE_TOKENS_PATH` | No | `data/invite_tokens.json` | Path to invite token storage |

**Railway auto-sets:**
- `PORT` - Provided by Railway
- `RAILWAY_ENVIRONMENT` - Triggers production mode detection

---

## Deployment Checklist

### Pre-Deployment (One-Time Setup)

1. **Create Railway Account**
   - Go to [railway.app](https://railway.app)
   - Sign up with GitHub

2. **Create New Project**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Connect your `axis-deal-engine` repository

3. **Configure Environment Variables**
   - Go to your service → **Variables** tab
   - Add: `ALLOWED_ORIGINS` = `https://your-app.up.railway.app`
   - (The exact URL will be assigned after first deploy)

4. **Generate Domain**
   - Go to **Settings** → **Networking**
   - Click "Generate Domain"
   - You'll get something like: `axis-deal-engine-production.up.railway.app`

5. **Update ALLOWED_ORIGINS**
   - Go back to Variables
   - Set `ALLOWED_ORIGINS` to your assigned domain (with `https://`)

### Deploy

Railway auto-deploys on push to `main`. To manually deploy:
- Go to Railway dashboard → your project
- Click "Deploy" or push to `main`

### Post-Deploy Verification

1. **Health Check**
   ```
   https://YOUR-DOMAIN.up.railway.app/api/health
   ```
   Should return:
   ```json
   {"status": "healthy", "version": "0.1.0", "environment": "production"}
   ```

2. **Invite Token Gating (MUST TEST)**
   ```
   https://YOUR-DOMAIN.up.railway.app/submit/
   ```
   Should return **403 Forbidden** (no token = blocked)

3. **Static Files**
   ```
   https://YOUR-DOMAIN.up.railway.app/static/css/style.css
   ```
   Should load CSS (200 OK)

4. **Reports Directory** (if PDFs exist)
   ```
   https://YOUR-DOMAIN.up.railway.app/reports/
   ```
   Should serve files from `/reports/`

5. **Admin Panel** (internal use)
   ```
   https://YOUR-DOMAIN.up.railway.app/submit/admin
   ```
   Accessible (for now - no auth)

---

## Creating Invite Tokens

For the pilot, create invite tokens via the admin API:

```bash
curl -X POST https://YOUR-DOMAIN.up.railway.app/submit/api/admin/invites \
  -F "agent_firm=Savills" \
  -F "agent_email=agent@savills.com" \
  -F "max_uses=10" \
  -F "expires_days=90"
```

Response includes the `invite_url` to share with the agent.

---

## Custom Domain (Later)

To add a custom subdomain like `pilot.axisallocation.com`:

1. **In Railway:**
   - Go to Settings → Networking → Custom Domains
   - Add: `pilot.axisallocation.com`

2. **In Your DNS Provider:**
   - Add a CNAME record:
     - Name: `pilot`
     - Value: `your-app.up.railway.app`

3. **Update ALLOWED_ORIGINS:**
   - Add your custom domain to the comma-separated list:
     ```
     https://pilot.axisallocation.com,https://your-app.up.railway.app
     ```

4. **Wait for SSL:**
   - Railway auto-provisions SSL certificates
   - Takes 5-10 minutes

---

## Security Notes

- **API docs disabled** in production (`/docs`, `/redoc`, `/openapi.json` all return 404)
- **Debug disabled** in production (forced off regardless of env var)
- **CORS locked down** to explicit origins only
- **Invite tokens required** for all submission routes
- **No public marketing pages** - this is a private tool
- **No mock data** - real auction data only

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| 403 on `/submit/` | Working correctly - invite token required |
| CORS errors | Check `ALLOWED_ORIGINS` includes your domain with protocol |
| PDFs not loading | Ensure `/reports/` directory exists and has files |
| Deploy fails | Check Railway logs for Python dependency issues |

---

## Files Changed for Deployment

- `railway.json` - Railway deployment configuration
- `web/app.py` - Production settings (CORS, debug, docs)
