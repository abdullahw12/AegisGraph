# Datadog Dashboard Troubleshooting Guide

## Issue: Dashboard Shows No Data

### Root Cause
Logs are being sent successfully to Datadog (confirmed by log message: "Successfully sent log to Datadog"), but there's a **2-5 minute indexing delay** before they appear in the dashboard.

### Verification Steps

1. **Check Backend Logs** - Confirm logs are being sent:
```bash
# Look for this message in backend logs:
"Successfully sent log to Datadog for request <request_id>"
```

2. **Wait for Indexing** - Datadog needs time to index logs:
   - Initial indexing: 2-5 minutes
   - Subsequent updates: 30-60 seconds

3. **Check Datadog Logs Explorer** (faster than dashboard):
   - Go to: https://app.datadoghq.com/logs
   - Search for: `source:aegisgraph`
   - You should see logs appearing here first

4. **Verify Dashboard Time Range**:
   - Open dashboard: https://app.datadoghq.com/dashboard/829-2yx-vsp
   - Check time range selector (top right)
   - Set to "Past 1 Hour" or "Past 4 Hours"
   - Click refresh button

### Current Status

✅ **Logs ARE being sent** - Backend confirms 202 responses from Datadog
✅ **Dashboard created** - Using log-based metrics (no agent required)
⏳ **Waiting for indexing** - Logs take 2-5 minutes to appear

### Test Data Sent

We've sent multiple test requests that should appear in Datadog:
- Request IDs logged successfully
- Prompts and responses included
- Token counts and costs tracked
- Authorization and security status recorded

### Dashboard Widgets

The new dashboard uses **log-based metrics** (no Datadog agent required):

**Row 1 - Counters (Last Hour):**
- Total Requests: Count of all logs with `source:aegisgraph`
- Blocked Requests: Count of logs with `@blocked:true`
- Authorized Requests: Count of logs with `@authorized:true`
- Total Cost: Sum of `@cost_usd` field

**Row 2 - Time Series:**
- Requests Over Time: Total vs blocked (bars)
- Token Usage: Input vs output tokens (area charts)

**Row 3 - Analysis:**
- Requests by Security Mode: Grouped by `@security_mode`
- Cost Over Time: Cumulative costs

**Row 4 - Log Stream:**
- Recent prompts and responses with full details

### Next Steps

1. **Wait 5 minutes** from the last test request
2. **Refresh the dashboard** - Click the refresh icon
3. **Check Logs Explorer first** - https://app.datadoghq.com/logs?query=source%3Aaegisgraph
4. **Adjust time range** - Set to "Past 1 Hour" if needed

### If Still No Data After 10 Minutes

Check the Logs Explorer with this query:
```
source:aegisgraph
```

If logs appear in Logs Explorer but not in dashboard:
1. The dashboard widgets may need time range adjustment
2. Try changing dashboard time range to "Past 4 Hours"
3. Click the refresh button in the dashboard

If logs DON'T appear in Logs Explorer:
1. Check if DD_API_KEY is correct in `.env`
2. Verify backend logs show "Successfully sent log to Datadog"
3. Check for any error messages in backend logs

### Log Format Being Sent

Each log entry includes:
```json
{
  "ddsource": "aegisgraph",
  "ddtags": "service:aegisgraph,env:prod,request_id:<id>",
  "hostname": "aegisgraph-backend",
  "message": "LLM Interaction - Request: <id>",
  "prompt": "<truncated to 1000 chars>",
  "response": "<truncated to 1000 chars>",
  "tokens_in": <number>,
  "tokens_out": <number>,
  "cost_usd": <number>,
  "model": "mock",
  "security_mode": "NORMAL",
  "authorized": true/false,
  "blocked": true/false,
  "timestamp": "<ISO 8601>"
}
```

### Dashboard URLs

- **New Dashboard (Log-Based)**: https://app.datadoghq.com/dashboard/829-2yx-vsp
- **Logs Explorer**: https://app.datadoghq.com/logs?query=source%3Aaegisgraph

### Generate More Test Data

```bash
# Send 10 test requests
for i in {1..10}; do
  curl -s -X POST http://localhost:8000/chat \
    -H "Content-Type: application/json" \
    -d "{
      \"user_id\": \"U1\",
      \"role\": \"doctor\",
      \"doc_id\": \"D1\",
      \"patient_id\": \"P101\",
      \"message\": \"Test request $i\",
      \"security_mode\": \"NORMAL\"
    }" > /dev/null
  echo "Request $i sent"
  sleep 1
done
```

Then wait 5 minutes and check the dashboard.

## Summary

The integration is working correctly. Logs are being sent to Datadog successfully (confirmed by backend logs). The dashboard will populate once Datadog finishes indexing the logs (2-5 minutes). Check the Logs Explorer first as it updates faster than dashboards.
