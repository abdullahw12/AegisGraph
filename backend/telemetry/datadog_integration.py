"""
Datadog Integration - Live metrics, logs, and dashboard creation.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import requests
from datadog import statsd, initialize

logger = logging.getLogger(__name__)


class DatadogIntegration:
    """Comprehensive Datadog integration for live monitoring."""
    
    def __init__(self):
        # Load keys dynamically to ensure .env is loaded first
        self.api_key = os.getenv("DD_API_KEY")
        self.app_key = os.getenv("DD_APP_KEY", self.api_key)  # Use API key if APP key not set
        self.site = os.getenv("DD_SITE", "datadoghq.com")
        self.base_url = f"https://api.{self.site}/api/v1"
        self.headers = {
            "DD-API-KEY": self.api_key,
            "DD-APPLICATION-KEY": self.app_key,
            "Content-Type": "application/json"
        }
        logger.info(f"DatadogIntegration initialized - API key present: {bool(self.api_key)}, APP key present: {bool(self.app_key)}")
        
        # Initialize statsd for metrics
        initialize(
            statsd_host=os.getenv("DD_AGENT_HOST", "localhost"),
            statsd_port=int(os.getenv("DD_STATSD_PORT", 8125))
        )
    
    def log_prompt(self, request_id: str, prompt: str, response: str, metadata: Dict[str, Any]):
        """
        Log LLM prompts and responses to Datadog.
        
        Args:
            request_id: Unique request identifier
            prompt: The prompt sent to LLM
            response: The LLM response
            metadata: Additional context (tokens, cost, etc.)
        """
        try:
            log_entry = {
                "ddsource": "aegisgraph",
                "ddtags": f"service:aegisgraph,env:prod,request_id:{request_id}",
                "hostname": "aegisgraph-backend",
                "message": f"LLM Interaction - Request: {request_id}",
                "prompt": prompt[:1000],  # Truncate long prompts
                "response": response[:1000],  # Truncate long responses
                "tokens_in": metadata.get("tokens_in"),
                "tokens_out": metadata.get("tokens_out"),
                "cost_usd": metadata.get("cost_usd"),
                "model": metadata.get("model", "mock"),
                "security_mode": metadata.get("security_mode"),
                "authorized": metadata.get("authorized"),
                "blocked": metadata.get("blocked"),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Send to Datadog Logs API
            response = requests.post(
                f"https://http-intake.logs.{self.site}/api/v2/logs",
                headers={
                    "DD-API-KEY": self.api_key,
                    "Content-Type": "application/json"
                },
                json=[log_entry],
                timeout=5
            )
            
            if response.status_code == 202:
                logger.info(f"Successfully sent log to Datadog for request {request_id}")
            else:
                logger.warning(f"Failed to send log to Datadog: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Error logging to Datadog: {e}")
    
    def send_metric(self, metric_name: str, value: float, tags: Optional[list] = None):
        """
        Send a metric to Datadog.
        
        Args:
            metric_name: Metric name (e.g., 'aegisgraph.requests.count')
            value: Metric value
            tags: List of tags (e.g., ['env:prod', 'service:aegisgraph'])
        """
        try:
            statsd.gauge(metric_name, value, tags=tags or [])
        except Exception as e:
            logger.error(f"Error sending metric to Datadog: {e}")
    
    def send_event(self, title: str, text: str, alert_type: str = "info", tags: Optional[list] = None):
        """
        Send an event to Datadog.
        
        Args:
            title: Event title
            text: Event description
            alert_type: 'info', 'warning', 'error', or 'success'
            tags: List of tags
        """
        try:
            event_data = {
                "title": title,
                "text": text,
                "alert_type": alert_type,
                "tags": tags or ["service:aegisgraph", "env:prod"]
            }
            
            response = requests.post(
                f"{self.base_url}/events",
                headers=self.headers,
                json=event_data,
                timeout=5
            )
            
            if response.status_code not in [200, 202]:
                logger.warning(f"Failed to send event to Datadog: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error sending event to Datadog: {e}")
    
    def create_dashboard(self, dashboard_config: Dict[str, Any]) -> Optional[str]:
        """
        Create a Datadog dashboard programmatically.
        
        Args:
            dashboard_config: Dashboard configuration dict
            
        Returns:
            Dashboard URL if successful, None otherwise
        """
        try:
            response = requests.post(
                f"{self.base_url}/dashboard",
                headers=self.headers,
                json=dashboard_config,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                dashboard_id = response.json().get("id")
                dashboard_url = f"https://app.{self.site}/dashboard/{dashboard_id}"
                logger.info(f"Created Datadog dashboard: {dashboard_url}")
                return dashboard_url
            else:
                logger.error(f"Failed to create dashboard: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating dashboard: {e}")
            return None
    
    def get_aegisgraph_dashboard_config(self) -> Dict[str, Any]:
        """
        Get the AegisGraph dashboard configuration.
        Uses log-based metrics since statsd requires a local agent.
        
        Returns:
            Dashboard configuration dict
        """
        return {
            "title": "AegisGraph - Live HIPAA LLM Firewall",
            "description": "Real-time monitoring of AegisGraph security pipeline with prompts, responses, and metrics",
            "widgets": [
                # Row 1: Log-based metrics (count of log entries)
                {
                    "definition": {
                        "title": "Total Requests (Last Hour)",
                        "title_size": "16",
                        "title_align": "left",
                        "type": "query_value",
                        "requests": [{
                            "response_format": "scalar",
                            "queries": [{
                                "data_source": "logs",
                                "name": "query1",
                                "search": {"query": "source:aegisgraph"},
                                "indexes": ["*"],
                                "compute": {"aggregation": "count"},
                                "group_by": []
                            }]
                        }],
                        "autoscale": True,
                        "precision": 0
                    },
                    "layout": {"x": 0, "y": 0, "width": 3, "height": 2}
                },
                {
                    "definition": {
                        "title": "Blocked Requests (Last Hour)",
                        "title_size": "16",
                        "title_align": "left",
                        "type": "query_value",
                        "requests": [{
                            "response_format": "scalar",
                            "queries": [{
                                "data_source": "logs",
                                "name": "query1",
                                "search": {"query": "source:aegisgraph @blocked:true"},
                                "indexes": ["*"],
                                "compute": {"aggregation": "count"},
                                "group_by": []
                            }]
                        }],
                        "autoscale": True,
                        "precision": 0,
                        "custom_unit": "blocks"
                    },
                    "layout": {"x": 3, "y": 0, "width": 3, "height": 2}
                },
                {
                    "definition": {
                        "title": "Authorized Requests (Last Hour)",
                        "title_size": "16",
                        "title_align": "left",
                        "type": "query_value",
                        "requests": [{
                            "response_format": "scalar",
                            "queries": [{
                                "data_source": "logs",
                                "name": "query1",
                                "search": {"query": "source:aegisgraph @authorized:true"},
                                "indexes": ["*"],
                                "compute": {"aggregation": "count"},
                                "group_by": []
                            }]
                        }],
                        "autoscale": True,
                        "precision": 0
                    },
                    "layout": {"x": 6, "y": 0, "width": 3, "height": 2}
                },
                {
                    "definition": {
                        "title": "Total Cost (Last Hour)",
                        "title_size": "16",
                        "title_align": "left",
                        "type": "query_value",
                        "requests": [{
                            "response_format": "scalar",
                            "queries": [{
                                "data_source": "logs",
                                "name": "query1",
                                "search": {"query": "source:aegisgraph"},
                                "indexes": ["*"],
                                "compute": {
                                    "aggregation": "sum",
                                    "metric": "@cost_usd"
                                },
                                "group_by": []
                            }]
                        }],
                        "autoscale": True,
                        "precision": 4,
                        "custom_unit": "$"
                    },
                    "layout": {"x": 9, "y": 0, "width": 3, "height": 2}
                },
                
                # Row 2: Time Series from Logs
                {
                    "definition": {
                        "title": "Requests Over Time",
                        "title_size": "16",
                        "title_align": "left",
                        "show_legend": True,
                        "legend_layout": "auto",
                        "legend_columns": ["avg", "min", "max", "value", "sum"],
                        "type": "timeseries",
                        "requests": [
                            {
                                "response_format": "timeseries",
                                "queries": [{
                                    "data_source": "logs",
                                    "name": "total",
                                    "search": {"query": "source:aegisgraph"},
                                    "indexes": ["*"],
                                    "compute": {"aggregation": "count"},
                                    "group_by": []
                                }],
                                "formulas": [{"formula": "total"}],
                                "style": {
                                    "palette": "dog_classic",
                                    "line_type": "solid",
                                    "line_width": "normal"
                                },
                                "display_type": "bars"
                            },
                            {
                                "response_format": "timeseries",
                                "queries": [{
                                    "data_source": "logs",
                                    "name": "blocked",
                                    "search": {"query": "source:aegisgraph @blocked:true"},
                                    "indexes": ["*"],
                                    "compute": {"aggregation": "count"},
                                    "group_by": []
                                }],
                                "formulas": [{"formula": "blocked"}],
                                "style": {
                                    "palette": "warm",
                                    "line_type": "solid",
                                    "line_width": "normal"
                                },
                                "display_type": "bars"
                            }
                        ]
                    },
                    "layout": {"x": 0, "y": 2, "width": 6, "height": 3}
                },
                {
                    "definition": {
                        "title": "LLM Token Usage Over Time",
                        "title_size": "16",
                        "title_align": "left",
                        "show_legend": True,
                        "legend_layout": "auto",
                        "legend_columns": ["avg", "min", "max", "value", "sum"],
                        "type": "timeseries",
                        "requests": [
                            {
                                "response_format": "timeseries",
                                "queries": [{
                                    "data_source": "logs",
                                    "name": "tokens_in",
                                    "search": {"query": "source:aegisgraph"},
                                    "indexes": ["*"],
                                    "compute": {
                                        "aggregation": "sum",
                                        "metric": "@tokens_in"
                                    },
                                    "group_by": []
                                }],
                                "formulas": [{"formula": "tokens_in"}],
                                "style": {
                                    "palette": "purple",
                                    "line_type": "solid",
                                    "line_width": "normal"
                                },
                                "display_type": "area"
                            },
                            {
                                "response_format": "timeseries",
                                "queries": [{
                                    "data_source": "logs",
                                    "name": "tokens_out",
                                    "search": {"query": "source:aegisgraph"},
                                    "indexes": ["*"],
                                    "compute": {
                                        "aggregation": "sum",
                                        "metric": "@tokens_out"
                                    },
                                    "group_by": []
                                }],
                                "formulas": [{"formula": "tokens_out"}],
                                "style": {
                                    "palette": "orange",
                                    "line_type": "solid",
                                    "line_width": "normal"
                                },
                                "display_type": "area"
                            }
                        ]
                    },
                    "layout": {"x": 6, "y": 2, "width": 6, "height": 3}
                },
                
                # Row 3: Security Metrics by Security Mode
                {
                    "definition": {
                        "title": "Requests by Security Mode",
                        "title_size": "16",
                        "title_align": "left",
                        "type": "timeseries",
                        "requests": [{
                            "response_format": "timeseries",
                            "queries": [{
                                "data_source": "logs",
                                "name": "by_mode",
                                "search": {"query": "source:aegisgraph"},
                                "indexes": ["*"],
                                "compute": {"aggregation": "count"},
                                "group_by": [{
                                    "facet": "@security_mode",
                                    "limit": 10,
                                    "sort": {"aggregation": "count", "order": "desc"}
                                }]
                            }],
                            "formulas": [{"formula": "by_mode"}],
                            "style": {
                                "palette": "dog_classic"
                            },
                            "display_type": "bars"
                        }]
                    },
                    "layout": {"x": 0, "y": 5, "width": 6, "height": 3}
                },
                {
                    "definition": {
                        "title": "Cost Over Time",
                        "title_size": "16",
                        "title_align": "left",
                        "type": "timeseries",
                        "requests": [{
                            "response_format": "timeseries",
                            "queries": [{
                                "data_source": "logs",
                                "name": "cost",
                                "search": {"query": "source:aegisgraph"},
                                "indexes": ["*"],
                                "compute": {
                                    "aggregation": "sum",
                                    "metric": "@cost_usd"
                                },
                                "group_by": []
                            }],
                            "formulas": [{"formula": "cost"}],
                            "style": {
                                "palette": "purple",
                                "line_type": "solid",
                                "line_width": "normal"
                            },
                            "display_type": "area"
                        }]
                    },
                    "layout": {"x": 6, "y": 5, "width": 6, "height": 3}
                },
                
                # Row 4: Recent Prompts (Log Stream)
                {
                    "definition": {
                        "title": "Recent LLM Prompts & Responses",
                        "title_size": "16",
                        "title_align": "left",
                        "type": "log_stream",
                        "query": "source:aegisgraph",
                        "columns": ["@timestamp", "@request_id", "@prompt", "@response", "@cost_usd", "@blocked", "@authorized"],
                        "message_display": "expanded-md",
                        "show_date_column": True,
                        "show_message_column": True,
                        "sort": {"column": "time", "order": "desc"}
                    },
                    "layout": {"x": 0, "y": 8, "width": 12, "height": 4}
                }
            ],
            "template_variables": [],
            "layout_type": "ordered",
            "notify_list": [],
            "reflow_type": "fixed"
        }


# Global instance - created lazily
_datadog_integration_instance: Optional[DatadogIntegration] = None


def get_datadog_integration() -> DatadogIntegration:
    """Get or create the global DatadogIntegration instance."""
    global _datadog_integration_instance
    if _datadog_integration_instance is None:
        _datadog_integration_instance = DatadogIntegration()
    return _datadog_integration_instance


# For backward compatibility
datadog_integration = get_datadog_integration()
