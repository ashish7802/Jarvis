import sys
import os
import argparse
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading

def run_web_mode():
    web_dir = os.path.join(os.path.dirname(__file__), "app", "ui", "web")
    os.chdir(web_dir)
    port = 8000
    server = HTTPServer(('127.0.0.1', port), SimpleHTTPRequestHandler)
    print(f"JARVIS Siri Web Interface running at http://127.0.0.1:{port}")
    
    # Open browser
    threading.Thread(target=lambda: webbrowser.open(f"http://127.0.0.1:{port}"), daemon=True).start()
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")

def main():
    parser = argparse.ArgumentParser(description="JARVIS Siri Voice Assistant UI")
    parser.add_argument("--web", action="store_true", help="Run as Web Interface in Browser")
    args = parser.parse_args()

    if args.web:
        run_web_mode()
    else:
        try:
            from app.ui.siri_app import run_siri_app
            print("Launching JARVIS Apple Siri Desktop Interface...")
            sys.exit(run_siri_app())
        except Exception as e:
            print(f"Desktop GUI error: {e}. Falling back to Web mode...")
            run_web_mode()

if __name__ == "__main__":
    main()
