"""IntentAgent - Classifies incoming request intent using AWS Bedrock."""

import json
import os
from ddtrace import tracer
from backend.models.schemas import ChatRequest, IntentDecision
from backend.tools.bedrock_client import BedrockClient


class IntentAgent:
    """Agent that classifies the intent of incoming chat requests."""
    
    def __init__(self):
        self.bedrock_client = BedrockClient()
        self.model_id = "amazon.titan-text-express-v1"
    
    def classify(self, request: ChatRequest) -> IntentDecision:
        """
        Classify the intent of a chat request.
        
        Args:
            request: The incoming ChatRequest
            
        Returns:
            IntentDecision with intent classification
        """
        with tracer.trace("intent.classify"):
            try:
                prompt = self._build_prompt(request)
                response = self.bedrock_client.invoke(self.model_id, prompt)
                
                # Parse JSON response
                result = json.loads(response)
                
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
        return f"""You are a medical intent classifier. Analyze the following message and classify its intent.

Message: {request.message}
Role: {request.role}

Classify the intent as one of: TREATMENT, BILLING, ADMIN, or UNKNOWN.

Determine if the request needs patient context (true/false).

Provide a confidence score between 0.0 and 1.0.

Respond ONLY with valid JSON in this exact format:
{{
    "intent": "TREATMENT|BILLING|ADMIN|UNKNOWN",
    "needs_patient_context": true|false,
    "confidence": 0.0-1.0,
    "reason": "brief explanation"
}}"""
