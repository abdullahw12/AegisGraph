#!/usr/bin/env python3
"""
Script to create AegisGraph dashboard in Datadog using the API.
Uses the DD_API_KEY from .env file.
"""

import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

DD_API_KEY = os.getenv("DD_API_KEY")
DD_SITE = os.getenv("DD_SITE", "datadoghq.com")

if not DD_API_KEY:
    print("❌ Error: DD_API_KEY not found in .env file")
    exit(1)

# Dashboard configuration
dashboard_config = {
    "title": "AegisGraph - HIPAA LLM Firewall",
    "description": "Real-time monitoring of AegisGraph security pipeline with agent health, risk metrics, and cost tracking",
    "widgets": [
        {
            "id": 1,
            "definition": {
                "title": "Access Legitimacy (Authorization Rate)",
                "title_size": "16",
                "title_align": "left",
                "type": "timeseries",
                "requests": [
                    {
                        "q": "avg:aegisgraph.eval.access_legitimacy{*}",
                        "display_type": "line",
                        "style": {
                            "palette": "dog_classic",
                            "line_type": "solid",
                            "line_width": "normal"
                        }
                    }
                ],
                "yaxis": {
                    "min": "0",
                    "max": "1"
                }
            },
            "layout": {
                "x": 0,
                "y": 0,
                "width": 4,
                "height": 3
            }
        },
        {
            "id": 2,
            "definition": {
                "title": "PHI Exposure Risk",
                "title_size": "16",
                "title_align": "left",
                "type": "timeseries",
                "requests": [
                    {
                        "q": "avg:aegisgraph.eval.phi_risk{*}",
                        "display_type": "line",
                        "style": {
                            "palette": "warm",
                            "line_type": "solid",
                            "line_width": "normal"
                        }
                    }
                ],
                "yaxis": {
                    "min": "0",
                    "max": "1"
                }
            },
            "layout": {
                "x": 4,
                "y": 0,
                "width": 4,
                "height": 3
            }
        },
        {
            "id": 3,
            "definition": {
                "title": "Authorization Denials",
                "title_size": "16",
                "title_align": "left",
                "type": "timeseries",
                "requests": [
                    {
                        "q": "sum:aegisgraph.security.auth_denies{*}.as_count()",
                        "display_type": "bars",
                        "style": {
                            "palette": "red",
                            "line_type": "solid",
                            "line_width": "normal"
                        }
                    }
                ]
            },
            "layout": {
                "x": 8,
                "y": 0,
                "width": 4,
                "height": 3
            }
        },
        {
            "id": 4,
            "definition": {
                "title": "LLM Cost (USD)",
                "title_size": "16",
                "title_align": "left",
                "type": "timeseries",
                "requests": [
                    {
                        "q": "sum:aegisgraph.eval.cost_usd{*}.as_count()",
                        "display_type": "area",
                        "style": {
                            "palette": "purple",
                            "line_type": "solid",
                            "line_width": "normal"
                        }
                    }
                ]
            },
            "layout": {
                "x": 0,
                "y": 3,
                "width": 6,
                "height": 3
            }
        },
        {
            "id": 5,
            "definition": {
                "title": "Agent Pipeline Traces",
                "title_size": "16",
                "title_align": "left",
                "type": "timeseries",
                "requests": [
                    {
                        "q": "sum:trace.intent.classify.hits{service:aegisgraph}.as_count()",
                        "display_type": "bars",
                        "style": {
                            "palette": "dog_classic"
                        }
                    },
                    {
                        "q": "sum:trace.policy.neo4j_check.hits{service:aegisgraph}.as_count()",
                        "display_type": "bars"
                    },
                    {
                        "q": "sum:trace.safety.scan.hits{service:aegisgraph}.as_count()",
                        "display_type": "bars"
                    },
                    {
                        "q": "sum:trace.llm.generate.hits{service:aegisgraph}.as_count()",
                        "display_type": "bars"
                    }
                ]
            },
            "layout": {
                "x": 6,
                "y": 3,
                "width": 6,
                "height": 3
            }
        },
        {
            "id": 6,
            "definition": {
                "title": "Total Requests",
                "title_size": "16",
                "title_align": "left",
                "type": "query_value",
                "requests": [
                    {
                        "q": "sum:trace.intent.classify.hits{service:aegisgraph}.as_count()",
                        "aggregator": "sum"
                    }
                ],
                "autoscale": True,
                "precision": 0
            },
            "layout": {
                "x": 0,
                "y": 6,
                "width": 3,
                "height": 2
            }
        },
        {
            "id": 7,
            "definition": {
                "title": "Blocked Requests",
                "title_size": "16",
                "title_align": "left",
                "type": "query_value",
                "requests": [
                    {
                        "q": "sum:aegisgraph.security.auth_denies{*}.as_count()",
                        "aggregator": "sum"
                    }
                ],
                "autoscale": True,
                "precision": 0,
                "custom_unit": "blocks"
            },
            "layout": {
                "x": 3,
                "y": 6,
                "width": 3,
                "height": 2
            }
        },
        {
            "id": 8,
            "definition": {
                "title": "Average Response Time",
                "title_size": "16",
                "title_align": "left",
                "type": "query_value",
                "requests": [
                    {
                        "q": "avg:trace.llm.generate.duration{service:aegisgraph}",
                        "aggregator": "avg"
                    }
                ],
                "autoscale": True,
                "precision": 2
            },
            "layout": {
                "x": 6,
                "y": 6,
                "width": 3,
                "height": 2
            }
        },
        {
            "id": 9,
            "definition": {
                "title": "Current Security Mode",
                "title_size": "16",
                "title_align": "left",
                "type": "query_value",
                "requests": [
                    {
                        "q": "avg:aegisgraph.security.auth_denies{*}",
                        "aggregator": "last"
                    }
                ],
                "autoscale": True,
                "precision": 0
            },
            "layout": {
                "x": 9,
                "y": 6,
                "width": 3,
                "height": 2
            }
        }
    ],
    "template_variables": [],
    "layout_type": "ordered",
    "is_read_only": False,
    "notify_list": [],
    "reflow_type": "fixed"
}

def create_dashboard():
    """Create the dashboard in Datadog."""
    url = f"https://api.{DD_SITE}/api/v1/dashboard"
    
    headers = {
        "Content-Type": "application/json",
        "DD-API-KEY": DD_API_KEY
    }
    
    print("🚀 Creating AegisGraph dashboard in Datadog...")
    print(f"   API endpoint: {url}")
    
    response = requests.post(url, headers=headers, json=dashboard_config)
    
    if response.status_code == 200:
        data = response.json()
        dashboard_id = data.get("id")
        dashboard_url = f"https://app.{DD_SITE}/dashboard/{dashboard_id}"
        
        print("\n✅ Dashboard created successfully!")
        print(f"\n📊 Dashboard URL: {dashboard_url}")
        print(f"\n💡 Next steps:")
        print(f"   1. Open the dashboard: {dashboard_url}")
        print(f"   2. Update your .env file:")
        print(f"      DD_DASHBOARD_URL={dashboard_url}")
        print(f"   3. Restart the backend to see it in the UI")
        
        # Update .env file automatically
        try:
            with open(env_path, "r") as f:
                env_content = f.read()
            
            # Replace or add DD_DASHBOARD_URL
            if "DD_DASHBOARD_URL=" in env_content:
                lines = env_content.split("\n")
                for i, line in enumerate(lines):
                    if line.startswith("DD_DASHBOARD_URL="):
                        lines[i] = f"DD_DASHBOARD_URL={dashboard_url}"
                env_content = "\n".join(lines)
            else:
                env_content += f"\nDD_DASHBOARD_URL={dashboard_url}\n"
            
            with open(env_path, "w") as f:
                f.write(env_content)
            
            print(f"\n✅ Updated .env file with dashboard URL")
        except Exception as e:
            print(f"\n⚠️  Could not update .env file: {e}")
            print(f"   Please manually add: DD_DASHBOARD_URL={dashboard_url}")
        
        return dashboard_url
    else:
        print(f"\n❌ Failed to create dashboard")
        print(f"   Status code: {response.status_code}")
        print(f"   Response: {response.text}")
        return None

if __name__ == "__main__":
    create_dashboard()
