# -*- coding: utf-8 -*-

import os
import shutil
import sys
from urllib.parse import unquote

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
import uuid

from resources.lib.file_operations import hash_file
from resources.lib.utilities import log, normalize_string

__addon__ = xbmcaddon.Addon()


def get_file_path():
    return xbmc.Player().getPlayingFile()


def get_media_data():
    item = {"year": xbmc.getInfoLabel("VideoPlayer.Year"),
            "season_number": str(xbmc.getInfoLabel("VideoPlayer.Season")),
            "episode_number": str(xbmc.getInfoLabel("VideoPlayer.Episode")),
            "tvshow": normalize_string(xbmc.getInfoLabel("VideoPlayer.TVshowtitle")),
            "query": normalize_string(xbmc.getInfoLabel("VideoPlayer.OriginalTitle")),
            "file_original_path": xbmc.Player().getPlayingFile()} # TODO don't need that, or have to get that from get_file_path

    if item["query"] == "":
        log(__name__, "VideoPlayer.OriginalTitle not found")
        item["query"] = normalize_string(xbmc.getInfoLabel("VideoPlayer.Title"))  # no original title, get just Title

    if item["episode_number"].lower().find("s") > -1:  # Check if season is "Special"
        item["season_number"] = "0"  #
        item["episode_number"] = item["episode_number"][-1:]

    return item


def get_language_data(params):
    search_languages = unquote(params.get("languages")).split(",")
    preferred_language = params.get("preferredlanguage")

    # fallback_language = __addon__.getSetting("fallback_language")

    item = {
        "hearing_impaired": __addon__.getSetting("hearing_impaired"),
        "foreign_parts_only": __addon__.getSetting("foreign_parts_only"),
        "machine_translated": __addon__.getSetting("machine_translated"),
        "languages": []}

    if preferred_language and preferred_language not in search_languages and preferred_language != "Unknown":
        search_languages.append(preferred_language)

    """ should implement properly as fallback, not additional language, leave it for now
    if fallback_language and fallback_language not in search_languages:
        search_languages.append(fallback_language)"""

    for language in search_languages:
        lang = convert_language(language)

        if lang:
            item["languages"].append(lang)
        else:
            log(__name__, "Language code not found: '%s'" % language)

    return item


def convert_language(language, reverse=False):
    language_list = {
        "English": "en",
        "Portuguese (Brazil)": "pt-br",
        "Portuguese": "pt-pt",
        "Chinese (simplified)": "zh-cn",
        "Chinese (traditional)": "zh-tw"}
    reverse_language_list = {v: k for k, v in language_list.items()}

    if reverse:
        iterated_list = reverse_language_list
        xbmc_param = xbmc.ENGLISH_NAME
    else:
        iterated_list = language_list
        xbmc_param = xbmc.ISO_639_1

    if language in iterated_list:
        return iterated_list[language]
    else:
        return xbmc.convertLanguage(language, xbmc_param)
