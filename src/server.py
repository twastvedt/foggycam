#!/usr/bin/python3
"""
    Author: Igor Maculan - n3wtron@gmail.com
    A Simple mjpg stream http server
"""
import time
import signal
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn, socket
from urllib.parse import urlparse, parse_qs

to_exit = False


def quit(sig, frame):
    print("Exiting server...")
    global to_exit
    to_exit = True
    exit(0)


signal.signal(signal.SIGINT, quit)


class CamHandler(BaseHTTPRequestHandler):

    cam = None

    def do_GET(self):

        print(f'Received GET request: {self.path}')

        url_parts = urlparse(self.path)

        if url_parts.path.endswith('config'):
            query_components = parse_qs(url_parts.query)

            self.send_response(200)

            for key, value in query_components.items():
                if key == 'fps':
                    message = f'Set framerate to {value[0]}'
                    print(message)
                    self.wfile.write(str.encode(message))

                    self.cam.set_framerate(int(value[0]))

        elif url_parts.path == '/':
            self.send_response(200)
            self.send_header(
                'Content-type', 'multipart/x-mixed-replace; boundary=jpgboundary')
            self.end_headers()
            global to_exit

            camera_id = self.cam.nest_camera_array[0].get("id")

            while not to_exit:
                response = self.cam.get_image(camera_id)

                if response:
                    try:
                        self.wfile.write(str.encode("\r\n--jpgboundary\r\n"))
                        self.send_header('Content-type', 'image/jpeg')
                        self.send_header('Content-length', response.length)
                        self.end_headers()

                        while True:
                            data = response.read(32768)

                            if data is None or len(data) == 0:
                                break
                            self.wfile.write(data)

                    except socket.error as e:
                        print(f'Closing due to socket error: {e}')
                        return

                    except Exception as e:
                        print(f'ERROR: {e}')

                else:
                    print('Empty response')


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""
