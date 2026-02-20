"""FastAPI application entry point for AegisGraph."""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables FIRST before any other imports
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

from backend.models.schemas import ChatRequest
from backend.orchestrator import run_pipeline, get_mode, set_mode
from backend.tools.datadog_mcp_tool import DatadogMCPTool

# Check if we should use mock mode (when Bedrock isn't available)
USE_MOCK_MODE = os.getenv("USE_MOCK_BEDROCK", "false").lower() == "true"

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize ddtrace
from backend.telemetry import ddtrace_setup  # noqa: F401


class SecurityModeRequest(BaseModel):
    """Request model for changing security mode."""
    mode: str


class SecurityModeResponse(BaseModel):
    """Response model for security mode queries."""
    security_mode: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI startup and shutdown.
    Initializes DatadogMCPTool and ddtrace on startup.
    """
    logger.info("Starting AegisGraph FastAPI application")
    logger.info("Datadog tracing initialized with service name: aegisgraph")
    logger.info("DatadogMCPTool initialized with 60s window, threshold=3, cooldown=600s")
    
    yield
    
    logger.info("Shutting down AegisGraph FastAPI application")


# Create FastAPI app
app = FastAPI(
    title="AegisGraph",
    description="HIPAA-aligned LLM firewall with graph-based authorization",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Main chat endpoint that processes requests through the security pipeline.
    
    Args:
        request: ChatRequest with user_id, role, doc_id, patient_id, message
        
    Returns:
        Pipeline result with final_text or refusal reason
    """
    try:
        logger.info(f"Received chat request: {request.request_id}")
        result = await run_pipeline(request)
        return result
    except Exception as e:
        logger.error(f"Error processing chat request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.post("/mode")
async def set_mode_endpoint(request: SecurityModeRequest):
    """
    Admin endpoint to manually set the security mode.
    
    Args:
        request: SecurityModeRequest with mode (NORMAL, STRICT_MODE, or LOCKDOWN)
        
    Returns:
        Confirmation with the new security mode
    """
    try:
        mode = request.mode.upper()
        if mode not in {"NORMAL", "STRICT_MODE", "LOCKDOWN"}:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid mode '{request.mode}'. Must be one of: NORMAL, STRICT_MODE, LOCKDOWN"
            )
        
        await set_mode(mode)
        logger.info(f"Security mode changed to: {mode}")
        
        return {
            "success": True,
            "security_mode": mode,
            "message": f"Security mode set to {mode}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting security mode: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/mode")
async def get_mode_endpoint() -> SecurityModeResponse:
    """
    Get the current security mode.
    Used by the UI for polling and displaying the current mode.
    
    Returns:
        SecurityModeResponse with the current security_mode
    """
    try:
        current_mode = await get_mode()
        return SecurityModeResponse(security_mode=current_mode)
    except Exception as e:
        logger.error(f"Error getting security mode: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        Status information
    """
    return {
        "status": "healthy",
        "service": "aegisgraph",
        "version": "1.0.0"
    }


@app.get("/")
async def root():
    """
    Serve the UI homepage.
    """
    ui_path = Path(__file__).parent.parent / "ui" / "app.html"
    if ui_path.exists():
        return FileResponse(ui_path)
    return {"message": "AegisGraph API", "docs": "/docs"}


@app.get("/doctors")
async def get_doctors():
    """
    Get list of all doctors.
    """
    try:
        from backend.tools.neo4j_client import Neo4jClient
        neo4j_client = Neo4jClient()
        
        query = """
        MATCH (d:Doctor)
        RETURN d.id as id, d.name as name, d.specialty as specialty
        ORDER BY d.name
        """
        
        result = await neo4j_client.run_query(query)
        await neo4j_client.close()
        
        return result
    except Exception as e:
        logger.error(f"Error getting doctors: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/patients")
async def get_patients(doctor_id: Optional[str] = None):
    """
    Get list of patients. If doctor_id provided, only return patients under their care.
    """
    try:
        from backend.tools.neo4j_client import Neo4jClient
        neo4j_client = Neo4jClient()
        
        if doctor_id:
            query = """
            MATCH (d:Doctor {id: $doctor_id})-[:TREATS]->(p:Patient)
            RETURN p.id as id, p.name as name, p.dob as dob, p.blood_type as blood_type
            ORDER BY p.name
            """
            result = await neo4j_client.run_query(query, {"doctor_id": doctor_id})
        else:
            # Emergency mode - all patients
            query = """
            MATCH (p:Patient)
            RETURN p.id as id, p.name as name, p.dob as dob, p.blood_type as blood_type
            ORDER BY p.name
            """
            result = await neo4j_client.run_query(query)
        
        await neo4j_client.close()
        return result
    except Exception as e:
        logger.error(f"Error getting patients: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chat/history")
async def get_chat_history(patient_id: str, doctor_id: str):
    """
    Get chat history for a patient.
    """
    try:
        from backend.tools.neo4j_client import Neo4jClient
        neo4j_client = Neo4jClient()
        
        query = """
        MATCH (d:Doctor {id: $doctor_id})-[:SENT_MESSAGE]->(msg:ChatMessage)-[:ABOUT_PATIENT]->(p:Patient {id: $patient_id})
        RETURN msg.id as id, msg.message as message, msg.response as response, 
               msg.blocked as blocked, msg.reason as reason, msg.timestamp as timestamp
        ORDER BY msg.timestamp ASC
        """
        
        result = await neo4j_client.run_query(query, {
            "doctor_id": doctor_id,
            "patient_id": patient_id
        })
        await neo4j_client.close()
        
        return result
    except Exception as e:
        logger.error(f"Error getting chat history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/activity/log")
async def log_activity(activity: dict):
    """
    Log activity for audit trail.
    """
    try:
        from backend.tools.neo4j_client import Neo4jClient
        from datetime import datetime
        
        neo4j_client = Neo4jClient()
        
        query = """
        MATCH (d:Doctor {id: $doctor_id})
        CREATE (a:Activity {
            id: randomUUID(),
            type: $type,
            description: $description,
            timestamp: datetime($timestamp)
        })
        CREATE (d)-[:PERFORMED]->(a)
        RETURN a
        """
        
        await neo4j_client.run_query(query, {
            "doctor_id": activity.get("doctor_id"),
            "type": activity.get("type"),
            "description": activity.get("description"),
            "timestamp": activity.get("timestamp", datetime.utcnow().isoformat())
        })
        await neo4j_client.close()
        
        return {"success": True}
    except Exception as e:
        logger.error(f"Error logging activity: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics")
async def get_metrics():
    """
    Get current metrics for dashboard.
    """
    try:
        from backend.tools.neo4j_client import Neo4jClient
        neo4j_client = Neo4jClient()
        
        # Get total and blocked requests
        query = """
        MATCH (msg:ChatMessage)
        WITH count(msg) as total, sum(CASE WHEN msg.blocked THEN 1 ELSE 0 END) as blocked
        RETURN total, blocked
        """
        
        result = await neo4j_client.run_query(query)
        await neo4j_client.close()
        
        total = result[0]["total"] if result else 0
        blocked = result[0]["blocked"] if result else 0
        
        current_mode = await get_mode()
        
        return {
            "total_requests": total,
            "blocked_requests": blocked,
            "security_mode": current_mode
        }
    except Exception as e:
        logger.error(f"Error getting metrics: {e}", exc_info=True)
        return {
            "total_requests": 0,
            "blocked_requests": 0,
            "security_mode": "NORMAL"
        }


@app.post("/datadog/create-dashboard")
async def create_datadog_dashboard():
    """
    Create or update the AegisGraph Datadog dashboard programmatically.
    """
    try:
        from backend.telemetry.datadog_integration import datadog_integration
        
        dashboard_config = datadog_integration.get_aegisgraph_dashboard_config()
        dashboard_url = datadog_integration.create_dashboard(dashboard_config)
        
        if dashboard_url:
            return {
                "success": True,
                "dashboard_url": dashboard_url,
                "message": "Dashboard created successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to create dashboard")
    except Exception as e:
        logger.error(f"Error creating Datadog dashboard: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
