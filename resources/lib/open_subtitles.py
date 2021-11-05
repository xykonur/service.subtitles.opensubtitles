# -*- coding: utf-8 -*-

import os
import json
import sys

from requests import Session, ConnectionError, HTTPError, ReadTimeout, Timeout

from resources.lib.os_subtitles_request import OpenSubtitlesSubtitlesRequest

'''local kodi module imports. replace by any other exception, cache, log provider'''
from resources.lib.exceptions import AuthenticationError, ConfigurationError, DownloadLimitExceeded, ProviderError, \
    ServiceUnavailable, TooManyRequests
from resources.lib.cache import Cache
from resources.lib.utilities import log


API_URL = "https://www.opensubtitles.com/api/v1/"
API_LOGIN = "login"
API_SUBTITLES = "subtitles"
API_DOWNLOAD = "download"

REQUEST_TIMEOUT = 30


# Replace with any other log implementation outside fo module/Kodi
def logging(msg):
    return log(__name__, msg)


class OpenSubtitlesProvider(object):

    def __init__(self, api_key, username, password):

        if not all((username, password)):
            raise ConfigurationError("Username and password must be specified")

        if not api_key:
            raise ConfigurationError("Api_key must be specified")

        self.api_key = api_key
        self.username = username
        self.password = password

        self.user_token = ""

        self.request_headers = {"Api-Key": self.api_key, "Content-Type": "application/json"}

        self.session = Session()
        self.session.headers = self.request_headers

        # Use any other cache outside of module/Kodi
        self.cache = Cache(key_prefix="os_com")

    # make login request. Sets auth token
    def login(self):

        # build login request
        login_url = API_URL + API_LOGIN
        login_body = {"username": self.username, "password": self.password}

        try:
            r = self.session.post(login_url, json=login_body, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
        except (ConnectionError, Timeout, ReadTimeout) as e:
            raise ServiceUnavailable("Unknown Error: %s: %r" % (e.response.status_code, e))
        except HTTPError as e:
            status_code = e.response.status_code
            if status_code == 401:
                raise AuthenticationError("Login failed: {}".format(e))
            elif status_code == 429:
                raise TooManyRequests()
            elif status_code == 503:
                raise ProviderError(e)
            else:
                raise ProviderError("Bad status code: {}".format(status_code))
        else:
            try:
                self.user_token = r.json()["token"]
            except ValueError:
                raise ValueError("Invalid JSON returned by provider")
            else:
                self.cache.set(key="user_token", value=self.user_token)
                return

    def search_subtitles(self, query: dict or OpenSubtitlesSubtitlesRequest):

        logging(type(query))
        logging(query)
        if type(query) is dict:
            try:
                subtitle_request = OpenSubtitlesSubtitlesRequest(**query)
            except ValueError as e:
                raise ValueError("Invalid subtitle search data provided: {}".format(e))
        elif type(query) is OpenSubtitlesSubtitlesRequest:
            subtitle_request = query
        else:
            raise ValueError("Invalid subtitle search data provided. Invalid query type")

        logging(vars(subtitle_request))
        params = subtitle_request.request_params()
        logging(params)

        if not len(params):
            raise ValueError("Invalid subtitle search data provided. Empty Object built")

        try:
            # build query request
            subtitles_url = API_URL + API_SUBTITLES
            r = self.session.get(subtitles_url, params=params, timeout=30)
            logging(r.url)
            r.raise_for_status()
        except (ConnectionError, Timeout, ReadTimeout) as e:
            raise ServiceUnavailable("Unknown Error, empty response: %s: %r" % (e.status_code, e))
        except HTTPError as e:
            status_code = e.response.status_code
            if status_code == 429:
                raise TooManyRequests()
            elif status_code == 503:
                raise ProviderError(e)
            else:
                raise ProviderError("Bad status code: {}".format(status_code))

        try:
            result = r.json()
            if "data" not in result:
                raise ValueError
        except ValueError:
            raise ProviderError("Invalid JSON returned by provider")
        else:
            logging("Query returned {} subtitles".format(len(result["data"])))

        if len(result["data"]):
            return result["data"]

        return None

    # download a single subtitle file using the file_no
    def download_subtitle(self, file_no, output_directory=None, output_filename=None, overwrite=False):

        # default saves to same folder as video file
        # cant set instance variable as a default argument, so a bit messy. Also it's late. I'm tired.
        download_directory = self.folder_path if output_directory is None else output_directory

        download_filename = os.path.splitext(self.file_name)[0] if output_filename is None else output_filename
        download_filename += "." + self.sublanguage
        download_filename += ".forced" if self.forced else ""
        download_filename += ".srt"

        # build download request
        download_url = "https://www.opensubtitles.com/api/v1/download"
        download_headers = {'api-key': self.apikey,
                            'authorization': self.login_token,
                            'content-type': CONTENT_TYPE}
        download_body = {'file_id': file_no}

        # dont download if subtitle already exists
        if os.path.exists(download_directory + os.path.sep + download_filename) and not overwrite:
            print("Subtitle file " + download_directory + os.path.sep + download_filename + " already exists")
            return None

        # only download if user has download credits remaining
        if self.user_downloads_remaining > 0:

            try:
                # this will cost a download
                download_response = requests.post(download_url, data=json.dumps(download_body),
                                                  headers=download_headers)
                download_json_response = download_response.json()

                # get the link stored on the server
                download_link = download_json_response['link']

                # download the file
                download_remote_file = requests.get(download_link)
                try:
                    open(download_directory + os.path.sep + download_filename, 'wb').write(download_remote_file.content)
                    print("Saved subtitle to " + download_directory + os.path.sep + download_filename)
                except IOError:
                    print("Failed to save subtitle to " + download_directory + os.path.sep + download_filename)


            except requests.exceptions.HTTPError as httperr:
                raise SystemExit(
                    httperr)  # need more documentation to know exactly what the API HTTP error responses are
            except requests.exceptions.RequestException as reqerr:
                raise SystemExit("Failed to login: " + reqerr)
            except ValueError as e:
                raise SystemExit("Failed to parse search_subtitle JSON response: " + e)
        else:
            print("Download limit reached. Please upgrade your account or wait for your quota to reset (~24hrs)")
            sys.exit(0)
