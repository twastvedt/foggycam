"""Module to start FoggyCam server."""

import json
import os
from collections import namedtuple
from foggycam import FoggyCam
from server import CamHandler, ThreadedHTTPServer
import logging
import signal
import threading


LOGLEVEL = os.environ.get('LOGLEVEL', 'WARNING').upper()
logging.basicConfig(level=LOGLEVEL)
print('LOGLEVEL: ' + LOGLEVEL)

print('Welcome to FoggyCam 1.0 - Nest video/image capture tool')

CONFIG_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', 'config.json'))

logging.info(f'Config file: {CONFIG_PATH}')

CONFIG = json.load(open(CONFIG_PATH), object_hook=lambda d: namedtuple(
    'X', d.keys())(*d.values()))

CAM = FoggyCam(CONFIG)

CAM.start()

CamHandler.cam = CAM

ip = '0.0.0.0'
port = 8080

server = ThreadedHTTPServer((ip, port), CamHandler)
server_thread = threading.Thread(target=server.serve_forever)
# Exit the server thread when the main thread terminates
server_thread.daemon = True
server_thread.start()

print("Server started at " + ip + ':' + str(port))
print('Find video at http://127.0.0.1:8080')

input("Press Enter to exit...")

CamHandler.to_exit = True
server.shutdown()
server.server_close()
