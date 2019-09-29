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
import sched
import time

to_exit = False


def quit(sig, frame):
    print("Exiting server...")
    global to_exit
    to_exit = True
    exit(0)


signal.signal(signal.SIGINT, quit)


class CamHandler(BaseHTTPRequestHandler):

    active_threads = 0

    frames_successful = 0
    frames_failed = 0

    scheduler = sched.scheduler(time.time, time.sleep)

    cancel_scheduler = None

    cam = None

    def log_frame_info(self):
        self.cancel_scheduler = self.scheduler.enter(
            60, 1, self.log_frame_info, (self))

        logging.warning(
            f'{self.frames_successful} successful frames, {self.frames_failed} failed.')

        self.frames_failed = 0
        self.frames_successful = 0

    def do_GET(self):

        print(f'Received GET request: {self.path}')

        url_parts = urlparse(self.path)

        if url_parts.path.endswith('config'):
            query_components = parse_qs(url_parts.query)

            self.send_response(200)

            for key, value in query_components.items():
                if key == 'fps':
                    message = f'Set framerate to {value[0]}\n'
                    print(message)
                    self.wfile.write(str.encode(message))

                    self.cam.set_framerate(float(value[0]))

        elif url_parts.path.endswith('video'):
            CamHandler.active_threads += 1

            self.send_response(200)
            self.send_header(
                'Content-type', 'multipart/x-mixed-replace; boundary=jpgboundary')
            self.end_headers()
            global to_exit

            if not self.cancel_scheduler:
                self.cancel_scheduler = self.scheduler.enter(
                    60, 1, self.log_frame_info, (self))

            camera_id = self.cam.nest_camera_array[0].get("id")

            frame_marker = time.time()

            while not to_exit:
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
                        logging.error(e)

                else:
                    logging.error('Empty response')

                logging.info(f' Frame time: {time.time() - frame_marker:.3f}')
                frame_marker = time.time()

                if success:
                    self.frames_successful += 1
                else:
                    self.frames_failed += 1

            CamHandler.active_threads -= 1

            if CamHandler.active_threads == 0 and self.cancel_scheduler:
                self.cancel_scheduler()


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""
