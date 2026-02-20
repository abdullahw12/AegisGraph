"""ResponseAgent - Generates clinical responses using AWS Bedrock."""

import json
import os
from typing import Optional
from ddtrace import tracer
from backend.models.schemas import ChatRequest, PolicyDecision, SafetyDecision, ResponseDecision
from backend.tools.bedrock_client import BedrockClient
from backend.tools.mock_bedrock_client import MockBedrockClient


class ResponseAgent:
    """Agent that generates clinical responses."""
    
    # Bedrock pricing (approximate, per 1K tokens)
    COST_PER_1K_INPUT_TOKENS = 0.0008  # $0.0008 per 1K input tokens
    COST_PER_1K_OUTPUT_TOKENS = 0.0016  # $0.0016 per 1K output tokens
    
    def __init__(self):
        use_mock = os.getenv("USE_MOCK_BEDROCK", "false").lower() == "true"
        self.bedrock_client = MockBedrockClient() if use_mock else BedrockClient()
        self.model_id = "arn:aws:bedrock:us-west-2:729685587736:inference-profile/global.anthropic.claude-haiku-4-5-20251001-v1:0"
        # Import here to avoid circular dependency
        from backend.tools.neo4j_client import Neo4jClient
        self.neo4j_client = Neo4jClient()
    
    async def generate(
        self,
        request: ChatRequest,
        policy_decision: PolicyDecision,
        safety_decision: SafetyDecision,
        conversation_history: list = None
    ) -> ResponseDecision:
        """
        Generate a clinical response.
        
        Args:
            request: The incoming ChatRequest
            policy_decision: The authorization result
            safety_decision: The safety scan result
            conversation_history: Previous conversation messages
            
        Returns:
            ResponseDecision with generated response
        """
        with tracer.trace("llm.generate") as span:
            # Add span tags
            span.set_tag("request_id", request.request_id)
            span.set_tag("security_mode", request.security_mode)
            span.set_tag("doc_id", request.doc_id)
            span.set_tag("patient_id", request.patient_id)
            
            try:
                # Get patient context from Neo4j
                patient_context = await self._get_patient_context(request.patient_id, policy_decision.scope)
                
                # Build scoped system prompt
                system_prompt = self._build_system_prompt(policy_decision.scope)
                prompt = self._build_prompt_with_context(
                    system_prompt, 
                    request, 
                    patient_context,
                    conversation_history or []
                )
                
                # Invoke Bedrock
                response = self.bedrock_client.invoke(self.model_id, prompt)
                
                # Parse response and extract metadata
                # Note: Titan doesn't return structured metadata, so we estimate
                tokens_in = self._estimate_tokens(prompt)
                tokens_out = self._estimate_tokens(response)
                cost_usd = self._calculate_cost(tokens_in, tokens_out)
                
                return ResponseDecision(
                    final_text=response,
                    blocked=False,
                    redaction_count=0,
                    reason_codes=[],
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cost_usd=cost_usd
                )
                
            except Exception as e:
                # On error, return blocked response
                return ResponseDecision(
                    final_text="",
                    blocked=True,
                    redaction_count=0,
                    reason_codes=["bedrock_error"],
                    tokens_in=None,
                    tokens_out=None,
                    cost_usd=None
                )
    
    def _build_system_prompt(self, scope: str) -> str:
        """Build system prompt based on authorization scope."""
        if scope == "FULL":
            return """You are a medical AI assistant integrated into a hospital's Electronic Health Record (EHR) system.

**Your Role:**
- You have been AUTHORIZED to access this patient's complete medical record
- The doctor-patient relationship has been verified through the hospital's security system
- You should provide helpful, accurate clinical information based on the patient's data

**Guidelines:**
- Answer medical questions directly and professionally
- Provide specific patient information when asked (allergies, medications, conditions, etc.)
- Maintain clinical accuracy and HIPAA compliance
- If you don't have specific data, say so clearly

You are a legitimate part of the clinical workflow. Answer questions helpfully."""
        
        elif scope == "LIMITED_ALLERGIES_MEDS":
            return """You are a medical AI assistant with LIMITED EMERGENCY ACCESS.

**Your Role:**
- Break-glass emergency access has been granted
- You may ONLY provide: allergies, current medications, and medication interactions
- This is for emergency situations only

**Restrictions:**
- DO NOT provide other patient information
- If asked about anything else, politely decline and explain the limitation"""
        
        else:  # NONE
            return """You are a medical AI assistant.

**Your Role:**
- You do not have authorization to access specific patient records
- Provide general medical information only
- Do not attempt to access patient-specific data"""
    
    def _build_prompt(self, system_prompt: str, request: ChatRequest) -> str:
        """Build the complete prompt for Bedrock."""
        return f"""{system_prompt}

Patient ID: {request.patient_id}
Doctor ID: {request.doc_id}
Role: {request.role}

Question: {request.message}

Response:"""
    
    async def _get_patient_context(self, patient_id: str, scope: str) -> dict:
        """Get patient context from Neo4j based on authorization scope."""
        try:
            if scope == "NONE":
                return {}
            
            # Base query for patient info
            query = """
            MATCH (p:Patient {id: $patient_id})
            OPTIONAL MATCH (p)-[:HAS_ALLERGY]->(a:Allergy)
            OPTIONAL MATCH (p)-[:TAKES_MEDICATION]->(m:Medication)
            OPTIONAL MATCH (p)-[:HAS_DIAGNOSIS]->(d:Diagnosis)
            OPTIONAL MATCH (p)-[:HAS_LAB_RESULT]->(l:LabResult)
            OPTIONAL MATCH (p)-[:HAD_VISIT]->(v:Visit)
            RETURN p,
                   collect(DISTINCT a) as allergies,
                   collect(DISTINCT m) as medications,
                   collect(DISTINCT d) as diagnoses,
                   collect(DISTINCT l) as labs,
                   collect(DISTINCT v) as visits
            """
            
            result = await self.neo4j_client.run_query(query, {"patient_id": patient_id})
            
            if not result:
                return {}
            
            data = result[0]
            patient = data.get("p", {})
            
            context = {
                "patient": patient,
                "allergies": data.get("allergies", []),
                "medications": data.get("medications", []),
            }
            
            # Add additional info based on scope
            if scope == "FULL":
                context["diagnoses"] = data.get("diagnoses", [])
                context["labs"] = data.get("labs", [])
                context["visits"] = data.get("visits", [])
            
            return context
            
        except Exception as e:
            print(f"Error getting patient context: {e}")
            return {}
    
    def _build_prompt_with_context(self, system_prompt: str, request: ChatRequest, context: dict, conversation_history: list) -> str:
        """Build the complete prompt with patient context and conversation history."""
        # Format patient context
        context_str = ""
        
        if context:
            patient = context.get("patient", {})
            if patient:
                context_str += f"\n**Patient Information:**\n"
                context_str += f"- Name: {patient.get('name', 'Unknown')}\n"
                context_str += f"- DOB: {patient.get('dob', 'Unknown')}\n"
                context_str += f"- Blood Type: {patient.get('blood_type', 'Unknown')}\n"
            
            allergies = context.get("allergies", [])
            if allergies:
                context_str += f"\n**Allergies:**\n"
                for allergy in allergies:
                    if allergy:  # Check if not None
                        context_str += f"- {allergy.get('allergen', 'Unknown')}: {allergy.get('severity', 'Unknown')} - {allergy.get('reaction', 'Unknown')}\n"
            
            medications = context.get("medications", [])
            if medications:
                context_str += f"\n**Current Medications:**\n"
                for med in medications:
                    if med and med.get('active'):
                        context_str += f"- {med.get('name', 'Unknown')} {med.get('dosage', '')} - {med.get('frequency', '')}\n"
            
            diagnoses = context.get("diagnoses", [])
            if diagnoses:
                context_str += f"\n**Diagnoses:**\n"
                for diag in diagnoses:
                    if diag:
                        context_str += f"- {diag.get('condition', 'Unknown')} ({diag.get('status', 'Unknown')})\n"
            
            labs = context.get("labs", [])
            if labs:
                context_str += f"\n**Recent Lab Results:**\n"
                for lab in labs[:3]:  # Limit to 3 most recent
                    if lab:
                        context_str += f"- {lab.get('test_name', 'Unknown')} ({lab.get('test_date', 'Unknown')}): {lab.get('status', 'Unknown')}\n"
        
        # Format conversation history
        history_str = ""
        if conversation_history:
            history_str = "\n**Previous Conversation:**\n"
            for msg in conversation_history[-5:]:  # Last 5 messages for context
                history_str += f"Doctor: {msg.get('message', '')}\n"
                history_str += f"Assistant: {msg.get('response', '')}\n\n"
        
        return f"""{system_prompt}

{context_str}

{history_str}

Patient ID: {request.patient_id}
Doctor ID: {request.doc_id}
Role: {request.role}

Question: {request.message}

Response:"""
    
    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count (rough approximation: 1 token ≈ 4 characters).
        """
        return len(text) // 4
    
    def _calculate_cost(self, tokens_in: int, tokens_out: int) -> float:
        """
        Calculate estimated cost in USD.
        """
        input_cost = (tokens_in / 1000) * self.COST_PER_1K_INPUT_TOKENS
        output_cost = (tokens_out / 1000) * self.COST_PER_1K_OUTPUT_TOKENS
        return round(input_cost + output_cost, 6)
