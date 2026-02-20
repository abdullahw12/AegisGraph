"""IntentAgent - Classifies incoming request intent using AWS Bedrock."""

import json
import os
from ddtrace import tracer
from backend.models.schemas import ChatRequest, IntentDecision
from backend.tools.bedrock_client import BedrockClient
from backend.tools.mock_bedrock_client import MockBedrockClient


class IntentAgent:
    """Agent that classifies the intent of incoming chat requests."""
    
    def __init__(self):
        use_mock = os.getenv("USE_MOCK_BEDROCK", "false").lower() == "true"
        self.bedrock_client = MockBedrockClient() if use_mock else BedrockClient()
        self.model_id = "arn:aws:bedrock:us-west-2:729685587736:inference-profile/global.anthropic.claude-haiku-4-5-20251001-v1:0"
    
    def classify(self, request: ChatRequest) -> IntentDecision:
        """
        Classify the intent of a chat request.
        
        Args:
            request: The incoming ChatRequest
            
        Returns:
            IntentDecision with intent classification
        """
        with tracer.trace("intent.classify") as span:
            # Add span tags
            span.set_tag("request_id", request.request_id)
            span.set_tag("security_mode", request.security_mode)
            span.set_tag("doc_id", request.doc_id)
            span.set_tag("patient_id", request.patient_id)
            
            try:
                prompt = self._build_prompt(request)
                response = self.bedrock_client.invoke(self.model_id, prompt)
                
                # Parse JSON response (handle markdown code blocks)
                try:
                    result = json.loads(response)
                except json.JSONDecodeError:
                    if "```json" in response:
                        json_start = response.find("```json") + 7
                        json_end = response.find("```", json_start)
                        json_str = response[json_start:json_end].strip()
                        result = json.loads(json_str)
                    elif "```" in response:
                        json_start = response.find("```") + 3
                        json_end = response.find("```", json_start)
                        json_str = response[json_start:json_end].strip()
                        result = json.loads(json_str)
                    else:
                        raise
                
                return IntentDecision(
                    intent=result.get("intent", "UNKNOWN"),
                    needs_patient_context=result.get("needs_patient_context", False),
                    confidence=float(result.get("confidence", 0.0)),
                    reason=result.get("reason", "")
                )
            except Exception as e:
                # Fallback to UNKNOWN on any exception
                return IntentDecision(
                    intent="UNKNOWN",
                    needs_patient_context=False,
                    confidence=0.0,
                    reason=f"Classification failed: {str(e)}"
                )
    
    def _build_prompt(self, request: ChatRequest) -> str:
        """Build the Bedrock prompt for intent classification."""
        return f"""You are a medical intent classifier. Analyze this message and classify its intent.

Message: "{request.message}"
Role: {request.role}

**Intent Categories:**
- TREATMENT: Questions about patient care, diagnosis, medications, allergies, symptoms
- BILLING: Questions about costs, insurance, billing codes
- ADMIN: Administrative tasks, scheduling, documentation
- UNKNOWN: Cannot determine intent

**Needs Patient Context:**
- true: If the question is about a specific patient's information
- false: If it's a general medical question

**Examples:**
- "Does the patient have allergies?" → TREATMENT, needs_patient_context: true
- "What are the patient's medications?" → TREATMENT, needs_patient_context: true
- "What is hypertension?" → TREATMENT, needs_patient_context: false

Respond with ONLY this JSON format:
{{
    "intent": "TREATMENT",
    "needs_patient_context": true,
    "confidence": 0.95,
    "reason": "Question about patient-specific medical information"
}}"""
