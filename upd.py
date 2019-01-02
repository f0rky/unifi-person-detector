#!/usr/bin/python3
"""
Unifi Person Detector
This script is used to run YOLO object detection on video files recorded by the unifi camera
"""

import argparse
import time
import subprocess
import os
import logging
import urllib.request
import shutil
import datetime
import sys
import tailer
import tailhead
import requests
import re
import configparser
import json
from unifiapi import get_camera
from unifiapi import list_cameras

config = configparser.ConfigParser()
config.read('config.ini')

# make this betterer?
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
UPD = config['DEFAULT']['UPD']
LOG_FILE = config['DEFAULT']['LOG_FILE']
API_KEY = config['DEFAULT']['API_KEY']
NVR_HOST = config['DEFAULT']['NVR_HOST']
RECORD_LOG = config['DEFAULT']['RECORD_LOG']
HASS_HOST = config['DEFAULT']['HASS_HOST']
HASS_API = config['DEFAULT']['HASS_API']
DARKNET = config['DEFAULT']['DARKNET']
VIDEO_URL = config['DEFAULT']['VIDEO_URL']

class UnifiPersonDetector():
    """
    The application.
    """
    def __init__(self):
        self.unifi_api_key = API_KEY
        self.unifi_nvr_host = NVR_HOST
        self.unifi_record_log = RECORD_LOG
        self.hass_api_pass = HASS_API
        self.hass_host = HASS_HOST
        self.video_url = VIDEO_URL
        logging.info('HomeAssistant %s' % self.hass_host)
    def run(self):
        """
        This function is used for tailing the recording log and finding
        out when a new recording have taken place.
        """
        logging.debug('ENTERING FUNCTION: run()')
        list_cameras()

        for line in tailhead.follow_path(self.unifi_record_log):
            if line is not None:
                if 'STOPPING' in line and 'motionRecording' in line:
                    split_row = line.split()
                    # Debug to output line captured from recording.log
                    #logging.debug('Capture: %s', split_row)
                    rec_time = split_row[2].split('.')[0]
                    rec_camera_id, rec_camera_name = split_row[4][6:].strip('[]').split('|')

                    logging.info('---------- Camera: %s ----------', rec_camera_name)
                    rec_id = split_row[7].split(':')[1]

                    logging.info('---------- New recording ----------')
                    logging.info('---------- Camera ID: %s Time: %s Rec ID: %s ----------', rec_camera_name, rec_time, rec_id)
                    rec_timestamp = rec_time.replace(":", "_")
                    # Download the recording.
                    rec_file = self.download_recording(rec_id)
                    if not rec_file:
                        continue

                    # Run detection on the recording.
                    self.run_detection(rec_file)

                    if self.get_detection_result():
                        self.copy_result_movie(rec_camera_name,rec_timestamp)
                        notification_image = self.get_notification_image(rec_camera_id, rec_id)
                        self.send_discord_notification(notification_image, rec_camera_name, rec_timestamp)
                    else:
                        logging.info('Person NOT FOUND in recording.')

                    # Destroy recording
                    os.remove(rec_file)

                time.sleep(1)


    def download_recording(self, recording_id):
        """
        This function is used for downloading the recording using the Unifi Video API

        Param 1: The ID of the recording to download.
        """
        logging.debug('ENTERING FUNCTION: download_recording(params)')
        logging.debug('PARAM 1: recording_id=%s', recording_id)

        recording_file_path = ("%s/%s" % (CURRENT_DIR, "recording.mp4"))
        url = ("http://%s%s%s%s%s" % (self.unifi_nvr_host, ":7080/api/2.0/recording/",
                                      recording_id, "/download/?apiKey=", self.unifi_api_key))

        logging.info("Download recording with url: %s", url)

        try:
            recf = urllib.request.urlopen(url)
            data = recf.read()
            with open(recording_file_path, "wb") as out:
                out.write(data)
        except urllib.error.HTTPError as err:
            logging.error('Error code: %s', err.code)
        except urllib.error.URLError as err:
            logging.error('Reason: %s', err.reason)

        logging.info('Downloaded the recording file!')

        if not os.path.isfile(recording_file_path):
            logging.error('Recording file does not exist! Something went wrong when downloading')
            return
        else:
            logging.info('Verified that file existed: ' + recording_file_path)
            os.chmod(recording_file_path, 0o777)
            return recording_file_path

    @staticmethod
    def run_detection(filepath):
        """
        This function is used for starting object detection on a certain video file

        Param 1: Path to the file that you want to run object detection on.
        """
        logging.debug('ENTERING FUNCTION: run_detection(params)')
        logging.debug('PARAM 1: filepath=' + filepath)

        # Run detection on filepath
        # Return true or false if person is detected
        logging.info("Running detection on " + filepath)
        with open('/opt/darknet/result.txt', "wb") as outfile:
            detection = "./darknet detector demo ./cfg/coco.data ./cfg/yolov3-tiny.cfg ./yolov3-tiny.weights %s -i 0 -thresh 0.25 -out_filename ./result.avi" % (filepath)
            logging.info("Running command: %s",detection)
            subprocess.call(detection, shell=True, stdout=outfile, cwd=r'/opt/darknet')
        return

    @staticmethod
    def get_detection_result():
        """
        This function is used to fetch the result from the object detection from a txt file.
        """
        logging.debug('ENTERING FUNCTION: get_detection_result()')
        result_file = "/opt/darknet/result.txt"
        found_person = False

        if not os.path.exists(result_file):
            logging.error(result_file + ' does not exist.')
            return False

        logging.debug('Scanning resultfile')
        with open(result_file, 'r') as result:
            for line in result:
                if 'person: ' in line:
                    person_regex = re.compile(r'person: \d{1,}%')
                    search_results = person_regex.search(line)
                    person = search_results.group()

                    logging.info('Found person on result line: %s', line.strip())
                    logging.info('%s',line.split(':')[1].strip().strip('%'))
                    if int(person.split(':')[1].strip().strip('%')) > 80:
                        found_person = True
                        break
                    else:
                        logging.info('False alarm: Percentage of found person was below 80% certainty.')

        return found_person


    @staticmethod
    def get_notification_image(recording_camera_id, recording_id):
        """
        This function is used for returning the path of the notification image.

        Param 1: The ID of the camera that recorded.
        Param 2: The ID of the recording.
        """
        logging.debug('ENTERING FUNCTION: get_notification_image(params)')
        logging.debug('PARAM 1: recording_camera_id=' + recording_camera_id)
        logging.debug('PARAM 2: recording_id=' + recording_id)

        camera_path = get_camera(recording_camera_id)
        year, month, day = time.strftime("%Y,%m,%d").split(',')

        #Look in todays image folder.
        image_path = ('%s/%s/%s/%s/meta/%s_full.jpg' % (camera_path, year, month, day, recording_id))
        #image_path = (camera_path + '/' + year + '/' + month + '/' + day + '/meta/' +
        #              recording_id + "_full.jpg")

        #Look in yesterdays image folder.
        yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
        year, month, day = yesterday.strftime("%Y,%m,%d").split(',')
        image_path_yd  = ('%s/%s/%s/%s/meta/%s_full.jpg' % (camera_path, year, month, day, recording_id))
        #image_path_yd = (camera_path + '/' + year + '/' + month + '/' +
        #                 day + '/meta/' + recording_id + "_full.jpg")

        if os.path.isfile(image_path):
            logging.info('Notification image found: ' + image_path)
            return image_path
        elif os.path.isfile(image_path_yd):
            logging.info('Notification image found: ' + image_path_yd)
            return image_path_yd
        else:
            logging.error('Notification image was not found.')
            logging.info('Paths checked: %s %s' % (image_path, image_path_yd))
            return


    @staticmethod
    def copy_result_movie(camera_name, rec_timestamp):
        """
        This function copies the result movie from darknet folder into an archive
        """
        result_movie = "/opt/darknet/result.avi"
        year, month, day = time.strftime("%Y,%m,%d").split(',')
        #timestamp = time.strftime('%H_%M_%S')
        timestamp = rec_timestamp
        dest_path = ("%s/recordings/%s/%s/%s" % (CURRENT_DIR, year, month, day))
        dest = ("%s/%s_%s.mp4" % (dest_path, timestamp, camera_name))
        recording_file_path = ("%s/%s" % (CURRENT_DIR, "recording.mp4"))
        if not os.path.exists(dest_path):
            os.makedirs(dest_path)
        try:
            shutil.copy(result_movie, dest)
            ffmpeg = "/usr/bin/ffmpeg -y -i %s -i %s -map 0:v:0 -map 1:a:0 -acodec copy %s -f null - 2> audiocopyoutput.txt" % (result_movie, recording_file_path, dest)
            logging.info("Running command: %s",ffmpeg)
            subprocess.call(ffmpeg , shell=True)

        except IOError as err:
            logging.error("Unable to copy file. %s", err)
        else:
            # if copy went good
            logging.info('Copied resultfile to ' + dest)


    def send_discord_notification(self, notification_image, camera_name, rec_timestamp):
        """
        This function is used for sending a notification about the detection.
        """
        logging.debug('ENTERING FUNCTION: send_notification()')
        # Send notification
        logging.info("Sending Notification!")
        year, month, day = time.strftime("%Y,%m,%d").split(',')
        # timestamp = time.strftime('%H_%M_%S')
        timestamp = rec_timestamp
        dest_path = ("/config/notification_images/%s/%s" % (month, day))
        dest = ("%s/%s_%s.jpg" % (dest_path, timestamp, camera_name))
        notification_url = ("https://cdn.data.net.nz/notification_images/%s/%s/%s_%s.jpg"
                % (month, day, timestamp, camera_name))
        video_url = ("%s/%s/%s/%s/%s_%s.mp4"
                % (VIDEO_URL, year, month, day, timestamp, camera_name))

        # Create path if not existing
        if not os.path.exists(dest_path):
            os.makedirs(dest_path)

        # Change permissions on notification image
        #subprocess.call(["sudo", "chmod", "755", notification_image])

        try:
            shutil.copy(notification_image, dest)
        except IOError as err:
            logging.error("Unable to copy file. %s", err)
        else:
            # if copy went good
            logging.info('Copied notification_image to ' + dest)

        logging.info('Notification url: %s', notification_url)

        data = { "message": "Person detected on camera: " + camera_name + "\nVideo URL:" + video_url,
                 "target": ["516078471147945984"],
                 "data": {
                     "images": [ dest ]
                     }
                 }

        url = ('http://%s/api/services/notify/discord' % self.hass_host)
        headers = {'x-ha-access': self.hass_api_pass,
                   'content-type': 'application/json'}
        logging.info('url: %s',url)
        logging.info('headers: %s',headers)
        logging.info('data: %s',data)
        response = requests.post(url, json=data, headers=headers)
        logging.info('Received Notify response: %s', response.text)
        print(response.text)
        return

def main():
    """
    The application entry point
    """
    upd = UnifiPersonDetector()
    upd.run()

if __name__ == '__main__':
    PARSER = argparse.ArgumentParser(
        prog='Unifi Persion Detector',
        description='Detects persons filmed by Unifi camera.')

    PARSER.add_argument(
        '-d', '--debug',
        help="Print lots of debugging statements",
        action="store_const", dest="loglevel", const=logging.DEBUG,
        default=logging.INFO,
        )

    ARGS = PARSER.parse_args()

    logging.basicConfig(
        level=ARGS.loglevel,
        format="%(asctime)s [%(levelname)-5.5s]  %(message)s",
        filename=(LOG_FILE),
        filemode='a'
    )
    main()
