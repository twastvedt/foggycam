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

    @staticmethod
    def log_frame_info():
        message = f'In {CamHandler.log_delay} seconds, {CamHandler.frames_successful} successful frames, {CamHandler.frames_failed} failed. {CamHandler.active_threads} active thread(s).'

        if CamHandler.frames_failed > 5 or CamHandler.active_threads > 1 or CamHandler.frames_successful < 20:
            logging.warning(f'Anomaly: {message}')
        else:
            logging.info(message)

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
            if not CamHandler.timer:
                CamHandler.timer = ServerStatus(
                    CamHandler.cancel_timer, CamHandler.log_delay, lambda: CamHandler.log_frame_info())

            CamHandler.timer.start()

            CamHandler.active_threads += 1

            self.send_response(200)
            self.send_header(
                'Content-type', 'multipart/x-mixed-replace; boundary=jpgboundary')
            self.end_headers()

            frame_marker = time.time()

            if not self.cam.is_capturing:
                self.cam.capture_images()

            last_frame = None

            while not CamHandler.to_exit:
                success = False

                logging.debug(
                    f'\nStart frame ({CamHandler.active_threads} threads)')

                start_time = time.time()

                if last_frame == self.cam.current_frame:
                    self.cam.new_frame_event.wait()

                last_frame = self.cam.current_frame

                logging.debug(f' Got image:  {(time.time() - start_time):.3f}')

                start_time = time.time()

                if self.cam.image:
                    try:
                        self.wfile.write(str.encode("\r\n--jpgboundary\r\n"))
                        self.send_header('Content-type', 'image/jpeg')
                        self.send_header('Content-length', len(self.cam.image))
                        self.end_headers()

                        self.wfile.write(self.cam.image)

                        logging.debug(
                            f' Sent image: {(time.time() - start_time):.3f}')

                        success = True

                    except BrokenPipeError as e:
                        logging.error(f'Broken Pipe')
                        break

                    except ConnectionAbortedError as e:
                        logging.error(f'Connection Aborted')
                        break

                    except Exception as e:
                        logging.error('Unknown exception', exc_info=e)
                        break

                else:
                    logging.info('Empty response')

                logging.debug(f' Frame time: {time.time() - frame_marker:.3f}')
                frame_marker = time.time()

                if success:
                    CamHandler.frames_successful += 1
                else:
                    CamHandler.frames_failed += 1

            CamHandler.active_threads -= 1

            logging.warning('Ending server loop')

            if CamHandler.active_threads == 0 and CamHandler.cancel_timer:
                CamHandler.cancel_timer.set()
                logging.info('Last remaining thread: cancelling timer.')


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""
