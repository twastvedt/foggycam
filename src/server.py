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
import logging
import time
from threading import Thread, Event


class ServerStatus(Thread):
    function = None
    delay = 30

    def __init__(self, event, delay, function):
        Thread.__init__(self, daemon=True)
        self.stopped = event
        self.delay = delay
        self.function = function

    def run(self):
        while not self.stopped.wait(self.delay):
            self.function()


class CamHandler(BaseHTTPRequestHandler):

    to_exit = False

    log_delay = 30

    active_threads = 0

    cancel_timer = Event()

    frames_successful = 0
    frames_failed = 0

    timer = None

    cam = None

    def log_frame_info(self):
        logging.warning(
            f'In {self.log_delay} seconds, {CamHandler.frames_successful} successful frames, {CamHandler.frames_failed} failed. {CamHandler.active_threads} active thread(s).')

        CamHandler.frames_failed = 0
        CamHandler.frames_successful = 0

    def do_GET(self):

        logging.warning(f'Received GET request: {self.path}')

        url_parts = urlparse(self.path)

        if url_parts.path.endswith('config'):
            query_components = parse_qs(url_parts.query)

            self.send_response(200)

            for key, value in query_components.items():
                if key == 'fps':
                    message = f'Set framerate to {value[0]}.\n'
                    logging.warning(message)
                    self.wfile.write(str.encode(message))

                    self.cam.set_framerate(float(value[0]))

        elif url_parts.path.endswith('video'):
            if not self.timer:
                self.timer = ServerStatus(
                    self.cancel_timer, self.log_delay, lambda: self.log_frame_info())
                self.timer.start()

            CamHandler.active_threads += 1

            self.send_response(200)
            self.send_header(
                'Content-type', 'multipart/x-mixed-replace; boundary=jpgboundary')
            self.end_headers()

            camera_id = self.cam.nest_camera_array[0].get("id")

            frame_marker = time.time()

            while not CamHandler.to_exit:
                success = False

                logging.info(
                    f'\nStart frame ({CamHandler.active_threads} threads)')

                start_time = time.time()

                response = self.cam.get_image(camera_id)

                logging.info(f' Got image:  {(time.time() - start_time):.3f}')

                start_time = time.time()

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

                        logging.info(
                            f' Sent image: {(time.time() - start_time):.3f}')

                        success = True

                    except BrokenPipeError as e:
                        logging.error(f'Broken Pipe')
                        break

                    except Exception as e:
                        logging.info('Server exception', exc_info=e)

                else:
                    logging.info('Empty response')

                logging.info(f' Frame time: {time.time() - frame_marker:.3f}')
                frame_marker = time.time()

                if success:
                    CamHandler.frames_successful += 1
                else:
                    CamHandler.frames_failed += 1

            CamHandler.active_threads -= 1

            logging.warning('Ending server loop')

            if CamHandler.active_threads == 0 and self.cancel_timer:
                self.cancel_timer.set()


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""
