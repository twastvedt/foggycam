"""Module to start FoggyCam processing."""

import json
from foggycam import FoggyCam
from collections import namedtuple

print 'Welcome to FoggyCam 1.0 - Nest video/image capture tool'

CONFIG = json.load(open('config.json'), object_hook=lambda d: namedtuple('X', d.keys())(*d.values()))

CAM = FoggyCam(username=CONFIG.username, password=CONFIG.password)
CAM.capture_images(CONFIG)
