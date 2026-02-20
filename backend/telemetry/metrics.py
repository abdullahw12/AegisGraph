import os

from datadog import initialize, statsd

# Initialize the Datadog statsd client once at import time.
# DD_API_KEY is read from the environment; statsd talks to the local agent.
initialize(
    api_key=os.environ.get("DD_API_KEY", ""),
    statsd_host=os.environ.get("DD_AGENT_HOST", "localhost"),
    statsd_port=int(os.environ.get("DD_STATSD_PORT", 8125)),
)


def emit_access_legitimacy(value: float) -> None:
    """Gauge: 1.0 for authorized requests, 0.0 for denied."""
    statsd.gauge("aegisgraph.eval.access_legitimacy", value)


def emit_phi_risk(value: float) -> None:
    """Gauge: phi_exposure_risk from SafetyDecision."""
    statsd.gauge("aegisgraph.eval.phi_risk", value)


def emit_cost(value: float) -> None:
    """Counter: cost_usd from ResponseDecision."""
    statsd.increment("aegisgraph.eval.cost_usd", value)


def emit_auth_deny() -> None:
    """Counter: incremented each time GraphPolicyAgent returns authorized=False."""
    statsd.increment("aegisgraph.security.auth_denies")
