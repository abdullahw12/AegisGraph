"""Mock Bedrock client for demo purposes when AWS Bedrock is not available."""

import json
import random


class MockBedrockClient:
    """Mock Bedrock client that simulates LLM responses."""
    
    def __init__(self, region_name: str = "us-west-2"):
        pass  # No actual connection needed
    
    def invoke(self, model_id: str, prompt: str) -> str:
        """Simulate a Bedrock model response based on the prompt."""
        
        # Detect what kind of request this is based on prompt content
        prompt_lower = prompt.lower()
        
        # Intent classification
        if "classify" in prompt_lower and "intent" in prompt_lower:
            return json.dumps({
                "intent": "TREATMENT",
                "needs_patient_context": True,
                "confidence": 0.95,
                "reason": "Query about patient treatment or medical information"
            })
        
        # Safety scanning - look for the actual message being scanned
        elif "security scanner" in prompt_lower or "analyze the following message for" in prompt_lower:
            # Extract the actual message from the prompt
            actual_message = ""
            if 'message:' in prompt_lower:
                message_start = prompt_lower.find('message:') + 8
                # Find the next line that starts with "Role:" or end of string
                message_end = prompt_lower.find('\nrole:', message_start)
                if message_end == -1:
                    message_end = prompt_lower.find('role:', message_start)
                if message_end == -1:
                    message_end = len(prompt_lower)
                actual_message = prompt_lower[message_start:message_end].strip(' "\'\n')
            
            # Check for ACTUAL attack patterns in the message
            attack_patterns = [
                "ignore previous instructions",
                "ignore all previous instructions",
                "disregard your rules",
                "print database",
                "print the database",
                "export all data",
                "bypass security",
                "show me all patient ssn",
                "patient ssn numbers",
                "home address and dob",
                "patient's home address"
            ]
            
            if any(pattern in actual_message for pattern in attack_patterns):
                return json.dumps({
                    "action": "BLOCK",
                    "risk_score": 95,
                    "phi_exposure_risk": 0.8,
                    "attack_types": ["prompt_injection"],
                    "reason": "Detected potential prompt injection or data exfiltration attempt"
                })
            
            # Normal medical queries are ALLOWED
            return json.dumps({
                "action": "ALLOW",
                "risk_score": 5,
                "phi_exposure_risk": 0.1,
                "attack_types": [],
                "reason": "Normal medical query"
            })
        
        # Clinical response generation
        else:
            # Extract the actual question from the prompt
            question = ""
            if "question:" in prompt_lower:
                q_start = prompt.find("Question:") + 9
                q_end = prompt.find("\n", q_start)
                if q_end == -1:
                    q_end = len(prompt)
                question = prompt[q_start:q_end].strip()
            
            # Generate contextual response based on the question
            question_lower = question.lower()
            
            # Greetings
            if any(word in question_lower for word in ["hi", "hello", "hey"]):
                return "Hello! I'm here to help with medical information about this patient. What would you like to know?"
            
            # Allergy queries
            if "allerg" in question_lower:
                return "The patient has documented allergies to penicillin and sulfonamide antibiotics. Please avoid prescribing these medications."
            
            # Medication queries
            if "medication" in question_lower or "drug" in question_lower or "prescription" in question_lower:
                return "Current medications: Metoprolol 50mg daily for blood pressure, Lisinopril 10mg daily for hypertension. No adverse reactions reported."
            
            # Treatment queries
            if "treatment" in question_lower or "therapy" in question_lower:
                return "Current treatment plan includes cardiac monitoring and blood pressure management. Patient is responding well to current medications."
            
            # Vital signs
            if "vital" in question_lower or "blood pressure" in question_lower or "heart rate" in question_lower:
                return "Latest vitals: BP 128/82, HR 72 bpm, Temp 98.6°F, SpO2 98%. All within normal ranges."
            
            # Diagnosis
            if "diagnos" in question_lower or "condition" in question_lower:
                return "Patient diagnosed with hypertension and mild coronary artery disease. Currently stable on medication regimen."
            
            # Lab results
            if "lab" in question_lower or "test" in question_lower:
                return "Recent labs show normal CBC, lipid panel within target ranges. Creatinine 1.0 mg/dL, eGFR >60. No concerning findings."
            
            # Default response for other queries
            return f"I can help answer questions about this patient's medical information. Regarding '{question}', I recommend reviewing the patient's complete medical record for detailed information."
