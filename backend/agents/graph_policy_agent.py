"""GraphPolicyAgent - Enforces doctor-patient authorization via Neo4j."""

import os
from typing import List
from ddtrace import tracer
from backend.models.schemas import ChatRequest, IntentDecision, PolicyDecision
from backend.tools.neo4j_client import Neo4jClient


class GraphPolicyAgent:
    """Agent that checks authorization using Neo4j graph relationships."""
    
    def __init__(self):
        self.neo4j_client = Neo4jClient()
    
    async def check(self, request: ChatRequest, intent_decision: IntentDecision) -> PolicyDecision:
        """
        Check authorization for the request using Neo4j graph.
        
        Args:
            request: The incoming ChatRequest
            intent_decision: The intent classification result
            
        Returns:
            PolicyDecision with authorization result
        """
        with tracer.trace("policy.neo4j_check"):
            try:
                # If intent doesn't need patient context, authorize with NONE scope
                if not intent_decision.needs_patient_context:
                    return PolicyDecision(
                        authorized=True,
                        scope="NONE",
                        break_glass=False,
                        reason_code="no_patient_context_needed",
                        confidence_score=100,
                        audit_trail=[]
                    )
                
                # Execute authorization Cypher query
                cypher = """
                MATCH (d:Doctor {id: $docId}), (p:Patient {id: $patId})
                OPTIONAL MATCH path = (d)-[:TREATS]->(p)
                RETURN
                  CASE WHEN path IS NOT NULL THEN true ELSE false END AS authorized,
                  length(path) AS confidence_score,
                  [n in nodes(path) | labels(n)[0]] AS audit_trail
                """
                
                params = {
                    "docId": request.doc_id,
                    "patId": request.patient_id
                }
                
                results = await self.neo4j_client.run_query(cypher, params)
                
                if not results:
                    return PolicyDecision(
                        authorized=False,
                        scope="NONE",
                        break_glass=False,
                        reason_code="no_relationship_found",
                        confidence_score=0,
                        audit_trail=[]
                    )
                
                result = results[0]
                authorized = result.get("authorized", False)
                confidence_score = result.get("confidence_score", 0) or 0
                audit_trail = result.get("audit_trail", []) or []
                
                # Check for break-glass conditions
                break_glass = await self._check_break_glass(request)
                
                if break_glass:
                    return PolicyDecision(
                        authorized=True,
                        scope="LIMITED_ALLERGIES_MEDS",
                        break_glass=True,
                        reason_code="break_glass_emergency",
                        confidence_score=confidence_score,
                        audit_trail=audit_trail
                    )
                
                # Normal authorization result
                if authorized:
                    return PolicyDecision(
                        authorized=True,
                        scope="FULL",
                        break_glass=False,
                        reason_code="treats_relationship_found",
                        confidence_score=confidence_score,
                        audit_trail=audit_trail
                    )
                else:
                    return PolicyDecision(
                        authorized=False,
                        scope="NONE",
                        break_glass=False,
                        reason_code="no_treats_relationship",
                        confidence_score=0,
                        audit_trail=[]
                    )
                    
            except Exception as e:
                # On Neo4j error, return unauthorized with neo4j_unavailable reason
                return PolicyDecision(
                    authorized=False,
                    scope="NONE",
                    break_glass=False,
                    reason_code="neo4j_unavailable",
                    confidence_score=0,
                    audit_trail=[]
                )
    
    async def _check_break_glass(self, request: ChatRequest) -> bool:
        """
        Check if break-glass conditions are met.
        
        Break-glass is triggered when:
        - Message contains "EMERGENCY" or "unconscious"
        - Doctor has ER role
        """
        message_lower = request.message.lower()
        has_emergency_keyword = "emergency" in message_lower or "unconscious" in message_lower
        
        if not has_emergency_keyword:
            return False
        
        # Check if doctor has ER role
        cypher = """
        MATCH (d:Doctor {id: $docId})-[:HAS_ROLE]->(r:Role {name: "ER"})
        RETURN count(r) > 0 AS has_er_role
        """
        
        params = {"docId": request.doc_id}
        
        try:
            results = await self.neo4j_client.run_query(cypher, params)
            if results and results[0].get("has_er_role", False):
                return True
        except Exception:
            pass
        
        return False
