# -*- coding: utf-8 -*-
"""Utility functions for project operations"""
import csv
import os
from typing import Dict, List, Any
from urllib.parse import urlparse

from ..constants import PARAM_SPLITTER


def load_file_list(filename: str, encoding: str = "utf8") -> List[str]:
    """Reads file and returns list of strings as list"""
    flist = []
    with open(filename, "r", encoding=encoding) as fobj:
        for line in fobj:
            flist.append(line.rstrip())
    return flist


def load_csv_data(filename: str, key: str, encoding: str = "utf8", delimiter: str = ";") -> Dict[str, Dict[str, str]]:
    """Reads CSV file and returns list records as array of dicts"""
    flist = {}
    with open(filename, "r", encoding=encoding) as fobj:
        reader = csv.DictReader(fobj, delimiter=delimiter)
        for row in reader:
            flist[row[key]] = row
    return flist


def _url_replacer(url: str, params: Dict[str, Any], query_mode: bool = False) -> str:
    """Replaces URL params"""
    if query_mode:
        query_char = "?"
        splitter = "&"
    else:
        splitter = PARAM_SPLITTER
        query_char = PARAM_SPLITTER
    parsed = urlparse(url)
    finalparams = []
    for key, value in params.items():
        finalparams.append("%s=%s" % (str(key), str(value)))
    return parsed.geturl() + query_char + splitter.join(finalparams)

