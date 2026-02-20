"""ResponseAgent - Generates clinical responses using AWS Bedrock."""

import json
from typing import Optional
from ddtrace import tracer
from backend.models.schemas import ChatRequest, PolicyDecision, SafetyDecision, ResponseDecision
from backend.tools.bedrock_client import BedrockClient


class ResponseAgent:
    """Agent that generates clinical responses."""
    
    # Bedrock pricing (approximate, per 1K tokens)
    COST_PER_1K_INPUT_TOKENS = 0.0008  # $0.0008 per 1K input tokens
    COST_PER_1K_OUTPUT_TOKENS = 0.0016  # $0.0016 per 1K output tokens
    
    def __init__(self):
        self.bedrock_client = BedrockClient()
        self.model_id = "amazon.titan-text-express-v1"
    
    def generate(
        self,
        request: ChatRequest,
        policy_decision: PolicyDecision,
        safety_decision: SafetyDecision
    ) -> ResponseDecision:
        """
        Generate a clinical response.
        
        Args:
            request: The incoming ChatRequest
            policy_decision: The authorization result
            safety_decision: The safety scan result
            
        Returns:
            ResponseDecision with generated response
        """
        with tracer.trace("llm.generate"):
            try:
                # Build scoped system prompt
                system_prompt = self._build_system_prompt(policy_decision.scope)
                prompt = self._build_prompt(system_prompt, request)
                
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
            return """You are a helpful medical assistant with full access to patient information.
Provide accurate, professional clinical responses based on the patient's complete medical record.
Always maintain HIPAA compliance and patient confidentiality."""
        
        elif scope == "LIMITED_ALLERGIES_MEDS":
            return """You are a helpful medical assistant with LIMITED access to patient information.
You may ONLY provide information about:
- Patient allergies
- Current medications
- Medication interactions

DO NOT provide any other patient information. If asked about anything else, politely decline."""
        
        else:  # NONE
            return """You are a helpful medical assistant.
You do not have access to specific patient information.
Provide general medical information only."""
    
    def _build_prompt(self, system_prompt: str, request: ChatRequest) -> str:
        """Build the complete prompt for Bedrock."""
        return f"""{system_prompt}

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
