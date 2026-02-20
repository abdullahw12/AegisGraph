#!/usr/bin/env python3
"""
Connectivity test script for AegisGraph Task 1 components.
Tests: Neo4j, AWS Bedrock, Datadog, and core schemas.
"""
import asyncio
import os
import sys

import pytest
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def test_schemas():
    """Test that all Pydantic schemas work correctly."""
    print("\n=== Testing Schemas ===")
    from backend.models.schemas import (
        ChatRequest,
        IntentDecision,
        PolicyDecision,
        ResponseDecision,
        SafetyDecision,
    )

    # Test ChatRequest with auto-generated request_id
    req = ChatRequest(
        user_id="U1",
        role="doctor",
        doc_id="D1",
        patient_id="P101",
        message="Test message",
    )
    assert req.request_id is not None
    print(f"✓ ChatRequest auto-generates request_id: {req.request_id}")

    # Test security_mode validation
    try:
        ChatRequest(
            user_id="U1",
            role="doctor",
            doc_id="D1",
            patient_id="P101",
            message="Test",
            security_mode="INVALID",
        )
        print("✗ security_mode validation failed — should reject INVALID")
        return False
    except ValueError:
        print("✓ security_mode validation works")

    # Test confidence clamping
    intent = IntentDecision(
        intent="TREATMENT", needs_patient_context=True, confidence=1.5, reason="test"
    )
    assert intent.confidence == 1.0
    print(f"✓ IntentDecision clamps confidence: 1.5 → {intent.confidence}")

    # Test risk_score clamping
    safety = SafetyDecision(
        action="ALLOW", risk_score=150, phi_exposure_risk=0.5, reason="test"
    )
    assert safety.risk_score == 100
    print(f"✓ SafetyDecision clamps risk_score: 150 → {safety.risk_score}")

    # Test phi_exposure_risk clamping
    safety2 = SafetyDecision(
        action="BLOCK", risk_score=80, phi_exposure_risk=-0.2, reason="test"
    )
    assert safety2.phi_exposure_risk == 0.0
    print(f"✓ SafetyDecision clamps phi_exposure_risk: -0.2 → {safety2.phi_exposure_risk}")

    print("✓ All schema tests passed\n")
    return True


@pytest.mark.asyncio
async def test_neo4j():
    """Test Neo4j connectivity."""
    print("=== Testing Neo4j Connectivity ===")
    from backend.tools.neo4j_client import Neo4jClient

    try:
        client = Neo4jClient()
        result = await client.run_query("RETURN 1 AS test", {})
        assert result[0]["test"] == 1
        print(f"✓ Neo4j connection successful: {os.environ['NEO4J_URI']}")
        await client.close()
        return True
    except Exception as exc:
        print(f"✗ Neo4j connection failed: {exc}")
        return False


def test_bedrock():
    """Test AWS Bedrock connectivity."""
    print("\n=== Testing AWS Bedrock Connectivity ===")
    from backend.tools.bedrock_client import BedrockClient, BedrockError

    try:
        client = BedrockClient()
        # Try Claude 3.5 Haiku (fast and cost-effective)
        response = client.invoke(
            "anthropic.claude-3-5-haiku-20241022-v1:0", "Say hello in one word."
        )
        print(f"✓ Bedrock connection successful (Claude 3.5 Haiku)")
        print(f"  Response: {response[:100]}...")
        return True
    except BedrockError as exc:
        print(f"✗ Bedrock connection failed: {exc}")
        print("  Note: Ensure AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are set")
        return False
    except Exception as exc:
        print(f"✗ Unexpected error: {exc}")
        return False


def test_datadog_mcp_tool():
    """Test DatadogMCPTool logic."""
    print("\n=== Testing DatadogMCPTool ===")
    from backend.tools.datadog_mcp_tool import DatadogMCPTool

    tool = DatadogMCPTool(window_seconds=60, threshold=3, cooldown_seconds=600)

    # Record 2 events — should not escalate
    tool.record_auth_deny()
    tool.record_auth_deny()
    assert not tool.should_escalate()
    print("✓ 2 events do not trigger escalation")

    # Record 3rd event — should escalate
    tool.record_auth_deny()
    assert tool.should_escalate()
    print("✓ 3 events trigger escalation")

    # Immediate re-check should not escalate (cooldown)
    assert not tool.should_escalate()
    print("✓ Cooldown prevents immediate re-escalation")

    # Reset and verify
    tool.reset_window()
    assert not tool.should_escalate()
    print("✓ reset_window() clears state\n")
    return True


def test_datadog_metrics():
    """Test Datadog metrics emission (statsd)."""
    print("=== Testing Datadog Metrics ===")
    try:
        from backend.telemetry import metrics

        # These will attempt to send to localhost:8125 (statsd)
        # If no agent is running, they'll fail silently
        metrics.emit_access_legitimacy(1.0)
        metrics.emit_phi_risk(0.3)
        metrics.emit_cost(0.05)
        metrics.emit_auth_deny()
        print("✓ Datadog metrics emitted (check if statsd agent is running)")
        print("  Note: Metrics sent to localhost:8125 — may fail silently if no agent")
        return True
    except Exception as exc:
        print(f"✗ Datadog metrics failed: {exc}")
        return False


def test_minimax_client():
    """Test MiniMaxClient graceful degradation."""
    print("\n=== Testing MiniMaxClient ===")
    from backend.tools.minimax_client import MiniMaxClient

    # Without API key — should no-op
    client = MiniMaxClient(api_key=None)
    client.speak_alert("Test alert")
    print("✓ MiniMaxClient no-ops gracefully without API key\n")
    return True


async def main():
    print("AegisGraph Task 1 Connectivity Test")
    print("=" * 50)

    results = []

    # Test schemas (synchronous)
    results.append(("Schemas", test_schemas()))

    # Test Neo4j (async)
    results.append(("Neo4j", await test_neo4j()))

    # Test Bedrock (synchronous)
    results.append(("Bedrock", test_bedrock()))

    # Test DatadogMCPTool (synchronous)
    results.append(("DatadogMCPTool", test_datadog_mcp_tool()))

    # Test Datadog metrics (synchronous)
    results.append(("Datadog Metrics", test_datadog_metrics()))

    # Test MiniMaxClient (synchronous)
    results.append(("MiniMaxClient", test_minimax_client()))

    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")

    all_passed = all(passed for _, passed in results)
    if all_passed:
        print("\n✓ All connectivity tests passed!")
        sys.exit(0)
    else:
        print("\n✗ Some tests failed — check credentials and connectivity")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
