"""Integration tests for task 3 - orchestrator and FastAPI."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, Mock

from backend.main import app
from backend.models.schemas import IntentDecision, PolicyDecision, SafetyDecision, ResponseDecision


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


def test_end_to_end_successful_flow(client):
    """Test complete flow from FastAPI endpoint through orchestrator to response."""
    # Mock all agents
    with patch("backend.orchestrator.IntentAgent") as mock_intent_cls, \
         patch("backend.orchestrator.GraphPolicyAgent") as mock_policy_cls, \
         patch("backend.orchestrator.SafetyAgent") as mock_safety_cls, \
         patch("backend.orchestrator.ResponseAgent") as mock_response_cls, \
         patch("backend.orchestrator.set_mode", new_callable=AsyncMock) as mock_set_mode:
        
        # Setup mocks
        mock_intent = Mock()
        mock_intent.classify.return_value = IntentDecision(
            intent="TREATMENT",
            needs_patient_context=True,
            confidence=0.9,
            reason="Treatment query"
        )
        mock_intent_cls.return_value = mock_intent
        
        mock_policy = Mock()
        mock_policy.check = AsyncMock(return_value=PolicyDecision(
            authorized=True,
            scope="FULL",
            break_glass=False,
            reason_code="treats_relationship_found",
            confidence_score=1,
            audit_trail=["Doctor", "Patient"]
        ))
        mock_policy_cls.return_value = mock_policy
        
        mock_safety = Mock()
        mock_safety.scan.return_value = SafetyDecision(
            action="ALLOW",
            risk_score=10,
            phi_exposure_risk=0.1,
            attack_types=[],
            reason="No threats detected"
        )
        mock_safety_cls.return_value = mock_safety
        
        mock_response = Mock()
        mock_response.generate.return_value = ResponseDecision(
            final_text="The patient should continue current treatment.",
            blocked=False,
            redaction_count=0,
            reason_codes=[],
            tokens_in=50,
            tokens_out=20,
            cost_usd=0.0001
        )
        mock_response_cls.return_value = mock_response
        
        # Make request
        request_data = {
            "user_id": "user1",
            "role": "doctor",
            "doc_id": "D1",
            "patient_id": "P101",
            "message": "What are the treatment options?"
        }
        
        response = client.post("/chat", json=request_data)
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["blocked"] is False
        assert data["final_text"] == "The patient should continue current treatment."
        assert data["cost_usd"] == 0.0001
        assert data["intent"] == "TREATMENT"
        assert data["authorized"] is True
        assert data["scope"] == "FULL"


def test_end_to_end_lockdown_mode(client):
    """Test that LOCKDOWN mode works through the full stack."""
    with patch("backend.orchestrator.get_mode", new_callable=AsyncMock) as mock_get_mode, \
         patch("backend.orchestrator.IntentAgent") as mock_intent_cls:
        
        mock_get_mode.return_value = "LOCKDOWN"
        
        request_data = {
            "user_id": "user1",
            "role": "doctor",
            "doc_id": "D1",
            "patient_id": "P101",
            "message": "What are the treatment options?"
        }
        
        response = client.post("/chat", json=request_data)
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["blocked"] is True
        assert "LOCKDOWN" in data["reason"]
        assert data["final_text"] == ""
        
        # Verify no agents were called
        mock_intent_cls.assert_not_called()


def test_mode_change_affects_pipeline(client):
    """Test that changing mode via API affects the pipeline."""
    with patch("backend.main.set_mode", new_callable=AsyncMock) as mock_set_mode, \
         patch("backend.main.get_mode", new_callable=AsyncMock) as mock_get_mode:
        
        # Set to STRICT_MODE
        response = client.post("/mode", json={"mode": "STRICT_MODE"})
        assert response.status_code == 200
        assert response.json()["security_mode"] == "STRICT_MODE"
        mock_set_mode.assert_called_once_with("STRICT_MODE")
        
        # Get mode
        mock_get_mode.return_value = "STRICT_MODE"
        response = client.get("/mode")
        assert response.status_code == 200
        assert response.json()["security_mode"] == "STRICT_MODE"


def test_validation_error_handling(client):
    """Test that validation errors are properly handled."""
    # Missing required fields
    request_data = {
        "user_id": "user1"
        # Missing role, doc_id, patient_id, message
    }
    
    response = client.post("/chat", json=request_data)
    assert response.status_code == 422
    assert "detail" in response.json()


def test_all_endpoints_accessible(client):
    """Test that all required endpoints are accessible."""
    # Health check
    response = client.get("/health")
    assert response.status_code == 200
    
    # Get mode (with mock)
    with patch("backend.orchestrator.get_mode", new_callable=AsyncMock) as mock_get_mode:
        mock_get_mode.return_value = "NORMAL"
        response = client.get("/mode")
        assert response.status_code == 200
    
    # Set mode (with mock)
    with patch("backend.orchestrator.set_mode", new_callable=AsyncMock):
        response = client.post("/mode", json={"mode": "NORMAL"})
        assert response.status_code == 200
    
    # Chat endpoint (with full mock)
    with patch("backend.main.run_pipeline", new_callable=AsyncMock) as mock_pipeline:
        mock_pipeline.return_value = {
            "request_id": "test",
            "blocked": False,
            "reason": "",
            "final_text": "Test",
            "security_mode": "NORMAL"
        }
        
        request_data = {
            "user_id": "user1",
            "role": "doctor",
            "doc_id": "D1",
            "patient_id": "P101",
            "message": "Test"
        }
        response = client.post("/chat", json=request_data)
        assert response.status_code == 200
