#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
streamlit run ui/streamlit_app.py --server.port 8501 --server.address localhost
