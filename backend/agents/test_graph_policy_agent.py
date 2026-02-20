"""Unit tests for GraphPolicyAgent."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from backend.agents.graph_policy_agent import GraphPolicyAgent
from backend.models.schemas import ChatRequest, IntentDecision, PolicyDecision


@pytest.fixture
def policy_agent():
    """Create a GraphPolicyAgent instance."""
    return GraphPolicyAgent()


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
def intent_needs_context():
    """Intent that needs patient context."""
    return IntentDecision(
        intent="TREATMENT",
        needs_patient_context=True,
        confidence=0.95,
        reason="Treatment query"
    )


@pytest.fixture
def intent_no_context():
    """Intent that doesn't need patient context."""
    return IntentDecision(
        intent="ADMIN",
        needs_patient_context=False,
        confidence=0.90,
        reason="Admin query"
    )


@pytest.mark.asyncio
async def test_check_no_patient_context_needed(policy_agent, sample_request, intent_no_context):
    """Test authorization when no patient context is needed."""
    result = await policy_agent.check(sample_request, intent_no_context)
    
    assert isinstance(result, PolicyDecision)
    assert result.authorized is True
    assert result.scope == "NONE"
    assert result.break_glass is False
    assert result.reason_code == "no_patient_context_needed"


@pytest.mark.asyncio
async def test_check_authorized_treats_relationship(policy_agent, sample_request, intent_needs_context):
    """Test authorization with valid TREATS relationship."""
    mock_results = [{
        "authorized": True,
        "confidence_score": 1,
        "audit_trail": ["Doctor", "Patient"]
    }]
    
    with patch.object(policy_agent.neo4j_client, 'run_query', new_callable=AsyncMock, return_value=mock_results):
        result = await policy_agent.check(sample_request, intent_needs_context)
        
        assert result.authorized is True
        assert result.scope == "FULL"
        assert result.break_glass is False
        assert result.reason_code == "treats_relationship_found"
        assert result.confidence_score == 1
        assert result.audit_trail == ["Doctor", "Patient"]


@pytest.mark.asyncio
async def test_check_denied_no_relationship(policy_agent, sample_request, intent_needs_context):
    """Test denial when no TREATS relationship exists."""
    mock_results = [{
        "authorized": False,
        "confidence_score": 0,
        "audit_trail": []
    }]
    
    with patch.object(policy_agent.neo4j_client, 'run_query', new_callable=AsyncMock, return_value=mock_results):
        result = await policy_agent.check(sample_request, intent_needs_context)
        
        assert result.authorized is False
        assert result.scope == "NONE"
        assert result.break_glass is False
        assert result.reason_code == "no_treats_relationship"


@pytest.mark.asyncio
async def test_check_break_glass_emergency(policy_agent, intent_needs_context):
    """Test break-glass activation with EMERGENCY keyword."""
    request = ChatRequest(
        user_id="user-1",
        role="doctor",
        doc_id="D4",
        patient_id="P999",
        message="EMERGENCY patient unconscious",
        security_mode="NORMAL"
    )
    
    # Mock no TREATS relationship
    mock_auth_results = [{
        "authorized": False,
        "confidence_score": 0,
        "audit_trail": []
    }]
    
    # Mock ER role exists
    mock_er_results = [{
        "has_er_role": True
    }]
    
    with patch.object(policy_agent.neo4j_client, 'run_query', new_callable=AsyncMock) as mock_query:
        # First call: authorization query, second call: ER role check
        mock_query.side_effect = [mock_auth_results, mock_er_results]
        
        result = await policy_agent.check(request, intent_needs_context)
        
        assert result.authorized is True
        assert result.scope == "LIMITED_ALLERGIES_MEDS"
        assert result.break_glass is True
        assert result.reason_code == "break_glass_emergency"


@pytest.mark.asyncio
async def test_check_break_glass_unconscious(policy_agent, intent_needs_context):
    """Test break-glass activation with 'unconscious' keyword."""
    request = ChatRequest(
        user_id="user-1",
        role="doctor",
        doc_id="D4",
        patient_id="P999",
        message="Patient is unconscious, need allergy info",
        security_mode="NORMAL"
    )
    
    mock_auth_results = [{
        "authorized": False,
        "confidence_score": 0,
        "audit_trail": []
    }]
    
    mock_er_results = [{
        "has_er_role": True
    }]
    
    with patch.object(policy_agent.neo4j_client, 'run_query', new_callable=AsyncMock) as mock_query:
        mock_query.side_effect = [mock_auth_results, mock_er_results]
        
        result = await policy_agent.check(request, intent_needs_context)
        
        assert result.break_glass is True
        assert result.scope == "LIMITED_ALLERGIES_MEDS"


@pytest.mark.asyncio
async def test_check_no_break_glass_without_er_role(policy_agent, intent_needs_context):
    """Test that break-glass fails without ER role."""
    request = ChatRequest(
        user_id="user-1",
        role="doctor",
        doc_id="D1",
        patient_id="P999",
        message="EMERGENCY patient unconscious",
        security_mode="NORMAL"
    )
    
    mock_auth_results = [{
        "authorized": False,
        "confidence_score": 0,
        "audit_trail": []
    }]
    
    mock_er_results = [{
        "has_er_role": False
    }]
    
    with patch.object(policy_agent.neo4j_client, 'run_query', new_callable=AsyncMock) as mock_query:
        mock_query.side_effect = [mock_auth_results, mock_er_results]
        
        result = await policy_agent.check(request, intent_needs_context)
        
        assert result.authorized is False
        assert result.break_glass is False


@pytest.mark.asyncio
async def test_check_no_break_glass_without_keyword(policy_agent, intent_needs_context):
    """Test that break-glass doesn't activate without emergency keywords."""
    request = ChatRequest(
        user_id="user-1",
        role="doctor",
        doc_id="D4",
        patient_id="P999",
        message="What is the patient's condition?",
        security_mode="NORMAL"
    )
    
    mock_auth_results = [{
        "authorized": False,
        "confidence_score": 0,
        "audit_trail": []
    }]
    
    with patch.object(policy_agent.neo4j_client, 'run_query', new_callable=AsyncMock, return_value=mock_auth_results):
        result = await policy_agent.check(request, intent_needs_context)
        
        assert result.authorized is False
        assert result.break_glass is False


@pytest.mark.asyncio
async def test_check_neo4j_error(policy_agent, sample_request, intent_needs_context):
    """Test handling of Neo4j connection errors."""
    with patch.object(policy_agent.neo4j_client, 'run_query', new_callable=AsyncMock, side_effect=Exception("Neo4j error")):
        result = await policy_agent.check(sample_request, intent_needs_context)
        
        assert result.authorized is False
        assert result.scope == "NONE"
        assert result.reason_code == "neo4j_unavailable"
        assert result.confidence_score == 0


@pytest.mark.asyncio
async def test_check_empty_results(policy_agent, sample_request, intent_needs_context):
    """Test handling of empty Neo4j results."""
    with patch.object(policy_agent.neo4j_client, 'run_query', new_callable=AsyncMock, return_value=[]):
        result = await policy_agent.check(sample_request, intent_needs_context)
        
        assert result.authorized is False
        assert result.reason_code == "no_relationship_found"


@pytest.mark.asyncio
async def test_check_null_values_in_results(policy_agent, sample_request, intent_needs_context):
    """Test handling of null values in Neo4j results."""
    mock_results = [{
        "authorized": True,
        "confidence_score": None,
        "audit_trail": None
    }]
    
    with patch.object(policy_agent.neo4j_client, 'run_query', new_callable=AsyncMock, return_value=mock_results):
        result = await policy_agent.check(sample_request, intent_needs_context)
        
        assert result.authorized is True
        assert result.confidence_score == 0  # Handles None
        assert result.audit_trail == []  # Handles None
