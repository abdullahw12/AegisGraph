#!/usr/bin/env python3
"""
Simple script to start both backend and UI for AegisGraph demo.
"""
import subprocess
import time
import sys
import os

def main():
    print("🚀 Starting AegisGraph Demo...")
    print("=" * 60)
    
    # Change to AegisGraph directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Start backend
    print("\n📡 Starting FastAPI backend on port 8000...")
    backend_cmd = [
        "./venv/bin/python", "-m", "uvicorn",
        "backend.main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload"
    ]
    
    try:
        backend_process = subprocess.Popen(
            backend_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        print("✅ Backend starting (PID: {})".format(backend_process.pid))
        time.sleep(3)
        
        # Check if backend is running
        if backend_process.poll() is not None:
            print("❌ Backend failed to start!")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Failed to start backend: {e}")
        sys.exit(1)
    
    # Start Streamlit UI
    print("\n🎨 Starting Streamlit UI on port 8501...")
    ui_cmd = [
        "./venv/bin/streamlit", "run",
        "ui/streamlit_app.py",
        "--server.port", "8501",
        "--server.headless", "true"
    ]
    
    try:
        ui_process = subprocess.Popen(
            ui_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        print("✅ UI starting (PID: {})".format(ui_process.pid))
        time.sleep(3)
        
        # Check if UI is running
        if ui_process.poll() is not None:
            print("❌ UI failed to start!")
            backend_process.terminate()
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Failed to start UI: {e}")
        backend_process.terminate()
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("✅ AegisGraph is running!")
    print("=" * 60)
    print("\n📍 Access points:")
    print("   • Backend API: http://localhost:8000")
    print("   • API Docs: http://localhost:8000/docs")
    print("   • Streamlit UI: http://localhost:8501")
    print("\n💡 Press Ctrl+C to stop both services")
    print("=" * 60)
    
    try:
        # Keep running and monitor processes
        while True:
            time.sleep(1)
            
            # Check if processes are still running
            if backend_process.poll() is not None:
                print("\n❌ Backend process died!")
                ui_process.terminate()
                sys.exit(1)
                
            if ui_process.poll() is not None:
                print("\n❌ UI process died!")
                backend_process.terminate()
                sys.exit(1)
                
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down...")
        backend_process.terminate()
        ui_process.terminate()
        print("✅ Stopped successfully")
        sys.exit(0)

if __name__ == "__main__":
    main()
