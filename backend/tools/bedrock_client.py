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
        """Invoke a Bedrock model using the Converse API."""
        try:
            # Use the Converse API which works with inference profiles
            response = self._client.converse(
                modelId=model_id,
                messages=[
                    {
                        "role": "user",
                        "content": [{"text": prompt}]
                    }
                ],
                inferenceConfig={
                    "maxTokens": 2000,
                    "temperature": 0.0
                }
            )
            
            # Extract text from response
            output = response.get("output", {})
            message = output.get("message", {})
            content = message.get("content", [])
            
            if content and len(content) > 0:
                return content[0].get("text", "")
            
            return ""
            
        except ClientError as exc:
            raise BedrockError(f"Bedrock invocation failed: {exc}") from exc
