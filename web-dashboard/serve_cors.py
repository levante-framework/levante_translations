#!/usr/bin/env python3
"""
CORS Proxy Server for PlayHT API
This server acts as a proxy to handle CORS issues with PlayHT API calls from the browser
"""
import http.server
import socketserver
import urllib.request
import urllib.parse
import json
import os
from urllib.error import HTTPError

class CORSProxyHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory='public', **kwargs)
    
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, PUT, DELETE')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-USER-ID, AUTHORIZATION')
        super().end_headers()
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()
    
    def do_POST(self):
        # Handle PlayHT API proxy requests
        if self.path.startswith('/proxy/playht'):
            self.handle_playht_proxy()
        else:
            super().do_POST()
    
    def handle_playht_proxy(self):
        try:
            # Read the request body
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            # Get headers from the original request
            auth_header = self.headers.get('AUTHORIZATION')
            user_id_header = self.headers.get('X-USER-ID')
            
            if not auth_header or not user_id_header:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'Missing PlayHT credentials')
                return
            
            # Create the request to PlayHT API
            playht_url = 'https://api.play.ht/api/v2/tts/stream'
            req = urllib.request.Request(
                playht_url,
                data=post_data,
                headers={
                    'Content-Type': 'application/json',
                    'AUTHORIZATION': auth_header,
                    'X-USER-ID': user_id_header,
                    'Accept': 'audio/mpeg'
                }
            )
            
            # Make the request to PlayHT
            with urllib.request.urlopen(req) as response:
                # Send the response back to the client
                self.send_response(response.getcode())
                
                # Copy relevant headers
                for header, value in response.headers.items():
                    if header.lower() not in ['connection', 'transfer-encoding']:
                        self.send_header(header, value)
                
                self.end_headers()
                
                # Copy the response body
                self.wfile.write(response.read())
                
        except HTTPError as e:
            print(f"PlayHT API error: {e.code} - {e.reason}")
            self.send_response(e.code)
            self.end_headers()
            error_response = e.read() if hasattr(e, 'read') else str(e).encode()
            self.wfile.write(error_response)
        except Exception as e:
            print(f"Proxy error: {e}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Proxy error: {str(e)}".encode())

if __name__ == "__main__":
    PORT = 8001
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    with socketserver.TCPServer(("", PORT), CORSProxyHandler) as httpd:
        print(f"CORS Proxy server running at http://localhost:{PORT}")
        print("This will handle PlayHT API calls and serve the dashboard")
        print("Press Ctrl+C to stop the server")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped") 