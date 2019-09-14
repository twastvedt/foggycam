"""Module to start FoggyCam server."""

import json
import os
from collections import namedtuple
from foggycam import FoggyCam
from server import CamHandler, ThreadedHTTPServer

print('Welcome to FoggyCam 1.0 - Nest video/image capture tool')

CONFIG_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', 'config.json'))
print(CONFIG_PATH)

CONFIG = json.load(open(CONFIG_PATH), object_hook=lambda d: namedtuple(
    'X', d.keys())(*d.values()))

CAM = FoggyCam(CONFIG)

CAM.start()

CamHandler.cam = CAM

ip = '0.0.0.0'
port = 8080
server = ThreadedHTTPServer((ip, port), CamHandler)


def quit(sig, frame):
    print("Exiting startServer...")
    global server
    server.socket.close()
    exit(0)


print("Server started at " + ip + ':' + str(port))
print('Find video at http://127.0.0.1:8080')
server.serve_forever()