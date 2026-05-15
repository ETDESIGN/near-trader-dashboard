# Netlify Deployment — NEAR Trader Dashboard

## Option A: Drag & Drop (Fastest, 2 minutes)

1. Go to [app.netlify.com](https://app.netlify.com/)
2. Log in or create a free account
3. Drag the entire `near-trader-dashboard/` folder onto the deploy drop zone
4. Done — Netlify gives you a live URL instantly

## Option B: Git Deploy (Recommended — auto-deploys on push)

1. Go to [app.netlify.com](https://app.netlify.com/) → **Add new site** → **Import an existing project**
2. Connect GitHub → select **ETDESIGN/near-trader-dashboard**
3. Settings:
   - **Branch:** `master` (or `gh-pages`)
   - **Build command:** leave empty (static site)
   - **Publish directory:** `/` (root)
4. Click **Deploy site**
5. Every `git push` to master will auto-deploy

## Option C: Netlify CLI

```bash
# Install CLI
npm install -g netlify-cli

# Login
netlify login

# Deploy from project directory
cd near-trader-dashboard
netlify init    # Follow prompts (static site, no build)
netlify deploy --prod
```

## Custom Domain (Optional)

1. In Netlify dashboard → **Site settings** → **Domain management**
2. Add custom domain (e.g., `trader.estudio.com`)
3. Update DNS records as instructed

## Notes
- `data.json` updates must be pushed to GitHub (for Git deploy) or re-deployed (for drag & drop)
- CoinGecko API is called client-side — no server needed
- Free tier: 100GB bandwidth/month (plenty for this dashboard)
