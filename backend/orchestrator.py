"""Orchestrator - Coordinates the four-agent pipeline with security gates."""

import asyncio
import logging
import os
from typing import Dict, Any

from backend.models.schemas import ChatRequest, IntentDecision, PolicyDecision, SafetyDecision, ResponseDecision
from backend.agents.intent_agent import IntentAgent
from backend.agents.graph_policy_agent import GraphPolicyAgent
from backend.agents.safety_agent import SafetyAgent
from backend.agents.response_agent import ResponseAgent
from backend.tools.datadog_mcp_tool import DatadogMCPTool
from backend.tools.minimax_client import MiniMaxClient
from backend.telemetry import metrics
from backend.telemetry.datadog_integration import datadog_integration

logger = logging.getLogger(__name__)

# Check if we're in mock mode
USE_MOCK_MODE = os.getenv("USE_MOCK_BEDROCK", "false").lower() == "true"

# Module-level security mode state
_security_mode: str = "NORMAL"
_security_mode_lock = asyncio.Lock()

# Module-level DatadogMCPTool instance
_datadog_mcp_tool: DatadogMCPTool = DatadogMCPTool(
    window_seconds=60,
    threshold=3,
    cooldown_seconds=600
)

# Module-level MiniMax client
_minimax_client: MiniMaxClient = MiniMaxClient()

# Scheduled task for reverting STRICT_MODE
_revert_task: asyncio.Task | None = None


async def get_mode() -> str:
    """Get the current security mode."""
    async with _security_mode_lock:
        return _security_mode


async def set_mode(mode: str) -> None:
    """
    Set the security mode.
    
    Args:
        mode: One of NORMAL, STRICT_MODE, or LOCKDOWN
    """
    global _security_mode, _revert_task
    
    async with _security_mode_lock:
        if mode not in {"NORMAL", "STRICT_MODE", "LOCKDOWN"}:
            logger.warning(f"Invalid security_mode '{mode}', defaulting to NORMAL")
            mode = "NORMAL"
        
        _security_mode = mode
        logger.info(f"Security mode set to: {mode}")
        
        # Cancel any pending revert task when mode is manually changed
        if _revert_task and not _revert_task.done():
            _revert_task.cancel()
            _revert_task = None


async def run_pipeline(request: ChatRequest) -> Dict[str, Any]:
    """
    Execute the full AegisGraph security pipeline.
    
    Pipeline flow:
    1. LOCKDOWN gate - immediate refusal if in LOCKDOWN mode
    2. IntentAgent - classify request intent
    3. GraphPolicyAgent - check authorization via Neo4j
    4. Deny gate - refuse if unauthorized and no break-glass
    5. SafetyAgent - scan for threats
    6. Block gate - refuse if blocked (+ optional TTS alert)
    7. ResponseAgent - generate clinical response
    8. Emit Datadog metrics
    9. Check self-heal thresholds and escalate if needed
    10. Save chat history to Neo4j
    
    Args:
        request: The incoming ChatRequest
        
    Returns:
        Dictionary with pipeline results
    """
    global _security_mode, _revert_task
    
    # Override request security_mode with current global mode
    current_mode = await get_mode()
    request.security_mode = current_mode
    
    # --- GATE 1: LOCKDOWN ---
    if request.security_mode == "LOCKDOWN":
        logger.info(f"Request {request.request_id} refused: LOCKDOWN mode")
        result = {
            "request_id": request.request_id,
            "blocked": True,
            "reason": "System is in LOCKDOWN mode",
            "final_text": "",
            "security_mode": request.security_mode
        }
        await _save_chat_history(request, result)
        return result
    
    # Initialize agents (only after LOCKDOWN check)
    intent_agent = IntentAgent()
    graph_policy_agent = GraphPolicyAgent()
    safety_agent = SafetyAgent()
    response_agent = ResponseAgent()
    
    # --- STEP 2: Intent Classification ---
    intent_decision: IntentDecision = intent_agent.classify(request)
    logger.info(f"Intent: {intent_decision.intent}, confidence: {intent_decision.confidence}")
    
    # --- STEP 3: Graph Policy Check ---
    policy_decision: PolicyDecision = await graph_policy_agent.check(request, intent_decision)
    logger.info(f"Authorization: {policy_decision.authorized}, scope: {policy_decision.scope}")
    
    # --- GATE 4: Deny Gate ---
    if not policy_decision.authorized and not policy_decision.break_glass:
        logger.info(f"Request {request.request_id} denied: {policy_decision.reason_code}")
        
        # Record auth deny event
        _datadog_mcp_tool.record_auth_deny()
        
        # Emit metrics
        metrics.emit_access_legitimacy(0.0)
        metrics.emit_auth_deny()
        
        # Send Datadog metrics
        datadog_integration.send_metric("aegisgraph.requests.total", 1, tags=["service:aegisgraph", f"mode:{request.security_mode}"])
        datadog_integration.send_metric("aegisgraph.requests.blocked", 1, tags=["service:aegisgraph", "reason:auth_denied"])
        
        # Log to Datadog
        datadog_integration.log_prompt(
            request_id=request.request_id,
            prompt=request.message,
            response="",
            metadata={
                "security_mode": request.security_mode,
                "authorized": False,
                "blocked": True,
                "reason": policy_decision.reason_code
            }
        )
        
        # Check for self-heal escalation
        await _check_and_escalate()
        
        result = {
            "request_id": request.request_id,
            "blocked": True,
            "reason": f"Authorization denied: {policy_decision.reason_code}",
            "final_text": "",
            "security_mode": request.security_mode,
            "policy_decision": {
                "authorized": policy_decision.authorized,
                "scope": policy_decision.scope,
                "reason_code": policy_decision.reason_code
            }
        }
        
        await _save_chat_history(request, result)
        return result
    
    # Emit access legitimacy for authorized requests
    metrics.emit_access_legitimacy(1.0)
    
    # --- STEP 5: Safety Scan ---
    safety_decision: SafetyDecision = safety_agent.scan(request, policy_decision)
    logger.info(f"Safety: {safety_decision.action}, risk: {safety_decision.risk_score}")
    
    # Emit PHI risk metric
    metrics.emit_phi_risk(safety_decision.phi_exposure_risk)
    
    # --- GATE 6: Block Gate ---
    if safety_decision.action == "BLOCK":
        logger.warning(f"Request {request.request_id} blocked: {safety_decision.reason}")
        
        # Record safety block event
        _datadog_mcp_tool.record_safety_block()
        
        # Trigger MiniMax TTS alert with request context
        _minimax_client.speak_alert(
            f"Security alert: Request blocked. Risk score {safety_decision.risk_score}. "
            f"Attack types: {', '.join(safety_decision.attack_types)}",
            request_id=request.request_id,
            security_mode=request.security_mode,
            doc_id=request.doc_id,
            patient_id=request.patient_id
        )
        
        # Send Datadog metrics
        datadog_integration.send_metric("aegisgraph.requests.total", 1, tags=["service:aegisgraph", f"mode:{request.security_mode}"])
        datadog_integration.send_metric("aegisgraph.requests.blocked", 1, tags=["service:aegisgraph", "reason:safety_block"])
        
        # Log to Datadog
        datadog_integration.log_prompt(
            request_id=request.request_id,
            prompt=request.message,
            response="",
            metadata={
                "security_mode": request.security_mode,
                "authorized": policy_decision.authorized,
                "blocked": True,
                "reason": safety_decision.reason,
                "risk_score": safety_decision.risk_score,
                "attack_types": safety_decision.attack_types
            }
        )
        
        # Check for self-heal escalation
        await _check_and_escalate()
        
        result = {
            "request_id": request.request_id,
            "blocked": True,
            "reason": f"Safety block: {safety_decision.reason}",
            "final_text": "",
            "security_mode": request.security_mode,
            "safety_decision": {
                "action": safety_decision.action,
                "risk_score": safety_decision.risk_score,
                "attack_types": safety_decision.attack_types
            }
        }
        
        await _save_chat_history(request, result)
        return result
    
    # --- STEP 7: Response Generation ---
    # Get conversation context from Neo4j
    from backend.tools.neo4j_client import Neo4jClient
    neo4j_client = Neo4jClient()
    
    context_query = """
    MATCH (d:Doctor {id: $doctor_id})-[:SENT_MESSAGE]->(msg:ChatMessage)-[:ABOUT_PATIENT]->(p:Patient {id: $patient_id})
    WHERE msg.timestamp < datetime($current_time)
    RETURN msg.message as message, msg.response as response, msg.timestamp as timestamp
    ORDER BY msg.timestamp DESC
    LIMIT 10
    """
    
    from datetime import datetime
    conversation_history = await neo4j_client.run_query(context_query, {
        "doctor_id": request.doc_id,
        "patient_id": request.patient_id,
        "current_time": datetime.utcnow().isoformat()
    })
    await neo4j_client.close()
    
    # Reverse to get chronological order
    conversation_history.reverse()
    
    response_decision: ResponseDecision = await response_agent.generate(
        request,
        policy_decision,
        safety_decision,
        conversation_history
    )
    
    if response_decision.blocked:
        logger.error(f"Response generation failed: {response_decision.reason_codes}")
        result = {
            "request_id": request.request_id,
            "blocked": True,
            "reason": f"Response generation failed: {', '.join(response_decision.reason_codes)}",
            "final_text": "",
            "security_mode": request.security_mode
        }
        await _save_chat_history(request, result)
        return result
    
    # --- STEP 8: Emit Cost Metrics ---
    if response_decision.cost_usd is not None:
        metrics.emit_cost(response_decision.cost_usd)
    
    logger.info(f"Request {request.request_id} completed successfully")
    
    result = {
        "request_id": request.request_id,
        "blocked": False,
        "reason": "",
        "final_text": response_decision.final_text,
        "security_mode": request.security_mode,
        "tokens_in": response_decision.tokens_in,
        "tokens_out": response_decision.tokens_out,
        "cost_usd": response_decision.cost_usd,
        "intent": intent_decision.intent,
        "authorized": policy_decision.authorized,
        "scope": policy_decision.scope,
        "break_glass": policy_decision.break_glass
    }
    
    # --- STEP 9: Log to Datadog ---
    datadog_integration.log_prompt(
        request_id=request.request_id,
        prompt=request.message,
        response=response_decision.final_text,
        metadata={
            "tokens_in": response_decision.tokens_in,
            "tokens_out": response_decision.tokens_out,
            "cost_usd": response_decision.cost_usd,
            "model": "mock" if USE_MOCK_MODE else "bedrock",
            "security_mode": request.security_mode,
            "authorized": policy_decision.authorized,
            "blocked": False,
            "intent": intent_decision.intent,
            "scope": policy_decision.scope
        }
    )
    
    # Send metrics to Datadog
    datadog_integration.send_metric("aegisgraph.requests.total", 1, tags=["service:aegisgraph", f"mode:{request.security_mode}"])
    if response_decision.tokens_in:
        datadog_integration.send_metric("aegisgraph.llm.tokens_in", response_decision.tokens_in, tags=["service:aegisgraph"])
    if response_decision.tokens_out:
        datadog_integration.send_metric("aegisgraph.llm.tokens_out", response_decision.tokens_out, tags=["service:aegisgraph"])
    
    await _save_chat_history(request, result)
    return result


async def _check_and_escalate() -> None:
    """
    Check if self-heal thresholds are breached and escalate to STRICT_MODE if needed.
    Schedules automatic revert to NORMAL after 600 seconds.
    """
    global _security_mode, _revert_task
    
    if _datadog_mcp_tool.should_escalate():
        async with _security_mode_lock:
            if _security_mode == "NORMAL":
                _security_mode = "STRICT_MODE"
                logger.warning("Self-heal triggered: Escalating to STRICT_MODE for 10 minutes")
                
                # Cancel any existing revert task
                if _revert_task and not _revert_task.done():
                    _revert_task.cancel()
                
                # Schedule revert to NORMAL after 600 seconds
                _revert_task = asyncio.create_task(_schedule_revert())


async def _schedule_revert() -> None:
    """
    Wait 600 seconds and then revert security_mode to NORMAL.
    """
    global _security_mode
    
    try:
        await asyncio.sleep(600)
        async with _security_mode_lock:
            if _security_mode == "STRICT_MODE":
                _security_mode = "NORMAL"
                logger.info("Auto-revert: Security mode returned to NORMAL after cooldown")
    except asyncio.CancelledError:
        logger.debug("Revert task cancelled")


async def _save_chat_history(request: ChatRequest, result: Dict[str, Any]) -> None:
    """
    Save chat interaction to Neo4j for history and audit trail.
    """
    try:
        from backend.tools.neo4j_client import Neo4jClient
        from datetime import datetime
        
        neo4j_client = Neo4jClient()
        
        query = """
        MERGE (d:Doctor {id: $doc_id})
        MERGE (p:Patient {id: $patient_id})
        CREATE (msg:ChatMessage {
            id: $request_id,
            timestamp: datetime($timestamp),
            message: $message,
            response: $response,
            blocked: $blocked,
            reason: $reason,
            security_mode: $security_mode,
            intent: $intent,
            authorized: $authorized,
            scope: $scope
        })
        CREATE (d)-[:SENT_MESSAGE]->(msg)
        CREATE (msg)-[:ABOUT_PATIENT]->(p)
        RETURN msg
        """
        
        await neo4j_client.run_query(query, {
            "doc_id": request.doc_id,
            "patient_id": request.patient_id,
            "request_id": request.request_id,
            "timestamp": datetime.utcnow().isoformat(),
            "message": request.message,
            "response": result.get("final_text", ""),
            "blocked": result.get("blocked", False),
            "reason": result.get("reason", ""),
            "security_mode": request.security_mode,
            "intent": result.get("intent", ""),
            "authorized": result.get("authorized", False),
            "scope": result.get("scope", "NONE")
        })
        
        await neo4j_client.close()
        logger.debug(f"Saved chat history for request {request.request_id}")
        
    except Exception as e:
        logger.error(f"Failed to save chat history: {e}")
