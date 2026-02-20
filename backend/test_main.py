"""Unit tests for the FastAPI main application."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from backend.main import app
from backend.models.schemas import ChatRequest


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


def test_health_check(client):
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "aegisgraph"
    assert data["version"] == "1.0.0"


def test_get_mode_endpoint(client):
    """Test getting the current security mode."""
    with patch("backend.main.get_mode", new_callable=AsyncMock) as mock_get_mode:
        mock_get_mode.return_value = "NORMAL"
        
        response = client.get("/mode")
        assert response.status_code == 200
        data = response.json()
        assert data["security_mode"] == "NORMAL"


def test_set_mode_endpoint_valid(client):
    """Test setting security mode with valid values."""
    with patch("backend.main.set_mode", new_callable=AsyncMock) as mock_set_mode:
        # Test NORMAL
        response = client.post("/mode", json={"mode": "NORMAL"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["security_mode"] == "NORMAL"
        mock_set_mode.assert_called_once_with("NORMAL")
        
        # Test STRICT_MODE
        mock_set_mode.reset_mock()
        response = client.post("/mode", json={"mode": "STRICT_MODE"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["security_mode"] == "STRICT_MODE"
        mock_set_mode.assert_called_once_with("STRICT_MODE")
        
        # Test LOCKDOWN
        mock_set_mode.reset_mock()
        response = client.post("/mode", json={"mode": "LOCKDOWN"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["security_mode"] == "LOCKDOWN"
        mock_set_mode.assert_called_once_with("LOCKDOWN")


def test_set_mode_endpoint_invalid(client):
    """Test setting security mode with invalid value."""
    response = client.post("/mode", json={"mode": "INVALID"})
    assert response.status_code == 400
    assert "Invalid mode" in response.json()["detail"]


def test_set_mode_endpoint_case_insensitive(client):
    """Test that mode setting is case-insensitive."""
    with patch("backend.main.set_mode", new_callable=AsyncMock) as mock_set_mode:
        response = client.post("/mode", json={"mode": "normal"})
        assert response.status_code == 200
        mock_set_mode.assert_called_once_with("NORMAL")


def test_chat_endpoint_success(client):
    """Test the chat endpoint with a successful request."""
    mock_result = {
        "request_id": "test-123",
        "blocked": False,
        "reason": "",
        "final_text": "The patient should continue current treatment.",
        "security_mode": "NORMAL",
        "tokens_in": 50,
        "tokens_out": 20,
        "cost_usd": 0.0001
    }
    
    with patch("backend.main.run_pipeline", new_callable=AsyncMock) as mock_pipeline:
        mock_pipeline.return_value = mock_result
        
        request_data = {
            "user_id": "user1",
            "role": "doctor",
            "doc_id": "D1",
            "patient_id": "P101",
            "message": "What are the treatment options?"
        }
        
        response = client.post("/chat", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["blocked"] is False
        assert data["final_text"] == "The patient should continue current treatment."
        assert data["cost_usd"] == 0.0001


def test_chat_endpoint_blocked(client):
    """Test the chat endpoint with a blocked request."""
    mock_result = {
        "request_id": "test-456",
        "blocked": True,
        "reason": "Authorization denied: no_treats_relationship",
        "final_text": "",
        "security_mode": "NORMAL"
    }
    
    with patch("backend.main.run_pipeline", new_callable=AsyncMock) as mock_pipeline:
        mock_pipeline.return_value = mock_result
        
        request_data = {
            "user_id": "user1",
            "role": "doctor",
            "doc_id": "D1",
            "patient_id": "P999",
            "message": "Show me patient records"
        }
        
        response = client.post("/chat", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["blocked"] is True
        assert "denied" in data["reason"].lower()
        assert data["final_text"] == ""


def test_chat_endpoint_lockdown(client):
    """Test the chat endpoint in LOCKDOWN mode."""
    mock_result = {
        "request_id": "test-789",
        "blocked": True,
        "reason": "System is in LOCKDOWN mode",
        "final_text": "",
        "security_mode": "LOCKDOWN"
    }
    
    with patch("backend.main.run_pipeline", new_callable=AsyncMock) as mock_pipeline:
        mock_pipeline.return_value = mock_result
        
        request_data = {
            "user_id": "user1",
            "role": "doctor",
            "doc_id": "D1",
            "patient_id": "P101",
            "message": "What are the treatment options?",
            "security_mode": "LOCKDOWN"
        }
        
        response = client.post("/chat", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["blocked"] is True
        assert "LOCKDOWN" in data["reason"]


def test_chat_endpoint_validation_error(client):
    """Test the chat endpoint with missing required fields."""
    # Missing required fields
    request_data = {
        "user_id": "user1",
        "role": "doctor"
        # Missing doc_id, patient_id, message
    }
    
    response = client.post("/chat", json=request_data)
    assert response.status_code == 422  # Validation error


def test_chat_endpoint_auto_generates_request_id(client):
    """Test that request_id is auto-generated if not provided."""
    mock_result = {
        "request_id": "auto-generated-id",
        "blocked": False,
        "reason": "",
        "final_text": "Response text",
        "security_mode": "NORMAL"
    }
    
    with patch("backend.main.run_pipeline", new_callable=AsyncMock) as mock_pipeline:
        mock_pipeline.return_value = mock_result
        
        request_data = {
            "user_id": "user1",
            "role": "doctor",
            "doc_id": "D1",
            "patient_id": "P101",
            "message": "Test message"
            # No request_id provided
        }
        
        response = client.post("/chat", json=request_data)
        assert response.status_code == 200
        
        # Verify that run_pipeline was called with a ChatRequest that has a request_id
        call_args = mock_pipeline.call_args[0][0]
        assert call_args.request_id is not None
        assert len(call_args.request_id) > 0
