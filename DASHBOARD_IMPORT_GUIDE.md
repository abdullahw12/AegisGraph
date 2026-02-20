# Quick Dashboard Import Guide

## Step 1: Copy the Dashboard JSON

The dashboard configuration is in `datadog_dashboard.json`

## Step 2: Import to Datadog

1. Go to https://app.datadoghq.com/dashboard/lists
2. Click **"New Dashboard"** button (top right)
3. Give it any name (it will be replaced)
4. Click the **settings gear icon** (⚙️) in the top right
5. Select **"Import dashboard JSON"**
6. Open `AegisGraph/datadog_dashboard.json` in a text editor
7. Copy ALL the JSON content
8. Paste it into the import dialog
9. Click **"Save"**

## Step 3: Get the Dashboard URL

After importing, your browser URL will look like:
```
https://app.datadoghq.com/dashboard/abc-123-xyz
```

Copy this URL!

## Step 4: Update the UI

1. Open `AegisGraph/.env`
2. Find the line with `DD_DASHBOARD_URL`
3. Replace it with your actual dashboard URL:
   ```
   DD_DASHBOARD_URL=https://app.datadoghq.com/dashboard/abc-123-xyz
   ```
4. Save the file

## Step 5: Update the UI Code

Open `AegisGraph/ui/index.html` and find this line (around line 280):

```html
<iframe src="https://app.datadoghq.com/dashboard/your-dashboard-id" frameborder="0"></iframe>
```

Replace it with:

```html
<iframe src="YOUR_ACTUAL_DASHBOARD_URL_HERE" frameborder="0"></iframe>
```

## Step 6: Restart and View

1. Restart the backend (kill and restart the uvicorn process)
2. Refresh http://localhost:8000 in your browser
3. The dashboard should now load in the right panel!

---

## Alternative: Use the Placeholder

If you don't want to set up the dashboard right now, the UI already shows a helpful placeholder with:
- List of metrics being tracked
- Link to open Datadog in a new tab
- Instructions for setting it up later

The core functionality (chat, authorization, security modes) works perfectly without the dashboard!

---

## Troubleshooting

### Dashboard shows "No data"

This is expected! The metrics won't show data until:
1. You run some chat requests through the UI
2. The Datadog Agent is running locally (or you configure agentless mode)
3. A few minutes pass for metrics to propagate

### Can't see the iframe

Check your browser console for errors. Some browsers block iframes from external domains. You may need to:
- Allow iframes in your browser settings
- Open the dashboard in a new tab instead (click the link in the placeholder)

### Metrics not appearing in Datadog

See `DATADOG_SETUP.md` for full troubleshooting steps. The short version:
- Install Datadog Agent locally, OR
- Configure agentless mode in `backend/telemetry/ddtrace_setup.py`
