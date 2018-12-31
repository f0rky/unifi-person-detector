#!/usr/bin/python3
"""
Unifi API Scraper 
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
import requests
import re
import configparser
import json

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


#logging.info("Camera API url: %s", url)

#Queries the API and gets the cameras
def list_cameras():
    url = ("http://%s:7080/api/2.0/camera?apiKey=%s" % (NVR_HOST, API_KEY))
    # Debug url
    # print(url)
    json_request = urllib.request.urlopen(url)
    json_data = json_request.read()
    json_object = json.loads(json_data.decode('utf-8'))
    for idx, cameras in enumerate(json_object['data']):
        logging.debug('========== Found camera: %s  ==========' %cameras['name'])
        logging.debug('MAC: %s' % cameras['mac'])
        logging.debug('UUID: %s' % cameras['uuid'])
    return
# get_camera - returns path to camera mac  Looks up the UUID
def get_camera(camera):
    url = ("http://%s:7080/api/2.0/camera?apiKey=%s" % (NVR_HOST, API_KEY))
    # Debug url
    # print(url)
    json_request = urllib.request.urlopen(url)
    json_data = json_request.read()
    json_object = json.loads(json_data.decode('utf-8'))
    for idx, cameras in enumerate(json_object['data']):
        if camera == cameras['mac']:
            camera_path = ('/mnt/videos/%s/' % cameras['uuid'])
            logging.info('========== Found camera: %s  ==========' % cameras['name'])
            logging.info('MAC: %s' % cameras['mac'])
            logging.info('UUID: %s' % cameras['uuid'])
            logging.info("Found camara path:%s" % camera_path)
            return camera_path

if __name__ == "__main__":
    list_cameras()
    print(get_camera("802AA84EF45C"))
