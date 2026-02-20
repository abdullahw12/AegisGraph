# AegisGraph

**HIPAA-Aligned LLM Firewall with Graph-Based Authorization**

AegisGraph is a security-first LLM gateway that enforces HIPAA compliance through a four-agent pipeline with Neo4j-powered authorization, real-time threat detection, and comprehensive Datadog monitoring.

## Features

### 🔒 Security Pipeline
- **Intent Classification**: Analyzes request intent (TREATMENT, DIAGNOSIS, ADMIN, etc.)
- **Graph-Based Authorization**: Neo4j relationship validation for doctor-patient access
- **Safety Scanning**: Real-time threat detection (prompt injection, jailbreak attempts, PII leakage)
- **Response Generation**: Context-aware clinical responses with conversation history

### 🏥 Healthcare-Specific
- **HIPAA Compliance**: Audit trails, access controls, and PHI protection
- **Break-Glass Access**: Emergency mode for critical situations with full audit logging
- **Doctor Authentication**: Passcode-based login with patient assignment
- **Conversation Context**: Maintains chat history per doctor-patient session

### 📊 Live Monitoring
- **Datadog Integration**: Real-time logs, metrics, and dashboards
- **Prompt Visibility**: All LLM prompts and responses logged
- **Cost Tracking**: Token usage and LLM costs monitored
- **Security Metrics**: Authorization rates, blocked requests, PHI risk scores

### 🎨 Modern UI
- **Three-Panel Layout**: Patient list, chat interface, live metrics
- **Emergency Mode**: One-click access to all patients with audit trail
- **Activity Logging**: All actions tracked in Neo4j for compliance
- **Real-Time Updates**: Live security mode and metrics display

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         UI Layer                             │
│  (Doctor Login → Patient Selection → Chat Interface)        │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    Security Pipeline                         │
│                                                              │
│  1. Intent Agent      → Classify request intent             │
│  2. Graph Policy      → Neo4j authorization check           │
│  3. Safety Agent      → Threat detection & scanning         │
│  4. Response Agent    → Context-aware LLM generation        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    Data & Monitoring                         │
│                                                              │
│  • Neo4j: Relationships, chat history, audit logs           │
│  • Datadog: Real-time logs, metrics, dashboards             │
│  • AWS Bedrock / Mock: LLM inference                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites
- Python 3.10+
- Neo4j Aura account (or local Neo4j instance)
- Datadog account (for monitoring)
- AWS Bedrock access (optional - mock mode available)

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd AegisGraph
```

2. **Create virtual environment**
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your credentials:
# - NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
# - DD_API_KEY, DD_APP_KEY (Datadog)
# - AWS credentials (optional if using mock mode)
```

5. **Seed Neo4j database**
```bash
python backend/seed_data/seed.py
```

6. **Start the backend**
```bash
./start_backend.sh
# Or manually: uvicorn backend.main:app --reload
```

7. **Access the UI**
```bash
open http://localhost:8000
```

### Default Credentials
- All doctor passcodes: `1234`
- Doctors: D1 (Cardiology), D2 (Neurology), D3 (Orthopedics)
- Patients: P101, P102, P103, P104, P105, P106

## Configuration

### Environment Variables

Create a `.env` file with the following:

```bash
# Neo4j Configuration
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password
NEO4J_DATABASE=neo4j

# Datadog Configuration
DD_API_KEY=your-datadog-api-key
DD_APP_KEY=your-datadog-app-key
DD_AGENT_HOST=localhost
DD_STATSD_PORT=8125

# AWS Bedrock (Optional)
AWS_REGION=us-west-2
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_SESSION_TOKEN=your-session-token

# Mock Mode (set to true if no AWS Bedrock access)
USE_MOCK_BEDROCK=true
```

### Security Modes

AegisGraph supports three security modes:

1. **NORMAL**: Standard authorization checks
2. **STRICT_MODE**: Enhanced security (auto-triggered after threshold breaches)
3. **LOCKDOWN**: All requests blocked (emergency shutdown)

Change mode via API:
```bash
curl -X POST http://localhost:8000/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "NORMAL"}'
```

## API Endpoints

### Chat
```bash
POST /chat
{
  "user_id": "U1",
  "role": "doctor",
  "doc_id": "D1",
  "patient_id": "P101",
  "message": "What is the patient's blood type?",
  "security_mode": "NORMAL"
}
```

### Doctors & Patients
```bash
GET /doctors                          # List all doctors
GET /patients?doctor_id=D1            # List patients for doctor
GET /chat/history?patient_id=P101&doctor_id=D1  # Get chat history
```

### Monitoring
```bash
GET /metrics                          # Current system metrics
GET /mode                             # Current security mode
POST /mode                            # Change security mode
POST /datadog/create-dashboard        # Create Datadog dashboard
```

### Activity Logging
```bash
POST /activity/log
{
  "doctor_id": "D1",
  "type": "emergency_access",
  "description": "Accessed all patients in emergency mode"
}
```

## Datadog Integration

### Create Dashboard
```bash
curl -X POST http://localhost:8000/datadog/create-dashboard
```

Returns:
```json
{
  "success": true,
  "dashboard_url": "https://app.datadoghq.com/dashboard/xxx-xxx-xxx",
  "message": "Dashboard created successfully"
}
```

### Dashboard Features
- **Total Requests**: Live count of all requests
- **Blocked Requests**: Security blocks and denials
- **Token Usage**: LLM input/output tokens over time
- **Cost Tracking**: Cumulative LLM costs
- **Log Stream**: Real-time prompts and responses
- **Security Metrics**: Authorization rates, PHI risk scores

### Viewing Logs
Logs appear in Datadog after 2-5 minutes of indexing:
- **Logs Explorer**: https://app.datadoghq.com/logs?query=source:aegisgraph
- **Dashboard**: Created via `/datadog/create-dashboard` endpoint

## Testing

### Run Tests
```bash
# All tests
pytest

# Specific test file
pytest backend/test_orchestrator.py

# With coverage
pytest --cov=backend --cov-report=html
```

### Integration Test
```bash
python backend/test_integration.py
```

### Connectivity Test
```bash
python test_connectivity.py
```

## Project Structure

```
AegisGraph/
├── backend/
│   ├── agents/              # Four-agent pipeline
│   │   ├── intent_agent.py
│   │   ├── graph_policy_agent.py
│   │   ├── safety_agent.py
│   │   └── response_agent.py
│   ├── models/              # Pydantic schemas
│   ├── tools/               # External integrations
│   │   ├── neo4j_client.py
│   │   ├── bedrock_client.py
│   │   ├── mock_bedrock_client.py
│   │   └── datadog_mcp_tool.py
│   ├── telemetry/           # Monitoring
│   │   ├── datadog_integration.py
│   │   ├── ddtrace_setup.py
│   │   └── metrics.py
│   ├── seed_data/           # Database seeding
│   ├── orchestrator.py      # Pipeline coordinator
│   └── main.py              # FastAPI app
├── ui/
│   └── app.html             # Modern web interface
├── .env.example             # Environment template
├── requirements.txt         # Python dependencies
└── README.md                # This file
```

## Documentation

- **[QUICK_START.md](QUICK_START.md)**: Step-by-step setup guide
- **[DEMO_GUIDE.md](DEMO_GUIDE.md)**: Demo walkthrough
- **[DATADOG_SETUP.md](DATADOG_SETUP.md)**: Datadog configuration
- **[DATADOG_LIVE_INTEGRATION.md](DATADOG_LIVE_INTEGRATION.md)**: Live monitoring details
- **[DATADOG_TROUBLESHOOTING.md](DATADOG_TROUBLESHOOTING.md)**: Common issues
- **[NEW_UI_FEATURES.md](NEW_UI_FEATURES.md)**: UI feature documentation

## Features in Detail

### Intent Classification
Automatically categorizes requests:
- `TREATMENT`: Treatment plans, medications
- `DIAGNOSIS`: Diagnostic queries
- `ADMIN`: Administrative tasks
- `EMERGENCY`: Critical situations
- `UNKNOWN`: Unclassified requests

### Graph-Based Authorization
Neo4j relationships enforce access control:
```cypher
MATCH (d:Doctor {id: $docId})-[:TREATS]->(p:Patient {id: $patId})
RETURN authorized
```

### Safety Scanning
Detects security threats:
- Prompt injection attempts
- Jailbreak patterns
- PII leakage risks
- Unauthorized data access
- Malicious intent

### Conversation Context
Maintains chat history:
- Last 10 messages per doctor-patient session
- Chronological ordering
- Context-aware responses
- Session management

## Security Features

### Audit Trail
All actions logged to Neo4j:
- Doctor logins
- Patient access
- Emergency mode activations
- Chat interactions
- Authorization denials

### Break-Glass Access
Emergency mode features:
- Access all patients
- Full audit logging
- Activity tracking
- Datadog alerts

### Self-Healing
Automatic security escalation:
- Monitors auth denials and safety blocks
- Auto-escalates to STRICT_MODE after threshold
- Auto-reverts after cooldown period
- Configurable thresholds

## Monitoring & Observability

### Metrics Tracked
- Total requests
- Blocked requests
- Authorization success rate
- Token usage (input/output)
- LLM costs
- Response times
- PHI exposure risk
- Security mode changes

### Logs Captured
- All LLM prompts and responses
- Authorization decisions
- Safety scan results
- Error traces
- Activity logs

## Development

### Adding New Agents
1. Create agent class in `backend/agents/`
2. Implement required methods
3. Add to pipeline in `orchestrator.py`
4. Update tests

### Extending Authorization
1. Modify Neo4j schema in `seed_data/seed.cypher`
2. Update `graph_policy_agent.py` queries
3. Add new relationship types
4. Test authorization logic

### Custom Monitoring
1. Add metrics in `telemetry/metrics.py`
2. Update Datadog dashboard config
3. Add log fields in `datadog_integration.py`

## Troubleshooting

### Common Issues

**Dashboard shows no data:**
- Wait 2-5 minutes for log indexing
- Check Logs Explorer first
- Verify DD_API_KEY and DD_APP_KEY in .env

**Neo4j connection errors:**
- Verify NEO4J_URI, username, password
- Check network connectivity
- Ensure database is seeded

**Chat not working:**
- Check backend logs for errors
- Verify mock mode is enabled if no AWS access
- Ensure Neo4j has doctor-patient relationships

**Authorization always fails:**
- Run seed script to create relationships
- Check doctor_id and patient_id are correct
- Verify Neo4j query in logs

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

[Add your license here]

## Support

For issues and questions:
- Check documentation in `/docs`
- Review troubleshooting guides
- Open an issue on GitHub

## Acknowledgments

Built with:
- FastAPI
- Neo4j
- Datadog
- AWS Bedrock
- Python 3.10+
