# -*- coding: utf-8 -*-
#
# Based on https://github.com/srgrn/google-drive-trash-cleaner
#
# Copyright (C) 2013 Google Inc. and 2016 Yannis Assael
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Command-line application to clean the trash folder in Google Drive.
Usage:
    $ python TrashCleaner.py

You can also get help on all the command-line flags the program understands
by running:

    $ python TrashCleaner.py --help

"""

import argparse
import httplib2
import os
import sys
import time
import pprint

from apiclient import discovery
from apiclient import errors
from oauth2client import file
from oauth2client import client
from oauth2client import tools

# Parser for command-line arguments.
parser = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 parents=[tools.argparser])
parser.add_argument('-p', '--path', dest='path', help='directory containing autherization file (.TrashCleaner)',
                    default='.')


def main(argv):
    # Parse the command-line flags.
    flags = parser.parse_args(argv[1:])

    # If the credentials don't exist or are invalid run through the native client
    # flow. The Storage object will ensure that if successful the good
    # credentials will get written back to the file.
    storage = file.Storage(flags.path + '/.TrashCleaner')
    credentials = storage.get()
    if credentials is None or credentials.invalid:
        CLIENT_ID = 'SOME_CLIENT_ID.apps.googleusercontent.com'
        CLIENT_SECRET = 'SOME_SECRET'
        REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'
        OAUTH_SCOPE = ['https://www.googleapis.com/auth/drive',
                       'https://www.googleapis.com/auth/drive.appdata',
                       'https://www.googleapis.com/auth/drive.file',
                       'https://www.googleapis.com/auth/drive.metadata.readonly',
                       'https://www.googleapis.com/auth/drive.readonly',
                       ]
        flow = client.OAuth2WebServerFlow(CLIENT_ID, CLIENT_SECRET, OAUTH_SCOPE, REDIRECT_URI)
        authorize_url = flow.step1_get_authorize_url()
        print('Go to the following link in your browser:\n' + authorize_url)
        code = input('Enter verification code: ').strip()
        credentials = flow.step2_exchange(code)

    # Create an httplib2.Http object to handle our HTTP requests and authorize it
    # with our good Credentials.
    http = httplib2.Http()
    http = credentials.authorize(http)

    # Construct the service object for the interacting with the Drive API.
    service = discovery.build('drive', 'v2', http=http)

    try:
        storage.put(credentials)
        print("Connected to drive!!!")
        candidates = findTrashedFiles(service)
        # Handle the bin update delay
        while True:
            if len(candidates['items']) > 0:
                printSpace(service)
                print("Starting to remove files")
                for item in candidates['items']:
                    if 'originalFilename' not in item:
                        item['originalFilename'] = item['id']
                    print("\tFile %s, has been moved to trash on %s" % (item['originalFilename'], item['modifiedDate']))
                    removeFromTrash(service, item['id'], item['originalFilename'])
                print("\tfinished removing all files")
                printSpace(service)
            else:
                print("No files to remove")
                # 30 mins to refresh
                time.sleep(30*60)
            candidates = findTrashedFiles(service)
    except client.AccessTokenRefreshError:
        print("The credentials have been revoked or expired, please re-run"
               "the application to re-authorize")
    except keyboardinterrupt:
        print("Finished")


def findTrashedFiles(service):
    print("Getting all trashed files")
    result = service.files().list(q="trashed=true").execute()
    print("\tCompleted request")
    return result


def removeFromTrash(service, fileid, filename):
    print("\ttry to remove %s with id %s" % (filename, fileid))
    try:
        result = service.files().delete(fileId=fileid).execute()
    except errors.HttpError as e:
        if e.resp.reason == "Not Found":
            print("\t%s is already removed or doesn't exist" % (filename))
        else:
            print("ERROR:: failed to remove %s returned %s %s" % (filename, e.resp.status, e.resp.reason))


def printSpace(service):
    about = service.about().get().execute()
    print('Used quota (bytes): %s' % about['quotaBytesUsed'])
    print('(might take time to fully update) Used trash quota (bytes): %s' % about['quotaBytesUsedInTrash'])


if __name__ == '__main__':
    main(sys.argv)
