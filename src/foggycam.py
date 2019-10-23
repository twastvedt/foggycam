"""FoggyCam captures Nest camera images and generates a video."""

from urllib.request import urlopen
import pickle
import urllib
import json
from http.cookiejar import CookieJar
import os
from collections import defaultdict
import traceback
from subprocess import Popen, PIPE
import uuid
import threading
import time
from datetime import datetime
import subprocess
from subprocess import call
import shutil
from socket import gaierror, timeout
import logging


class FoggyCam(object):
    """FoggyCam client class that performs capture operations."""

    nest_user_id = ''
    nest_access_token = ''
    nest_access_token_expiration = ''
    nest_current_user = None

    nest_session_url = 'https://home.nest.com/session'
    nest_user_url = 'https://home.nest.com/api/0.1/user/#USERID#/app_launch'
    nest_api_login_url = 'https://webapi.camera.home.nest.com/api/v1/login.login_nest'
    nest_image_url = 'https://nexusapi-us1.camera.home.nest.com/get_image?uuid=#CAMERAID#&width=#WIDTH#&cachebuster=#CBUSTER#'
    nest_verify_pin_url = 'https://home.nest.com/api/0.1/2fa/verify_pin'

    nest_user_request_payload = {
        "known_bucket_types": ["quartz"],
        "known_bucket_versions": []
    }

    nest_camera_array = []
    nest_camera_buffer_threshold = 50

    is_capturing = False
    cookie_jar = None
    merlin = None

    image = None

    image_thread = None

    last_frame = None
    frame_time = None
    start_time = None
    current_frame = 0
    new_frame_event = threading.Event()

    config = None

    def set_framerate(self, fps):
        self.config["frame_rate"] = fps
        self.frame_time = 1 / self.config["frame_rate"]

    def __init__(self, config):
        self.config = config._asdict()
        self.frame_time = 1 / self.config["frame_rate"]

        if self.config["upload_to_azure"]:
            from azurestorageprovider import AzureStorageProvider

        self.cookie_jar = CookieJar()
        self.merlin = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar))

    def start(self):
        # It's important to try and load the cookies first to check
        # if we can avoid logging in.
        try:
            self.unpickle_cookies()

            utc_date = datetime.utcnow()
            utc_millis_str = str(int(utc_date.timestamp())*1000)
            self.initialize_twof_session(utc_millis_str)
        except:
            logging.warning(
                "Failed to re-use the cookies. Re-initializing session...")
            self.initialize_session()

        self.login()
        self.initialize_user()

    def unpickle_cookies(self):
        """Get local cookies and load them into the cookie jar."""

        logging.info("Unpickling cookies...")
        with open("cookies.bin", 'rb') as f:
            pickled_cookies = pickle.load(f)

            for pickled_cookie in pickled_cookies:
                self.cookie_jar.set_cookie(pickled_cookie)

            cookie_data = dict((cookie.name, cookie.value)
                               for cookie in self.cookie_jar)

            self.nest_access_token = cookie_data["cztoken"]

    def pickle_cookies(self):
        """Store the cookies locally to reduce auth calls."""

        logging.info("Pickling cookies...")
        pickle.dump([c for c in self.cookie_jar], open("cookies.bin", "wb"))

    def initialize_twof_session(self, time_token):
        """Creates the first session to get the access token and cookie, with 2FA enabled."""

        logging.info("Intializing 2FA session...")

        target_url = self.nest_session_url + "?=_" + time_token
        logging.info(target_url)

        try:
            request = urllib.request.Request(target_url)
            request.add_header('Authorization', 'Basic %s' %
                               self.nest_access_token)

            response = self.merlin.open(request)
            session_data = response.read().decode('utf-8')

            session_json = json.loads(session_data)

            self.nest_access_token = session_json['access_token']
            self.nest_access_token_expiration = session_json['expires_in']
            logging.warning(
                f'Captured expiration date for token: {self.nest_access_token_expiration}')

            self.nest_user_id = session_json['userid']

            self.pickle_cookies()
        except urllib.request.HTTPError as err:
            logging.critical(err)

    def initialize_session(self):
        """Creates the first session to get the access token and cookie."""

        logging.info('Initializing session...')

        payload = {'email': self.config["username"],
                   'password': self.config["password"]}
        binary_data = json.dumps(payload).encode('utf-8')

        request = urllib.request.Request(self.nest_session_url, binary_data)
        request.add_header('Content-Type', 'application/json')

        try:
            response = self.merlin.open(request)
            session_data = response.read().decode('utf-8')
            session_json = json.loads(session_data)

            self.nest_access_token = session_json['access_token']
            self.nest_access_token_expiration = session_json['expires_in']
            self.nest_user_id = session_json['userid']

            logging.debug(
                f'Captured authentication token: {self.nest_access_token}')

            logging.warning(
                f'Captured expiration date for token: {self.nest_access_token_expiration}')

            cookie_data = dict((cookie.name, cookie.value)
                               for cookie in self.cookie_jar)
            for cookie in cookie_data:
                logging.info(cookie)

            logging.debug(
                f'[COOKIE] Captured authentication token: {cookie_data["cztoken"]}')

        except urllib.request.HTTPError as err:
            if err.code == 401:
                error_message = err.read().decode('utf-8')
                unauth_content = json.loads(error_message)

                if unauth_content["status"].lower() == "verification_pending":
                    print("Pending 2FA verification!")

                    two_factor_token = unauth_content["2fa_token"]
                    phone_truncated = unauth_content["truncated_phone_number"]

                    print(
                        "Enter PIN you just received on number ending with", phone_truncated)
                    pin = input()

                    payload = {"pin": pin, "2fa_token": two_factor_token}
                    binary_data = json.dumps(payload).encode('utf-8')

                    request = urllib.request.Request(
                        self.nest_verify_pin_url, binary_data)
                    request.add_header('Content-Type', 'application/json')

                    try:
                        response = self.merlin.open(request)
                        pin_attempt = response.read().decode('utf-8')

                        parsed_pin_attempt = json.loads(pin_attempt)
                        if parsed_pin_attempt["status"].lower() == "id_match_positive":
                            print("2FA verification successful.")

                            utc_date = datetime.utcnow()
                            utc_millis_str = str(
                                int(utc_date.timestamp())*1000)

                            print(
                                "Targetting new session with timestamp: ", utc_millis_str)

                            cookie_data = dict((cookie.name, cookie.value)
                                               for cookie in self.cookie_jar)

                            logging.debug(
                                f'[COOKIE] Captured authentication token: {cookie_data["cztoken"]}')

                            self.nest_access_token = parsed_pin_attempt['access_token']

                            self.initialize_twof_session(utc_millis_str)
                        else:
                            print("Could not verify. Exiting...")
                            exit()

                    except:
                        traceback.print_exc()

                        print("Failed 2FA checks. Exiting...")
                        exit()

        logging.info('Session initialization complete!')

    def login(self):
        """Performs user login to get the website_2 cookie."""

        logging.info('Performing user login...')

        post_data = {'access_token': self.nest_access_token}
        post_data = urllib.parse.urlencode(post_data)
        binary_data = post_data.encode('utf-8')

        logging.debug(f'Auth post data: {post_data}')

        request = urllib.request.Request(
            self.nest_api_login_url, data=binary_data)
        request.add_header('Content-Type', 'application/x-www-form-urlencoded')

        response = self.merlin.open(request)
        session_data = response.read().decode('utf-8')

        logging.debug(session_data)

    def initialize_user(self):
        """Gets the assets belonging to Nest user."""

        logging.info('Initializing current user...')

        user_url = self.nest_user_url.replace('#USERID#', self.nest_user_id)

        logging.debug(f'Requesting user data from: {user_url}')

        binary_data = json.dumps(
            self.nest_user_request_payload).encode('utf-8')

        request = urllib.request.Request(user_url, binary_data)

        request.add_header('Content-Type', 'application/json')
        request.add_header('Authorization', 'Basic %s' %
                           self.nest_access_token)

        response = self.merlin.open(request)

        response_data = response.read().decode('utf-8')

        logging.debug(response_data)

        user_object = json.loads(response_data)
        for bucket in user_object['updated_buckets']:
            bucket_id = bucket['object_key']

            if bucket_id.startswith('quartz.'):
                camera_id = bucket_id.replace('quartz.', '')
                camera_description = bucket['value']['description']

                logging.debug(f'Detected camera configuration: {bucket}')
                logging.info(f'Camera UUID: {camera_id}')
                logging.debug(camera_description)

                self.nest_camera_array.append(
                    {"id": camera_id, "name": camera_description})

    def capture_images(self):
        """Starts the multi-threaded image capture process."""

        logging.info('Capturing images...')

        self.is_capturing = True

        self.nest_camera_buffer_threshold = self.config["threshold"]

        camera_id = self.nest_camera_array[0].get("id")

        # TODO: Handle multiple cameras. Currently just uses the first.
        self.image_thread = threading.Thread(
            target=self.perform_capture, args=[camera_id])
        self.image_thread.daemon = True
        self.image_thread.start()

    def perform_capture(self, camera_id=None):
        """Get images."""

        self.current_frame = 0

        while self.is_capturing:
            self.new_frame_event.clear()

            try:
                response = self.get_image(camera_id)
                self.image = response.read()
                # TODO: loop and read response into a buffer that is read as it is written by multiple threads. This would reduce lag, not sure if that's an issue yet.
                # Would need to keep two buffers on hand (I think), so that threads can finish reading from the old one if foggycam has moved on to write to the new one.

            except timeout as e:
                continue

            except Exception as e:
                logging.warning("Capture error", exc_info=e)
                continue

            self.current_frame += 1

            self.new_frame_event.set()

    def stop(self):
        if self.image_thread:
            self.image_thread.stop()
            self.image_thread = None

            self.new_frame_event.clear()

            self.is_capturing = False

    def get_image(self, camera_id=None):
        """Generate image from cam."""

        utc_date = datetime.utcnow()
        utc_millis_str = str(int(utc_date.timestamp())*1000)

        logging.debug('Applied cache buster: ', utc_millis_str)

        image_url = self.nest_image_url.replace('#CAMERAID#', camera_id).replace(
            '#CBUSTER#', utc_millis_str).replace('#WIDTH#', str(self.config["width"]))

        request = urllib.request.Request(image_url)
        request.add_header('accept', 'image/webp,image/apng,image/*,*/*;q=0.9')
        request.add_header('accept-encoding', 'gzip, deflate, br')
        request.add_header(
            'user-agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.181 Safari/537.36')
        request.add_header('referer', 'https://home.nest.com/')
        request.add_header('authority', 'nexusapi-us1.camera.home.nest.com')

        try:
            response = self.merlin.open(request, timeout=3)

            if self.last_frame:
                actual_frame_time = time.time() - self.last_frame

                logging.debug(f' Since last: {actual_frame_time:.3f}')

                sleep_time = self.frame_time - actual_frame_time

                if sleep_time > 0:
                    logging.debug(f' Sleep:      {sleep_time:.3f}')
                    time.sleep(sleep_time)

            self.last_frame = time.time()

            return response

        except urllib.request.HTTPError as err:
            if err.code == 403:
                logging.error('HTTP 403 Error')

                self.initialize_session()
                self.login()
                self.initialize_user()
            else:
                logging.info(err)

            self.last_frame = None

        except gaierror as err:
            logging.error('gaierror', exc_info=err)

            self.initialize_session()
            self.login()
            self.initialize_user()

            self.last_frame = None

        except Exception as err:
            logging.info(err, exc_info=True)

            self.last_frame = None
