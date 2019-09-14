#!/usr/bin/python3
"""
    Author: Igor Maculan - n3wtron@gmail.com
    A Simple mjpg stream http server
"""
import time
import signal
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn


def quit(sig, frame):
    print("Exiting server...")
    global to_exit
    to_exit = True


signal.signal(signal.SIGINT, quit)


class CamHandler(BaseHTTPRequestHandler):

    cam = None

    def do_GET(self):
        self.send_response(200)
        self.send_header(
            'Content-type', 'multipart/x-mixed-replace; boundary=jpgboundary')
        self.end_headers()
        global to_exit

        while not to_exit:
            jpg = cam.get_image(self.cam.nest_camera_array[0])

            jpg_bytes = jpg.tobytes()

            self.wfile.write(str.encode("\r\n--jpgboundary\r\n"))
            self.send_header('Content-type', 'image/jpeg')
            self.send_header('Content-length', len(jpg_bytes))
            self.end_headers()

            jpg.save(self.wfile, 'JPEG')


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""
