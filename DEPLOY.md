# Deployment Guide

> **Status**: ✅ **LIVE** — System is deployed and operational.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Frontend      │     │   Backend       │     │   Database      │
│   (Vercel)      │────▶│   (Render)      │────▶│ (InfluxDB Cloud)│
│   React + Vite  │     │   FastAPI       │     │   Time-Series   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

| Component | Technology | Hosting |
|-----------|------------|---------|
| Frontend | React 18 + Vite | Vercel |
| Backend | FastAPI + Uvicorn + Docker | Render |
| Database | InfluxDB 2.x | InfluxDB Cloud (AWS us-east-1) |

---

## 🚀 Live Links

| Service | URL | Status |
|---------|-----|--------|
| **Frontend** | https://predictive-maintenance-ten.vercel.app/ | ✅ Live |
| **Backend API** | https://predictive-maintenance-uhlb.onrender.com | ✅ Live |
| **API Docs** | https://predictive-maintenance-uhlb.onrender.com/docs | ✅ Live |
| **Health Check** | https://predictive-maintenance-uhlb.onrender.com/health | ✅ Live |

---

## Deployment Instructions

### Backend (Render)

Already deployed at `https://predictive-maintenance-uhlb.onrender.com`

**Environment Variables (configured in Render Dashboard):**
```
ENVIRONMENT=production
PORT=8000
INFLUX_URL=https://us-east-1-1.aws.cloud2.influxdata.com
INFLUX_TOKEN=<your-token>
INFLUX_ORG=<your-org-id>
INFLUX_BUCKET=sensor_data
```

### Frontend (Vercel)

1. **Connect Repository:**
   - Go to [vercel.com](https://vercel.com)
   - Import the GitHub repository
   - Set **Root Directory** to `frontend`

2. **Build Settings:**
   - Framework: Vite
   - Build Command: `npm run build`
   - Output Directory: `dist`

3. **Deploy:**
   - Click "Deploy"
   - Vercel will auto-configure rewrites from `vercel.json`

---

## Local Development

### Quick Start (Docker)

```bash
# Start all services
docker-compose up --build

# Access
# Frontend: http://localhost:5173
# Backend:  http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Manual Setup

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.api.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/system/calibrate` | POST | Start calibration |
| `/system/inject-fault` | POST | Inject fault (severity: mild/medium/severe) |
| `/system/reset` | POST | Reset to idle |
| `/api/v1/status/{asset_id}` | GET | Get asset status |
| `/api/v1/report/{asset_id}` | GET | Generate PDF report |

---

## Environment Variables Reference

### Backend (Render Dashboard)

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `ENVIRONMENT` | Yes | Runtime mode | `production` |
| `PORT` | Yes | Server port | `8000` |
| `INFLUX_URL` | Yes | InfluxDB Cloud URL | `https://us-east-1-1.aws.cloud2.influxdata.com` |
| `INFLUX_TOKEN` | Yes | InfluxDB API token | `kg2i8Mq...` |
| `INFLUX_ORG` | Yes | InfluxDB Organization ID | `67c4314d97304c09` |
| `INFLUX_BUCKET` | Yes | InfluxDB bucket name | `sensor_data` |

### Frontend (Vercel)

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `VITE_API_URL` | No | Backend URL (handled via rewrites) | `https://predictive-maintenance-uhlb.onrender.com` |

---

## Vercel Rewrites Configuration

The `frontend/vercel.json` file handles API proxying:

```json
{
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://predictive-maintenance-uhlb.onrender.com/api/:path*"
    },
    {
      "source": "/system/:path*",
      "destination": "https://predictive-maintenance-uhlb.onrender.com/system/:path*"
    },
    {
      "source": "/health",
      "destination": "https://predictive-maintenance-uhlb.onrender.com/health"
    }
  ]
}
```

This allows the frontend to call `/api/...` and have Vercel proxy to Render automatically.

---

## Monitoring

- **InfluxDB Dashboard:** https://cloud2.influxdata.com
- **Render Logs:** Render Dashboard → Service → Logs
- **Vercel Logs:** Vercel Dashboard → Project → Functions

---

## ⚠️ Common Pitfalls

### Windows Pitfall: node_modules in Git

**Problem**: Committing `node_modules/` from Windows uploads Windows-specific binaries (`.cmd`, `.exe`). When Vercel (Linux) tries to execute these, you get:

```
Error: Command "npm run build" exited with 126
```

**Solution**:
1. Ensure `node_modules/` is in `.gitignore`
2. If already committed, remove with:
   ```bash
   git rm -r --cached frontend/node_modules
   git commit -m "fix: remove node_modules from tracking"
   git push
   ```
3. Redeploy on Vercel

### Render Cold Starts

Free-tier Render services spin down after 15 minutes of inactivity. First request after idle may take 30-60 seconds.

### InfluxDB Token Scope

Ensure your InfluxDB token has **read/write** access to the `sensor_data` bucket.

---

## Troubleshooting

### Backend not responding
```bash
curl https://predictive-maintenance-uhlb.onrender.com/health
```
Expected: `{"status":"healthy","database":"connected",...}`

### Frontend API errors
- Check browser DevTools → Network tab
- Verify Vercel rewrites are working (requests to `/api/*` should proxy to Render)

### InfluxDB connection issues
- Verify credentials in Render environment variables
- Check InfluxDB Cloud dashboard for bucket access
