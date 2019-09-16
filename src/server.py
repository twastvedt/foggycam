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
        self.send_response(200)
        self.send_header(
            'Content-type', 'multipart/x-mixed-replace; boundary=jpgboundary')
        self.end_headers()
        global to_exit

        print('do_GET')

        camera_id = self.cam.nest_camera_array[0].get("id")

        while not to_exit:
            response = self.cam.get_image(camera_id)

            if response:
                try:
                    self.wfile.write(str.encode("\r\n--jpgboundary\r\n"))
                    self.send_header('Content-type', 'image/jpeg')
                    self.send_header('Content-length', response.length)
                    self.end_headers()

                    self.wfile.write(response.read())

                except Exception as e:
                    print(f'ERROR: {e}')

            else:
                print('Empty response')


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""
