#!/usr/bin/env python3
import socket
import threading
import json
import time
import sys
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from queue import Queue, Empty
from urllib.parse import urlparse, parse_qs

# Configuration
TCP_HOST = '127.0.0.1'
TCP_PORT = 5050  # Mesen connects here
HTTP_PORT = 8080 # Clients (Agents/CLI) connect here

# Global State
mesen_socket = None
latest_state = {}
command_queue = Queue()
connected_event = threading.Event()
response_queues = {} # {cmd_id: Queue}

def drain_queue(q: Queue) -> None:
    try:
        while True:
            q.get_nowait()
    except Empty:
        return

def clear_pending() -> None:
    drain_queue(command_queue)
    response_queues.clear()

class MesenTCPHandler(threading.Thread):
    def __init__(self):
        super().__init__()
        self.daemon = True

    def run(self):
        global mesen_socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((TCP_HOST, TCP_PORT))
            s.listen(1)
            print(f"[TCP] Listening for Mesen2 on {TCP_HOST}:{TCP_PORT}...")
            
            while True:
                conn, addr = s.accept()
                with conn:
                    print(f"[TCP] Connected by {addr}")
                    mesen_socket = conn
                    connected_event.set()
                    
                    # Buffer for partial JSON messages
                    buffer = ""
                    
                    while True:
                        try:
                            # 1. Send pending commands
                            while not command_queue.empty():
                                cmd = command_queue.get_nowait()
                                msg = json.dumps(cmd) + "\n"
                                conn.sendall(msg.encode('utf-8'))
                                # print(f"[TCP] Sent: {msg.strip()}")

                            # 2. Read updates
                            conn.settimeout(0.01)
                            try:
                                data = conn.recv(16384) # Larger buffer
                                if not data:
                                    break
                                buffer += data.decode('utf-8')
                                
                                # Process complete lines
                                while "\n" in buffer:
                                    line, buffer = buffer.split("\n", 1)
                                    line = line.strip()
                                    if line:
                                        try:
                                            msg = json.loads(line)
                                            msg_type = msg.get("type", "state")
                                            
                                            if msg_type == "state":
                                                global latest_state
                                                latest_state = msg.get("payload", msg)
                                            elif msg_type == "response":
                                                cmd_id = msg.get("id")
                                                if cmd_id in response_queues:
                                                    response_queues[cmd_id].put(msg)
                                            else:
                                                # Legacy/Unknown fallthrough
                                                latest_state = msg

                                        except json.JSONDecodeError as e:
                                            print(f"[TCP] JSON Error: {e} in {line}")
                            except socket.timeout:
                                pass
                                
                        except BrokenPipeError:
                            print("[TCP] Connection broken")
                            break
                        except Exception as e:
                            print(f"[TCP] Error: {e}")
                            break
                    
                    print("[TCP] Disconnected")
                    mesen_socket = None
                    connected_event.clear()
                    clear_pending()

class AgentHTTPHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            try:
                with open('scripts/dashboard.html', 'rb') as f:
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(f.read())
            except FileNotFoundError:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Dashboard not found (scripts/dashboard.html missing)")
        elif self.path == '/state':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(latest_state, indent=2).encode('utf-8'))
        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            status = {"connected": connected_event.is_set()}
            self.wfile.write(json.dumps(status).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == '/command':
            params = parse_qs(parsed.query)
            wait = 'true' in params.get('wait', ['false'])
            timeout = float(params.get('timeout', [5.0])[0])

            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                cmd = json.loads(post_data)
                
                # Assign ID if missing
                if "id" not in cmd:
                    cmd["id"] = str(uuid.uuid4())
                
                cmd_id = cmd["id"]

                if not connected_event.is_set():
                    result = {
                        "status": "disconnected",
                        "id": cmd_id,
                        "error": "mesen_not_connected",
                    }
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(result).encode('utf-8'))
                    return
                
                if wait:
                    response_queues[cmd_id] = Queue()
                
                command_queue.put(cmd)
                
                result = {"status": "queued", "id": cmd_id}
                
                if wait:
                    try:
                        # Wait for response
                        resp = response_queues[cmd_id].get(timeout=timeout)
                        result = resp
                    except Empty:
                        result = {"status": "timeout", "id": cmd_id}
                    finally:
                        del response_queues[cmd_id]
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode('utf-8'))
                
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(str(e).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        return # Silence logs

def run_http():
    server = HTTPServer(('127.0.0.1', HTTP_PORT), AgentHTTPHandler)
    print(f"[HTTP] Agent API listening on http://127.0.0.1:{HTTP_PORT}")
    server.serve_forever()

if __name__ == '__main__':
    tcp_thread = MesenTCPHandler()
    tcp_thread.start()
    try:
        run_http()
    except KeyboardInterrupt:
        pass
