#!/usr/bin/env python3
"""
CORS Proxy Server for PlayHT and Google Translate APIs
This server acts as a proxy to handle CORS issues with API calls from the browser
Supports:
- PlayHT API for text-to-speech generation
- Google Translate API for translation validation and back-translation
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
        # Handle Google Translate API proxy requests
        elif self.path.startswith('/proxy/translate'):
            self.handle_translate_proxy()
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
    
    def handle_translate_proxy(self):
        try:
            # Read the request body
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            request_data = json.loads(post_data.decode('utf-8'))
            
            # Get API key from headers
            api_key = self.headers.get('X-API-KEY')
            if not api_key:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'Missing Google Translate API key')
                return
            
            # Extract request parameters
            text = request_data.get('text', '')
            source_lang = request_data.get('source', 'en')
            target_lang = request_data.get('target', 'es')
            operation = request_data.get('operation', 'translate')  # 'translate' or 'back_translate'
            
            if not text:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'Missing text to translate')
                return
            
            # Prepare Google Translate API request
            translate_url = f'https://translation.googleapis.com/language/translate/v2?key={api_key}'
            
            # For back-translation, we reverse source and target languages
            if operation == 'back_translate':
                source_lang, target_lang = target_lang, source_lang
            
            translate_data = {
                'q': text,
                'source': source_lang,
                'target': target_lang,
                'format': 'text'
            }
            
            # Create the request to Google Translate API
            req = urllib.request.Request(
                translate_url,
                data=json.dumps(translate_data).encode('utf-8'),
                headers={
                    'Content-Type': 'application/json',
                }
            )
            
            # Make the request to Google Translate
            with urllib.request.urlopen(req) as response:
                response_data = json.loads(response.read().decode('utf-8'))
                
                # Extract translated text
                if 'data' in response_data and 'translations' in response_data['data']:
                    translated_text = response_data['data']['translations'][0]['translatedText']
                    
                    # Prepare response
                    result = {
                        'original': text,
                        'translated': translated_text,
                        'source_lang': source_lang,
                        'target_lang': target_lang,
                        'operation': operation
                    }
                    
                    # For back-translation, add similarity calculation and proper text structure
                    if operation == 'back_translate':
                        original_english = request_data.get('original_text', '')
                        
                        # Basic similarity calculation (can be enhanced later)
                        original_words = set(original_english.lower().split())
                        back_translated_words = set(translated_text.lower().split())
                        
                        if original_words:
                            similarity = len(original_words & back_translated_words) / len(original_words)
                            result['similarity_score'] = round(similarity * 100, 1)
                        else:
                            result['similarity_score'] = 0
                        
                        # Update result structure for back-translation display
                        result.update({
                            'original_english': original_english,  # Original English text
                            'source_text': text,  # The translated text that was sent back
                            'back_translated': translated_text,  # Back-translated English
                        })
                    
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(result).encode('utf-8'))
                else:
                    raise Exception("Invalid response from Google Translate API")
                    
        except HTTPError as e:
            print(f"Google Translate API error: {e.code} - {e.reason}")
            self.send_response(e.code)
            self.end_headers()
            error_response = e.read() if hasattr(e, 'read') else str(e).encode()
            self.wfile.write(error_response)
        except Exception as e:
            print(f"Translation proxy error: {e}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Translation proxy error: {str(e)}".encode())

if __name__ == "__main__":
    PORT = 8001
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    with socketserver.TCPServer(("", PORT), CORSProxyHandler) as httpd:
        print(f"CORS Proxy server running at http://localhost:{PORT}")
        print("Available endpoints:")
        print("  - /proxy/playht     : PlayHT API for text-to-speech")
        print("  - /proxy/translate  : Google Translate API for validation")
        print("  - Static files served from public/ directory")
        print("Press Ctrl+C to stop the server")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped") 