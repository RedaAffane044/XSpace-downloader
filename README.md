# 🎙️ Space Downloader — Team Version

A simple web app your team can use to download Twitter/X Spaces.  
**No installs needed** — just a URL they visit in their browser.

---

## 🚀 Deploy in 5 Minutes (Railway — Free)

### Step 1: Get the files ready

You need these 3 files (all included):
- `app.py`
- `requirements.txt`  
- `Dockerfile`

### Step 2: Create a GitHub repo

1. Go to [github.com/new](https://github.com/new)
2. Name it `space-downloader`
3. Click **Create repository**
4. Upload the 3 files (drag & drop)

### Step 3: Deploy to Railway

1. Go to [railway.app](https://railway.app) and sign in with GitHub
2. Click **New Project** → **Deploy from GitHub repo**
3. Select your `space-downloader` repo
4. Railway will auto-detect the Dockerfile and deploy
5. Click **Settings** → **Generate Domain** to get your URL

### Step 4: Share with your team!

Send them the Railway URL (something like `space-downloader-xyz.up.railway.app`)

They just:
1. Open the link
2. Paste a Space URL
3. Click Download

---

## 🔄 Alternative: Deploy to Render (Also Free)

1. Go to [render.com](https://render.com) and sign up
2. Click **New** → **Web Service**
3. Connect your GitHub repo
4. Set:
   - **Environment:** Docker
   - **Plan:** Free
5. Click **Create Web Service**
6. Wait for deploy, then share the URL

---

## 📝 Notes

- **Free tier limits:** Railway gives 500 hours/month, Render gives 750 hours/month
- **Long Spaces:** Downloads might take 1-3 minutes for hour-long recordings
- **Not all Spaces work:** Host must have enabled recording, and it expires after 30 days

---

## 🛠️ Local Testing (Optional)

If you want to test locally first:

```bash
pip install flask yt-dlp
python app.py
```

Then open `http://localhost:5000`

---

Made with ❤️ for easy Space downloading
