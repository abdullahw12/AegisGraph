import ddtrace

# Patch all supported integrations (requests, boto3, etc.)
ddtrace.patch_all()

# Configure the global tracer
ddtrace.tracer.configure(
    hostname="localhost",
    port=8126,
)

# Tag every span with the service name
import ddtrace.settings  # noqa: E402 — must come after patch_all

ddtrace.config.service = "aegisgraph"
