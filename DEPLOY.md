# Deployment Guide

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
| Backend | FastAPI + Uvicorn | Render |
| Database | InfluxDB 2.x | InfluxDB Cloud |

---

## Live Links

| Service | URL |
|---------|-----|
| **Frontend** | `https://your-app.vercel.app` *(update after deployment)* |
| **Backend API** | https://predictive-maintenance-uhlb.onrender.com |
| **API Docs** | https://predictive-maintenance-uhlb.onrender.com/docs |
| **Health Check** | https://predictive-maintenance-uhlb.onrender.com/health |

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

## Monitoring

- **InfluxDB Dashboard:** https://cloud2.influxdata.com
- **Render Logs:** Render Dashboard → Service → Logs
- **Vercel Logs:** Vercel Dashboard → Project → Functions

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
