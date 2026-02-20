import ddtrace

# Patch all supported integrations (requests, boto3, etc.)
ddtrace.patch_all()

# Tag every span with the service name
ddtrace.config.service = "aegisgraph"
