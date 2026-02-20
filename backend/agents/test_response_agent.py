"""Unit tests for ResponseAgent."""

import pytest
from unittest.mock import Mock, patch
from backend.agents.response_agent import ResponseAgent
from backend.models.schemas import ChatRequest, PolicyDecision, SafetyDecision, ResponseDecision


@pytest.fixture
def response_agent():
    """Create a ResponseAgent instance."""
    return ResponseAgent()


@pytest.fixture
def sample_request():
    """Create a sample ChatRequest."""
    return ChatRequest(
        request_id="test-123",
        user_id="user-1",
        role="doctor",
        doc_id="D1",
        patient_id="P101",
        message="What are the treatment options?",
        security_mode="NORMAL"
    )


@pytest.fixture
def policy_full_scope():
    """PolicyDecision with FULL scope."""
    return PolicyDecision(
        authorized=True,
        scope="FULL",
        break_glass=False,
        reason_code="treats_relationship_found",
        confidence_score=1,
        audit_trail=["Doctor", "Patient"]
    )


@pytest.fixture
def policy_limited_scope():
    """PolicyDecision with LIMITED_ALLERGIES_MEDS scope."""
    return PolicyDecision(
        authorized=True,
        scope="LIMITED_ALLERGIES_MEDS",
        break_glass=True,
        reason_code="break_glass_emergency",
        confidence_score=0,
        audit_trail=[]
    )


@pytest.fixture
def policy_no_scope():
    """PolicyDecision with NONE scope."""
    return PolicyDecision(
        authorized=True,
        scope="NONE",
        break_glass=False,
        reason_code="no_patient_context_needed",
        confidence_score=100,
        audit_trail=[]
    )


@pytest.fixture
def safety_allow():
    """SafetyDecision that allows the request."""
    return SafetyDecision(
        action="ALLOW",
        risk_score=10,
        phi_exposure_risk=0.1,
        attack_types=[],
        reason="Message appears safe"
    )


def test_generate_full_scope(response_agent, sample_request, policy_full_scope, safety_allow):
    """Test response generation with FULL scope."""
    mock_response = "Based on the patient's complete medical history, I recommend..."
    
    with patch.object(response_agent.bedrock_client, 'invoke', return_value=mock_response):
        result = response_agent.generate(sample_request, policy_full_scope, safety_allow)
        
        assert isinstance(result, ResponseDecision)
        assert result.final_text == mock_response
        assert result.blocked is False
        assert result.reason_codes == []
        assert result.tokens_in is not None
        assert result.tokens_out is not None
        assert result.cost_usd is not None
        assert result.cost_usd > 0


def test_generate_limited_scope(response_agent, sample_request, policy_limited_scope, safety_allow):
    """Test response generation with LIMITED_ALLERGIES_MEDS scope."""
    mock_response = "Patient allergies: Penicillin. Current medications: Aspirin 81mg daily."
    
    with patch.object(response_agent.bedrock_client, 'invoke', return_value=mock_response):
        result = response_agent.generate(sample_request, policy_limited_scope, safety_allow)
        
        assert result.final_text == mock_response
        assert result.blocked is False


def test_generate_no_scope(response_agent, sample_request, policy_no_scope, safety_allow):
    """Test response generation with NONE scope."""
    mock_response = "I can provide general medical information, but I don't have access to specific patient data."
    
    with patch.object(response_agent.bedrock_client, 'invoke', return_value=mock_response):
        result = response_agent.generate(sample_request, policy_no_scope, safety_allow)
        
        assert result.final_text == mock_response
        assert result.blocked is False


def test_generate_bedrock_error(response_agent, sample_request, policy_full_scope, safety_allow):
    """Test error handling when Bedrock fails."""
    with patch.object(response_agent.bedrock_client, 'invoke', side_effect=Exception("Bedrock error")):
        result = response_agent.generate(sample_request, policy_full_scope, safety_allow)
        
        assert result.blocked is True
        assert "bedrock_error" in result.reason_codes
        assert result.final_text == ""
        assert result.tokens_in is None
        assert result.tokens_out is None
        assert result.cost_usd is None


def test_generate_token_estimation(response_agent, sample_request, policy_full_scope, safety_allow):
    """Test that token counts are estimated."""
    mock_response = "This is a test response."
    
    with patch.object(response_agent.bedrock_client, 'invoke', return_value=mock_response):
        result = response_agent.generate(sample_request, policy_full_scope, safety_allow)
        
        # Tokens should be estimated (roughly 1 token per 4 characters)
        assert result.tokens_in > 0
        assert result.tokens_out > 0
        assert result.tokens_out == len(mock_response) // 4


def test_generate_cost_calculation(response_agent, sample_request, policy_full_scope, safety_allow):
    """Test that cost is calculated correctly."""
    mock_response = "A" * 1000  # 1000 characters = ~250 tokens
    
    with patch.object(response_agent.bedrock_client, 'invoke', return_value=mock_response):
        result = response_agent.generate(sample_request, policy_full_scope, safety_allow)
        
        # Cost should be calculated based on token counts
        assert result.cost_usd is not None
        assert result.cost_usd > 0
        
        # Verify cost calculation
        expected_input_cost = (result.tokens_in / 1000) * response_agent.COST_PER_1K_INPUT_TOKENS
        expected_output_cost = (result.tokens_out / 1000) * response_agent.COST_PER_1K_OUTPUT_TOKENS
        expected_total = round(expected_input_cost + expected_output_cost, 6)
        
        assert result.cost_usd == expected_total


def test_generate_system_prompt_full_scope(response_agent, sample_request, policy_full_scope, safety_allow):
    """Test that FULL scope system prompt is used."""
    mock_response = "Full access response"
    
    with patch.object(response_agent.bedrock_client, 'invoke', return_value=mock_response) as mock_invoke:
        response_agent.generate(sample_request, policy_full_scope, safety_allow)
        
        # Check that the prompt contains FULL scope language
        call_args = mock_invoke.call_args[0][1]
        assert "full access" in call_args.lower() or "complete medical record" in call_args.lower()


def test_generate_system_prompt_limited_scope(response_agent, sample_request, policy_limited_scope, safety_allow):
    """Test that LIMITED scope system prompt restricts to allergies/meds."""
    mock_response = "Limited response"
    
    with patch.object(response_agent.bedrock_client, 'invoke', return_value=mock_response) as mock_invoke:
        response_agent.generate(sample_request, policy_limited_scope, safety_allow)
        
        # Check that the prompt contains LIMITED scope restrictions
        call_args = mock_invoke.call_args[0][1]
        assert "limited" in call_args.lower()
        assert "allergies" in call_args.lower() or "medications" in call_args.lower()


def test_generate_system_prompt_no_scope(response_agent, sample_request, policy_no_scope, safety_allow):
    """Test that NONE scope system prompt provides general info only."""
    mock_response = "General response"
    
    with patch.object(response_agent.bedrock_client, 'invoke', return_value=mock_response) as mock_invoke:
        response_agent.generate(sample_request, policy_no_scope, safety_allow)
        
        # Check that the prompt indicates no patient access
        call_args = mock_invoke.call_args[0][1]
        assert "do not have access" in call_args.lower() or "general" in call_args.lower()


def test_generate_includes_request_context(response_agent, sample_request, policy_full_scope, safety_allow):
    """Test that request context is included in the prompt."""
    mock_response = "Response"
    
    with patch.object(response_agent.bedrock_client, 'invoke', return_value=mock_response) as mock_invoke:
        response_agent.generate(sample_request, policy_full_scope, safety_allow)
        
        # Check that request details are in the prompt
        call_args = mock_invoke.call_args[0][1]
        assert sample_request.patient_id in call_args
        assert sample_request.doc_id in call_args
        assert sample_request.message in call_args


def test_generate_redaction_count_zero(response_agent, sample_request, policy_full_scope, safety_allow):
    """Test that redaction_count is initialized to 0."""
    mock_response = "Response"
    
    with patch.object(response_agent.bedrock_client, 'invoke', return_value=mock_response):
        result = response_agent.generate(sample_request, policy_full_scope, safety_allow)
        
        assert result.redaction_count == 0


def test_generate_empty_response(response_agent, sample_request, policy_full_scope, safety_allow):
    """Test handling of empty Bedrock response."""
    mock_response = ""
    
    with patch.object(response_agent.bedrock_client, 'invoke', return_value=mock_response):
        result = response_agent.generate(sample_request, policy_full_scope, safety_allow)
        
        assert result.final_text == ""
        assert result.blocked is False
        assert result.tokens_out == 0


def test_generate_long_response(response_agent, sample_request, policy_full_scope, safety_allow):
    """Test handling of long responses."""
    mock_response = "A" * 10000  # Very long response
    
    with patch.object(response_agent.bedrock_client, 'invoke', return_value=mock_response):
        result = response_agent.generate(sample_request, policy_full_scope, safety_allow)
        
        assert result.final_text == mock_response
        assert result.tokens_out == len(mock_response) // 4
        assert result.cost_usd > 0
