import json
import os

import boto3
from botocore.exceptions import ClientError


class BedrockError(Exception):
    """Raised when the Bedrock API call fails."""


class BedrockClient:
    def __init__(self, region_name: str = "us-west-2"):
        # Support session tokens for temporary credentials
        session_token = os.environ.get("AWS_SESSION_TOKEN")
        if session_token:
            self._client = boto3.client(
                "bedrock-runtime",
                region_name=region_name,
                aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
                aws_session_token=session_token,
            )
        else:
            self._client = boto3.client("bedrock-runtime", region_name=region_name)

    def invoke(self, model_id: str, prompt: str) -> str:
        """Invoke a Bedrock model and return the response text."""
        # Different models have different request/response formats
        if "titan" in model_id.lower():
            body = json.dumps(
                {
                    "inputText": prompt,
                    "textGenerationConfig": {
                        "maxTokenCount": 1024,
                        "temperature": 0.0,
                    },
                }
            )
        elif "claude" in model_id.lower():
            body = json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": prompt}],
                }
            )
        else:
            # Generic format
            body = json.dumps({"prompt": prompt, "max_tokens": 1024})

        try:
            response = self._client.invoke_model(
                modelId=model_id,
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            result = json.loads(response["body"].read())
            
            # Parse response based on model type
            if "titan" in model_id.lower():
                return result.get("results", [{}])[0].get("outputText", "")
            elif "claude" in model_id.lower():
                return result.get("content", [{}])[0].get("text", "")
            else:
                return str(result)
        except ClientError as exc:
            raise BedrockError(f"Bedrock invocation failed: {exc}") from exc
