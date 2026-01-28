# 🎯 PREDICTIVE MAINTENANCE - DEMO GUIDE
> **Private Demo Manual** - For presentation and demonstration purposes

---

## 📋 PRE-DEMO CHECKLIST

- [ ] Docker Desktop closed (we use local development)
- [ ] 3 PowerShell terminals ready
- [ ] Browser open to `http://localhost:3000`
- [ ] This guide open on phone/second monitor

---

## 🚀 STEP 1: START THE SYSTEM

### Terminal 1: Backend (FastAPI)
```powershell
cd "c:\Users\oumme\OneDrive\Desktop\Predictive Maintenance"
.\venv\Scripts\Activate.ps1
uvicorn backend.api.main:app --port 8000
```
✅ **Expected:** `Uvicorn running on http://127.0.0.1:8000`

### Terminal 2: Frontend (React)
```powershell
cd "c:\Users\oumme\OneDrive\Desktop\Predictive Maintenance\frontend"
npm run dev
```
✅ **Expected:** `VITE ready` with `http://localhost:3000`

### Terminal 3: Data Commands
```powershell
cd "c:\Users\oumme\OneDrive\Desktop\Predictive Maintenance"
.\venv\Scripts\Activate.ps1
```

### Open Browser
**URL:** `http://localhost:3000`

---

## 🧪 STEP 2: BUILD BASELINE (Do This First!)

### Generate Healthy Data (20 seconds of normal readings)
```powershell
python scripts/generate_data.py --asset_id Motor-01 --duration 20 --healthy
```

### Build Baseline Model
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/baseline/build?asset_id=Motor-01" -Method Post
```
✅ **Expected Response:**
```json
{
  "status": "success",
  "baseline_id": "...",
  "sample_count": 20
}
```

### Check Current Status
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/status/Motor-01"
```

---

## 📊 STEP 3: DEMONSTRATE ALL RISK LEVELS

### 🟢 LOW RISK (Healthy State)
**Show first!** After building baseline, dashboard shows:
- Health Score: **75-100** (green ring)
- Risk Level: **LOW** (green badge)
- Maintenance Window: **~60 days**
- **NO red dashed lines** on chart

---

### 🟡 MODERATE RISK (Slight Anomaly)
```powershell
$body = @{
    asset_id='Motor-01'
    voltage_v=240
    current_a=17
    power_factor=0.85
    vibration_g=0.25
} | ConvertTo-Json
Invoke-RestMethod -Uri 'http://localhost:8000/api/v1/data/simple' -Method Post -Body $body -ContentType 'application/json'
```

**What to point out:**
- Health Score: **50-74** (yellow/orange ring)
- Risk Level: **MODERATE** (orange badge)
- Maintenance Window: **~19 days**
- **Red dashed lines with ⚠️** appear at anomaly point!

---

### 🟠 HIGH RISK (Significant Anomaly)
```powershell
$body = @{
    asset_id='Motor-01'
    voltage_v=250
    current_a=19
    power_factor=0.75
    vibration_g=0.4
} | ConvertTo-Json
Invoke-RestMethod -Uri 'http://localhost:8000/api/v1/data/simple' -Method Post -Body $body -ContentType 'application/json'
```

**What to point out:**
- Health Score: **25-49** (orange ring)
- Risk Level: **HIGH** (orange badge)
- Maintenance Window: **~4 days**
- Multiple explanations in Insight panel

---

### 🔴 CRITICAL RISK (Extreme Anomaly)
```powershell
$body = @{
    asset_id='Motor-01'
    voltage_v=280
    current_a=25
    power_factor=0.60
    vibration_g=2.5
} | ConvertTo-Json
Invoke-RestMethod -Uri 'http://localhost:8000/api/v1/data/simple' -Method Post -Body $body -ContentType 'application/json'
```

**What to point out:**
- Health Score: **0-24** (red ring)
- Risk Level: **CRITICAL** (red badge)
- Maintenance Window: **< 1 day**
- Vibration spiked **2500%** above normal!
- Clear explanation: "Vibration value (2.5) exceeds observed maximum (0.22)"

---

## 🔄 STEP 4: DEMONSTRATE RECOVERY

### Send Healthy Data
```powershell
python scripts/generate_data.py --asset_id Motor-01 --duration 10 --healthy
```

**What to point out:**
- Health Score recovers to 75+
- Risk Level returns to LOW
- **Red lines disappear** (system is healthy again!)

---

## 📄 STEP 5: DOWNLOAD INDUSTRIAL REPORT

### Click the "DOWNLOAD FULL REPORT" Button
The dashboard has a blue button: **"📄 DOWNLOAD FULL REPORT (5-Page PDF)"**

**What to show in the PDF:**
1. **Page 1 - Executive Summary**: Large health gauge, RUL days, risk level badge
2. **Page 2 - Sensor Analysis**: Current readings vs baseline, 24h statistics
3. **Page 3 - ML Explainability**: Bar chart showing which sensors contributed most to the risk
4. **Page 4 - Business ROI**: $450 maintenance vs $45,000 failure = 100x ROI, recommended actions
5. **Page 5 - Audit Trail**: Millisecond-precision process log, ISO compliance checkboxes

### Alternative Downloads
- **Excel button**: Spreadsheet format for data analysis
- **Basic PDF button**: Simple 1-page certificate

---

## 🎤 TALKING POINTS

### When Asked "What Problem Does This Solve?"
> "Unexpected equipment failures cost industries millions. This system monitors industrial motors in real-time and predicts maintenance needs BEFORE failures occur, reducing downtime by up to 40%."

### When Asked "How Does the ML Work?"
> "We use Isolation Forest algorithm trained on healthy sensor data to detect anomalies. When new readings deviate from the learned baseline, the system flags it and calculates a health score."

### When Asked "What Makes This Different?"
> "Unlike black-box ML systems, we provide EXPLAINABILITY. The system tells you exactly WHY it flagged an issue - 'Vibration is 3x above normal' - so operators can take targeted action."

### When Asked "What About Compliance?"
> "Our 5-page Industrial Report includes an audit trail with millisecond precision and ISO 55000/13374 compliance verification. It's designed to meet industrial audit requirements."

### When Asked "What Sensors Are Monitored?"
> "We track 4 key signals: Voltage (V), Current (A), Power Factor, and Vibration (g). These are the primary indicators of motor health."

---

## 🔧 TROUBLESHOOTING

| Issue | Fix |
|-------|-----|
| STATUS: OFFLINE | Restart backend: `uvicorn backend.api.main:app --port 8000` |
| Port 3000 in use | Frontend auto-switches to 3001, or close other terminals |
| No chart data | Run `python scripts/generate_data.py --healthy` first |
| venv not activated | Run `.\venv\Scripts\Activate.ps1` |
| "No baseline found" | Build baseline first with the commands above |

---

## 📱 API ENDPOINTS REFERENCE

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/data/simple` | POST | Ingest sensor data |
| `/api/v1/baseline/build` | POST | Build baseline model |
| `/api/v1/status/{asset_id}` | GET | Get health status |
| `/api/v1/data/history/{asset_id}` | GET | Get historical data |
| `/api/v1/report/{asset_id}?format=industrial` | GET | Download 5-page Industrial Report (PDF) |
| `/api/v1/report/{asset_id}?format=pdf` | GET | Download basic PDF report |
| `/api/v1/report/{asset_id}?format=xlsx` | GET | Download Excel report |

---

## 🎓 ARCHITECTURE SUMMARY

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Sensor Data    │────▶│  FastAPI Backend │────▶│  React Dashboard│
│  (Generator)    │     │  + ML Pipeline   │     │  (Real-time UI) │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                        ┌──────┴──────┐
                        │             │
                   ┌────▼────┐  ┌─────▼─────┐
                   │Baseline │  │  Health   │
                   │Builder  │  │  Assessor │
                   └─────────┘  └───────────┘
```

---

## ✅ DEMO SUCCESS CHECKLIST

- [ ] Showed LOW risk (healthy state, no red lines)
- [ ] Showed MODERATE risk (lines appear)
- [ ] Showed HIGH risk (multiple alerts)
- [ ] Showed CRITICAL risk (extreme spike)
- [ ] Showed recovery back to LOW
- [ ] Downloaded 5-page Industrial Report (PDF)
- [ ] Explained ML anomaly detection
- [ ] Showed explainability panel
- [ ] Mentioned real-world use case

---

**Good luck with your demo!** 🚀
