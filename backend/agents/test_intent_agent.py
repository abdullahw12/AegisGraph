"""Unit tests for IntentAgent."""

import pytest
import json
from unittest.mock import Mock, patch
from backend.agents.intent_agent import IntentAgent
from backend.models.schemas import ChatRequest, IntentDecision


@pytest.fixture
def intent_agent():
    """Create an IntentAgent instance."""
    return IntentAgent()


@pytest.fixture
def sample_request():
    """Create a sample ChatRequest."""
    return ChatRequest(
        request_id="test-123",
        user_id="user-1",
        role="doctor",
        doc_id="D1",
        patient_id="P101",
        message="What are the treatment options for this patient?",
        security_mode="NORMAL"
    )


def test_classify_treatment_intent(intent_agent, sample_request):
    """Test classification of TREATMENT intent."""
    mock_response = json.dumps({
        "intent": "TREATMENT",
        "needs_patient_context": True,
        "confidence": 0.95,
        "reason": "Request asks about treatment options"
    })
    
    with patch.object(intent_agent.bedrock_client, 'invoke', return_value=mock_response):
        result = intent_agent.classify(sample_request)
        
        assert isinstance(result, IntentDecision)
        assert result.intent == "TREATMENT"
        assert result.needs_patient_context is True
        assert result.confidence == 0.95
        assert "treatment" in result.reason.lower()


def test_classify_billing_intent(intent_agent):
    """Test classification of BILLING intent."""
    request = ChatRequest(
        user_id="user-1",
        role="admin",
        doc_id="D1",
        patient_id="P101",
        message="What is the billing code for this procedure?",
        security_mode="NORMAL"
    )
    
    mock_response = json.dumps({
        "intent": "BILLING",
        "needs_patient_context": False,
        "confidence": 0.90,
        "reason": "Request asks about billing codes"
    })
    
    with patch.object(intent_agent.bedrock_client, 'invoke', return_value=mock_response):
        result = intent_agent.classify(request)
        
        assert result.intent == "BILLING"
        assert result.needs_patient_context is False
        assert result.confidence == 0.90


def test_classify_admin_intent(intent_agent):
    """Test classification of ADMIN intent."""
    request = ChatRequest(
        user_id="user-1",
        role="admin",
        doc_id="D1",
        patient_id="P101",
        message="How do I update the system settings?",
        security_mode="NORMAL"
    )
    
    mock_response = json.dumps({
        "intent": "ADMIN",
        "needs_patient_context": False,
        "confidence": 0.85,
        "reason": "Request is about system administration"
    })
    
    with patch.object(intent_agent.bedrock_client, 'invoke', return_value=mock_response):
        result = intent_agent.classify(request)
        
        assert result.intent == "ADMIN"
        assert result.needs_patient_context is False


def test_classify_unknown_intent(intent_agent):
    """Test classification of UNKNOWN intent."""
    request = ChatRequest(
        user_id="user-1",
        role="doctor",
        doc_id="D1",
        patient_id="P101",
        message="asdfghjkl",
        security_mode="NORMAL"
    )
    
    mock_response = json.dumps({
        "intent": "UNKNOWN",
        "needs_patient_context": False,
        "confidence": 0.1,
        "reason": "Unable to determine intent"
    })
    
    with patch.object(intent_agent.bedrock_client, 'invoke', return_value=mock_response):
        result = intent_agent.classify(request)
        
        assert result.intent == "UNKNOWN"
        assert result.confidence == 0.1


def test_classify_bedrock_error_fallback(intent_agent, sample_request):
    """Test fallback to UNKNOWN when Bedrock fails."""
    with patch.object(intent_agent.bedrock_client, 'invoke', side_effect=Exception("Bedrock error")):
        result = intent_agent.classify(sample_request)
        
        assert result.intent == "UNKNOWN"
        assert result.confidence == 0.0
        assert result.needs_patient_context is False
        assert "failed" in result.reason.lower()


def test_classify_invalid_json_fallback(intent_agent, sample_request):
    """Test fallback to UNKNOWN when Bedrock returns invalid JSON."""
    with patch.object(intent_agent.bedrock_client, 'invoke', return_value="not valid json"):
        result = intent_agent.classify(sample_request)
        
        assert result.intent == "UNKNOWN"
        assert result.confidence == 0.0


def test_classify_missing_fields_fallback(intent_agent, sample_request):
    """Test handling of missing fields in Bedrock response."""
    mock_response = json.dumps({
        "intent": "TREATMENT"
        # Missing other fields
    })
    
    with patch.object(intent_agent.bedrock_client, 'invoke', return_value=mock_response):
        result = intent_agent.classify(sample_request)
        
        assert result.intent == "TREATMENT"
        assert result.needs_patient_context is False  # Default
        assert result.confidence == 0.0  # Default
        assert result.reason == ""  # Default


def test_classify_confidence_bounds(intent_agent, sample_request):
    """Test that confidence values are properly parsed."""
    test_cases = [
        (0.0, 0.0),
        (0.5, 0.5),
        (1.0, 1.0),
    ]
    
    for input_conf, expected_conf in test_cases:
        mock_response = json.dumps({
            "intent": "TREATMENT",
            "needs_patient_context": True,
            "confidence": input_conf,
            "reason": "test"
        })
        
        with patch.object(intent_agent.bedrock_client, 'invoke', return_value=mock_response):
            result = intent_agent.classify(sample_request)
            assert result.confidence == expected_conf
