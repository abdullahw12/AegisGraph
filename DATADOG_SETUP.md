# Datadog Dashboard Setup Guide

## Quick Setup

### Option 1: Import Dashboard JSON (Recommended)

1. Go to https://app.datadoghq.com/dashboard/lists
2. Click "New Dashboard" button
3. Click the settings gear icon (⚙️) in the top right
4. Select "Import dashboard JSON"
5. Copy the contents of `datadog_dashboard.json` and paste it
6. Click "Save"

### Option 2: Create Dashboard Manually

1. Go to https://app.datadoghq.com/dashboard/lists
2. Click "New Dashboard"
3. Name it "AegisGraph - HIPAA LLM Firewall"
4. Add the following widgets:

#### Widget 1: Access Legitimacy (Timeseries)
- Metric: `avg:aegisgraph.eval.access_legitimacy{*}`
- Y-axis: 0 to 1
- Shows authorization success rate

#### Widget 2: PHI Exposure Risk (Timeseries)
- Metric: `avg:aegisgraph.eval.phi_risk{*}`
- Y-axis: 0 to 1
- Shows risk of PHI exposure

#### Widget 3: Authorization Denials (Timeseries - Bars)
- Metric: `sum:aegisgraph.security.auth_denies{*}.as_count()`
- Shows denied access attempts

#### Widget 4: LLM Cost (Timeseries - Area)
- Metric: `sum:aegisgraph.eval.cost_usd{*}.as_count()`
- Shows cumulative LLM costs

#### Widget 5: Agent Pipeline Traces (Timeseries - Bars)
- Metric 1: `sum:trace.intent.classify.hits{service:aegisgraph}.as_count()`
- Metric 2: `sum:trace.policy.neo4j_check.hits{service:aegisgraph}.as_count()`
- Metric 3: `sum:trace.safety.scan.hits{service:aegisgraph}.as_count()`
- Metric 4: `sum:trace.llm.generate.hits{service:aegisgraph}.as_count()`
- Shows agent execution counts

#### Widget 6-9: Query Values
- Total Requests
- Blocked Requests
- Average Response Time
- Security Mode Status

---

## Update UI with Dashboard URL

Once you've created the dashboard:

1. Copy the dashboard URL from your browser (e.g., `https://app.datadoghq.com/dashboard/abc-123-xyz`)
2. Update `AegisGraph/.env`:
   ```bash
   DD_DASHBOARD_URL=https://app.datadoghq.com/dashboard/your-actual-dashboard-id
   ```
3. Restart the backend
4. Refresh the UI at http://localhost:8000

---

## Verify Metrics Are Being Sent

### Check if Datadog Agent is Running

The code uses the Datadog Python SDK which sends metrics via StatsD to localhost:8125.

**Option 1: Use Datadog Agent (Recommended for production)**
```bash
# Install Datadog Agent
# macOS
brew install datadog-agent

# Start agent
datadog-agent start

# Check status
datadog-agent status
```

**Option 2: Direct API (Current setup)**
The current setup sends metrics directly using the DD_API_KEY. However, you may not see metrics immediately because:
- The Datadog Agent isn't running locally (you'll see connection errors in logs)
- Metrics are being sent but may take a few minutes to appear

### View Metrics in Datadog

1. Go to https://app.datadoghq.com/metric/explorer
2. Search for `aegisgraph.*`
3. You should see:
   - `aegisgraph.eval.access_legitimacy`
   - `aegisgraph.eval.phi_risk`
   - `aegisgraph.eval.cost_usd`
   - `aegisgraph.security.auth_denies`

### View Traces in Datadog

1. Go to https://app.datadoghq.com/apm/traces
2. Filter by service: `aegisgraph`
3. You should see traces with spans:
   - `intent.classify`
   - `policy.neo4j_check`
   - `safety.scan`
   - `llm.generate`
   - `minimax.tts_alert` (if MiniMax is configured)

---

## Troubleshooting

### No metrics showing up

The backend logs show:
```
failed to send, dropping 2 traces to intake at http://localhost:8126/v0.5/traces: client error (Connect)
```

This is because ddtrace expects a local Datadog Agent running on port 8126. You have two options:

**Option A: Install Datadog Agent (Recommended)**
```bash
# macOS
brew install datadog-agent

# Configure with your API key
sudo sh -c "sed 's/api_key:.*/api_key: 02c9008059f75f749ca1fbfdea595145/' /opt/datadog-agent/etc/datadog.yaml.example > /opt/datadog-agent/etc/datadog.yaml"

# Start agent
datadog-agent start
```

**Option B: Use Agentless Mode**
Update `backend/telemetry/ddtrace_setup.py` to send traces directly to Datadog:
```python
import ddtrace
from ddtrace import tracer

tracer.configure(
    hostname="",
    port=0,
    https=True,
    agent_url="https://trace.agent.datadoghq.com"
)
```

### Metrics delayed

Datadog metrics can take 2-5 minutes to appear in the UI. Be patient and run a few test requests.

---

## Demo Without Datadog Agent

If you don't want to set up the Datadog Agent right now, the application still works perfectly! The metrics/traces just won't be visible in Datadog. You can:

1. Use the web UI to test all scenarios
2. See the chat responses and blocked requests
3. Watch the STRICT_MODE banner trigger
4. View all the functionality working

The Datadog integration is optional for the demo - the core security pipeline works independently.
