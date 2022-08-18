import os
import argparse
from webexteamssdk import WebexTeamsAPI,ApiError

import logging
import sys
from logging.handlers import TimedRotatingFileHandler
FORMATTER = logging.Formatter("%(asctime)s — %(name)s — %(levelname)s — %(message)s")
LOG_FILE = "webexlogs.log"

def get_console_handler():
   console_handler = logging.StreamHandler(sys.stdout)
   console_handler.setFormatter(FORMATTER)
   return console_handler
def get_file_handler():
   file_handler = TimedRotatingFileHandler(LOG_FILE, when='midnight')
   file_handler.setFormatter(FORMATTER)
   return file_handler
def get_logger(logger_name):
   logger = logging.getLogger(logger_name)
   logger.setLevel(logging.DEBUG) # better to have too much log than not enough
   logger.addHandler(get_console_handler())
   logger.addHandler(get_file_handler())
   # with this pattern, it's rarely necessary to propagate the error up to parent
   logger.propagate = False
   return logger


def sendMessage(roomid, message):
    api = WebexTeamsAPI()
    try:
        message = api.messages.create(roomid, markdown=message)
        print(message)
        my_logger.info(message)
    except ApiError as e:
        print(e.response, e.status)
        print(e.message)
        my_logger.error((e.response, e.status, e.message))


my_logger = get_logger("sendWebexMessage")

if __name__ == '__main__':
    try:
        os.environ["WEBEX_TEAMS_ACCESS_TOKEN"]
    except KeyError:
        print("Please set the environment variable WEBEX_TEAMS_ACCESS_TOKEN\n"
              "Additional info at https://developer.webex.com/docs/getting-started")
        sys.exit(1)
    
    parser = argparse.ArgumentParser(description='Send a text message to a Webex space or person')
    parser.add_argument('--roomid', metavar='roomid', required=True,
                        help='the roomid of the group or 1:1 person space')
    parser.add_argument('--message', metavar='"message"', required=True,
                        help='message to send as raw text or markdown')
    args = parser.parse_args()
    sendMessage(args.roomid, args.message)
