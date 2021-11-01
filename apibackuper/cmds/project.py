# -* coding: utf-8 -*-
import configparser
import json
import logging
import os
import csv
import time
from timeit import default_timer as timer
from zipfile import ZipFile, ZIP_DEFLATED
import gzip
from urllib.parse import urlparse
import requests
import xmltodict
try:
    import aria2p
except ImportError:
    pass

from ..common import get_dict_value, set_dict_value, update_dict_values
from ..constants import DEFAULT_DELAY, FIELD_SPLITTER, DEFAULT_RETRY_COUNT, DEFAULT_TIMEOUT, PARAM_SPLITTER, FILE_SIZE_DOWNLOAD_LIMIT, DEFAULT_ERROR_STATUS_CODES, RETRY_DELAY
from ..storage import FilesystemStorage, ZipFileStorage

def load_file_list(filename, encoding='utf8'):
    """Reads file and returns list of strings as list"""
    flist = []
    with open(filename, 'r', encoding=encoding) as f:
        for l in f:
            flist.append(l.rstrip())
    return flist

def load_csv_data(filename, key, encoding='utf8', delimiter=';'):
    """Reads CSV file and returns list records as array of dicts"""
    flist = {}
    with open(filename, 'r', encoding=encoding) as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        for r in reader:
            flist[r[key]] = r
    return flist


def _url_replacer(url, params, query_mode=False):
    """Replaces urp params"""
    if query_mode:
        query_char = '?'
        splitter = '&'
    else:
        splitter = PARAM_SPLITTER
        query_char = PARAM_SPLITTER
    parsed = urlparse(url)
    finalparams = []
    for k, v in params.items():
        finalparams.append('%s=%s' % (str(k), str(v)))
    return parsed.geturl() + query_char + splitter.join(finalparams)



class ProjectBuilder:
    """Project builder"""

    def __init__(self, project_path=None):
        self.http = requests.Session()
        self.project_path = os.getcwd() if project_path is None else project_path
        self.config_filename = os.path.join(self.project_path, 'apibackuper.cfg')
        self.__read_config(self.config_filename)
        self.enable_logging()


    def enable_logging(self):
        """Enable logging to file and StdErr"""
        logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
        rootLogger = logging.getLogger()

        fileHandler = logging.FileHandler("{0}".format(self.logfile))
        fileHandler.setFormatter(logFormatter)
        rootLogger.addHandler(fileHandler)

        consoleHandler = logging.StreamHandler()
        consoleHandler.setFormatter(logFormatter)
        rootLogger.addHandler(consoleHandler)

    def __read_config(self, filename):
        self.config = None
        if os.path.exists(self.config_filename):
            conf = configparser.ConfigParser()
            conf.read(filename, encoding='utf8')
            self.config = conf
            storagedir = conf.get('storage', 'storage_path') if conf.has_option('storage',
                                                                                   'storage_path') else 'storage'
            self.storagedir = os.path.join(self.project_path, storagedir)
            self.field_splitter = conf.get('settings', 'splitter') if conf.has_option('settings',
                                                                                      'splitter') else FIELD_SPLITTER
            self.id = conf.get('settings', 'id') if conf.has_option('settings', 'id') else None
            self.name = conf.get('settings', 'name')
            self.logfile = conf.get('settings', 'logfile') if conf.has_option('settings', 'logfile') else "apibackuper.log"
            self.data_key = conf.get('data', 'data_key')
            self.storage_type = conf.get('storage', 'storage_type')
            self.http_mode = conf.get('project', 'http_mode')
            self.description = conf.get('project', 'description')  if conf.has_option('project', 'description') else None
            self.start_url = conf.get('project', 'url')
            self.page_limit = conf.getint('params', 'page_size_limit')
            self.resp_type = conf.get('project', 'resp_type') if conf.has_option('project', 'resp_type') else 'json'
            self.iterate_by = conf.get('project', 'iterate_by') if conf.has_option('project', 'iterate_by') else 'page'
            self.default_delay = conf.getint('project', 'default_delay') if conf.has_option('project', 'default_delay') else DEFAULT_DELAY
            self.retry_delay = conf.getint('project', 'retry_delay') if conf.has_option('project',
                                                                                            'retry_delay') else RETRY_DELAY
            self.force_retry = conf.getboolean('project', 'force_retry') if conf.has_option('project', 'force_retry') else False
            self.retry_count = conf.getint('project', 'retry_count') if conf.has_option('project',
                                                                                            'retry_count') else DEFAULT_RETRY_COUNT

            self.start_page = conf.getint('params', 'start_page') if conf.has_option('params', 'start_page') else 1
            self.query_mode = conf.get('params', 'query_mode') if conf.has_option('params', 'query_mode') else "query"
            self.flat_params = conf.getboolean('params', 'force_flat_params') if conf.has_option('params', 'force_flat_params') else False
            self.total_number_key = conf.get('data', 'total_number_key') if conf.has_option('data', 'total_number_key') else ''
            self.pages_number_key = conf.get('data', 'pages_number_key') if conf.has_option('data', 'pages_number_key') else ''
            self.page_number_param = conf.get('params', 'page_number_param') if conf.has_option('params', 'page_number_param') else None
            self.count_skip_param = conf.get('params', 'count_skip_param') if conf.has_option('params', 'count_skip_param') else None
            self.count_from_param = conf.get('params', 'count_from_param') if conf.has_option('params', 'count_from_param') else None
            self.count_to_param = conf.get('params', 'count_to_param') if conf.has_option('params', 'count_to_param') else None
            self.page_size_param = conf.get('params', 'page_size_param') if conf.has_option('params', 'page_size_param') else None
            self.storage_file = os.path.join(self.storagedir, 'storage.zip')
            self.details_storage_file = os.path.join(self.storagedir, 'details.zip')

            if conf.has_section('follow'):
                self.follow_data_key = conf.get('follow', 'follow_data_key') if conf.has_option('follow',
                                                                                       'follow_data_key') else None
                self.follow_item_key = conf.get('follow', 'follow_item_key')  if conf.has_option('follow',
                                                                                       'follow_item_key') else None
                self.follow_mode = conf.get('follow', 'follow_mode')  if conf.has_option('follow',
                                                                                       'follow_mode') else None
                self.follow_http_mode = conf.get('follow', 'follow_http_mode')  if conf.has_option('follow',
                                                                                       'follow_http_mode') else 'GET'
                self.follow_param = conf.get('follow', 'follow_param') if conf.has_option('follow',
                                                                                       'follow_param') else None
                self.follow_pattern = conf.get('follow', 'follow_pattern') if conf.has_option('follow',
                                                                                       'follow_pattern') else None
                self.follow_url_key = conf.get('follow', 'follow_url_key') if conf.has_option('follow',
                                                                                       'follow_url_key') else None
            if conf.has_section('files'):
                self.fetch_mode = conf.get('files', 'fetch_mode')
                self.default_ext = conf.get('files', 'default_ext') if conf.has_option('files', 'default_ext') else None
                self.files_keys = conf.get('files', 'keys').split(',')
                self.root_url = conf.get('files', 'root_url')
                self.storage_mode = conf.get('files', 'storage_mode') if conf.has_option('files', 'storage_mode') else 'filepath'
                self.file_storage_type = conf.get('files', 'file_storage_type') if conf.has_option('files', 'file_storage_type') else 'zip'
                self.use_aria2 = conf.get('files', 'use_aria2') if conf.has_option('files', 'use_aria2') else 'False'


    @staticmethod
    def create(name):
        """Create new project"""
        if not os.path.exists(name):
            os.mkdir(name)
        config_filename = 'apibackuper.cfg'
        config_path = os.path.join(name, config_filename)
        if os.path.exists(config_path):
            print('Project already exists')
        else:
            config = configparser.ConfigParser()
            config['settings'] = {'initialized': False, 'name': name}
            f = open(config_path, 'w', encoding='utf8')
            config.write(f)
            f.close()
            print('Projects %s created' % (name))

    def init(self, url, pagekey, pagesize, datakey, itemkey, changekey, iterateby, http_mode, work_modes):
        """[TBD] Unfinished method. Don't use it please"""
        conf = self.__read_config(self.config_filename)
        if conf is None:
            print('Config file not found. Please run in project directory')
            return
        pass

    def export(self, format, filename):
        """Exports data"""
        if self.config is None:
            print('Config file not found. Please run in project directory')
            return
        if format == 'jsonl':
            outfile = open(filename, 'w', encoding='utf8')
        elif format == 'gzip':
            outfile = gzip.open(filename, mode='wt', encoding='utf8')
            pass
        else:
            print("Only 'jsonl' format supported for now.")
            return
        details_file = os.path.join(self.storagedir, 'details.zip')
        if self.config.has_section('follow') and os.path.exists(details_file):
            mzip = ZipFile(details_file, mode='r', compression=ZIP_DEFLATED)
            for fname in mzip.namelist():
                tf = mzip.open(fname, 'r')
                logging.info('Loading %s' % (fname))
                data = json.load(tf)
                tf.close()
                try:
                    if self.follow_data_key:
                        follow_data =  get_dict_value(data, self.follow_data_key, splitter=self.field_splitter)
                        if isinstance(follow_data, dict):
                            outfile.write(json.dumps(follow_data, ensure_ascii=False) + '\n')
                        else:
                            for item in follow_data:
                                outfile.write(json.dumps(item, ensure_ascii=False) + '\n')
                    else:
                        outfile.write(json.dumps(data, ensure_ascii=False) + '\n')
                except KeyError:
                    logging.info('Data key: %s not found' % (self.data_key))
        else:
            storage_file = os.path.join(self.storagedir, 'storage.zip')
            if not os.path.exists(storage_file):
                print('Storage file not found %s' % (storage_file))
                return
            mzip = ZipFile(storage_file, mode='r', compression=ZIP_DEFLATED)
            for fname in mzip.namelist():
                tf = mzip.open(fname, 'r')
                try:
                    data = json.load(tf)
                except:
                    continue
                finally:
                    tf.close()
                try:
                    if self.data_key:
                        for item in get_dict_value(data, self.data_key, splitter=self.field_splitter):
                            outfile.write(json.dumps(item, ensure_ascii=False) + '\n')
                    else:
                        for item in data:
                            outfile.write(json.dumps(item, ensure_ascii=False) + '\n')
                except KeyError:
                    logging.info('Data key: %s not found' % (self.data_key))
        outfile.close()
        logging.info('Data exported to %s' % (filename))


    def _single_request(self, url, headers, params, flatten=None):
        if self.http_mode == 'GET':
            if self.flat_params and len(params.keys()) > 0:
                s = []
                for k, v in flatten.items():
                    s.append('%s=%s' % (k, v.replace("'", '"').replace('True', 'true')))
                logging.info('url: %s' % (url + '?' + '&'.join(s)))
                if headers:
                    response = self.http.get(url + '?' + '&'.join(s), headers=headers)
                else:
                    response = self.http.get(url + '?' + '&'.join(s))
            else:
                logging.info('url: %s, params: %s' % (url, str(params)))
                if headers:
                    response = self.http.get(url, params=params, headers=headers)
                else:
                    response = self.http.get(url, params=params)
        else:
            logging.debug('Request %s, params %s, headers %s' % (url, str(params), str(headers)))
            if headers:
                response = self.http.post(url, json=params, headers=headers)
            else:
                response = self.http.post(url, json=params)
        return response

    def run(self, mode):
        if self.config is None:
            print('Config file not found. Please run in project directory')
            return
        if not os.path.exists(self.storagedir):
            os.mkdir(self.storagedir)
        if self.storage_type != 'zip':
            print('Only zip storage supported right now')
            return
        storage_file = os.path.join(self.storagedir, 'storage.zip')
        if mode == 'full':
            mzip = ZipFile(storage_file, mode='w', compression=ZIP_DEFLATED)
        else:
            mzip = ZipFile(storage_file, mode='a', compression=ZIP_DEFLATED)


        start = timer()

        headers_file = os.path.join(self.project_path, 'headers.json')
        if os.path.exists(headers_file):
            f = open(headers_file, 'r', encoding='utf8')
            headers = json.load(f)
            f.close()
        else:
            headers = {}

        params = None
        params_file = os.path.join(self.project_path, 'params.json')
        if os.path.exists(params_file):
            f = open(params_file, 'r', encoding='utf8')
            params = json.load(f)
            f.close()
        else:
            params = {}
        if self.flat_params:
            flatten = {}
            for k, v in params.items():
                flatten[k] = str(v)
        else:
            flatten = None

        url_params = None
        params_file = os.path.join(self.project_path, 'url_params.json')
        if os.path.exists(params_file):
            f = open(params_file, 'r', encoding='utf8')
            url_params = json.load(f)
            f.close()
        if self.query_mode == 'params':
            url = _url_replacer(self.start_url, url_params)
        elif self.query_mode == 'mixed':
            url = _url_replacer(self.start_url, url_params, query_mode=True)
        else:
            url = self.start_url
        if self.http_mode == 'GET':
            if self.flat_params and len(params.keys()) > 0:
                s = []
                for k, v in flatten.items():
                    s.append('%s=%s' % (k, v.replace("'", '"').replace('True', 'true')))
                if headers:
                    response = self.http.get(url + '?' + '&'.join(s), headers=headers)
                else:
                    response = self.http.get(url + '?' + '&'.join(s))
            else:
                if headers:
                    response = self.http.get(url, params=params, headers=headers, verify=False)
                else:
                    response = self.http.get(url, params=params, verify=False)
            if self.resp_type == 'json':
                start_page_data = response.json()
            else:
                start_page_data = xmltodict.parse(response.content)
        else:
#            if flat_params and len(params.keys()) > 0:
#                response = self.http.post(url, json=flatten)
#            else:
            logging.debug('Request %s, params %s, headers %s' % (url, str(params), str(headers)))
            if headers:
                response = self.http.post(url, json=params, headers=headers, verify=False)
            else:
                response = self.http.post(url, json=params, verify=False)
            if self.resp_type == 'json':
                start_page_data = response.json()
            else:
                start_page_data = xmltodict.parse(response.content)

#        print(json.dumps(start_page_data, ensure_ascii=False))
        end = timer()

        if len(self.total_number_key) > 0:
            total = get_dict_value(start_page_data, self.total_number_key, splitter=self.field_splitter)
            nr = 1 if total % self.page_limit > 0 else 0
            num_pages = (total / self.page_limit) + nr
        elif len(self.pages_number_key) > 0:
            num_pages = int(get_dict_value(start_page_data, self.pages_number_key, splitter=self.field_splitter))
            total = num_pages * self.page_limit
        else:
            num_pages = None
            total = None
        logging.info('Total pages %d, records %d' % (num_pages, total))
        num_pages = int(num_pages)

        change_params = {}
        for page in range(self.start_page, num_pages + self.start_page):
            if self.page_size_param and len(self.page_size_param) > 0:
                change_params[self.page_size_param] = self.page_limit
            if self.iterate_by == 'page':
                change_params[self.page_number_param] = page
            elif self.iterate_by == 'skip':
                change_params[self.count_skip_param] = (page-1) * self.page_limit
            elif self.iterate_by == 'range':
                change_params[self.count_from_param] = (page-1) * self.page_limit
                change_params[self.count_to_param] = page * self.page_limit
            url = self.start_url if self.query_mode != 'params' else _url_replacer(self.start_url, url_params)
            if self.query_mode in ['params', 'mixed']:
                url_params.update(change_params)
            else:
#                print(params, change_params)
                params = update_dict_values(params, change_params)
                if self.flat_params and len(params.keys()) > 0:
                    for k, v in params.items():
                        flatten[k] = str(v)
            if self.query_mode == 'params':
                url = _url_replacer(self.start_url, url_params)
            elif self.query_mode == 'mixed':
                url = _url_replacer(self.start_url, url_params, query_mode=True)
            else:
                url = self.start_url
            response = self._single_request(url, headers, params, flatten)
            time.sleep(self.default_delay)
            if response.status_code in DEFAULT_ERROR_STATUS_CODES:
                rc = 0
                for rc in range(1, self.retry_count, 1):
                    logging.info('Retry attempt %d of %d, delay %d' % (rc, self.retry_count, self.retry_delay))
                    time.sleep(self.retry_delay)
                    response = self._single_request(url, headers, params, flatten)
                    if response.status_code not in DEFAULT_ERROR_STATUS_CODES:
                        logging.info('Looks like finally we have proper response on %d attempt' %(rc))
                        break
            if response.status_code not in DEFAULT_ERROR_STATUS_CODES:
                if num_pages is not None:
                    logging.info('Saving page %d of %d' % (page, num_pages))
                else:
                    logging.info('Saving page %d' % (page))
                if self.resp_type == 'json':
                    outdata = response.content
                elif self.resp_type == 'xml':
                    outdata = json.dump(xmltodict.parse(response.content))
                mzip.writestr('page_%d.json' % (page), outdata)
            else:
                logging.info('Errors persist on page %d. Stopped' % (page))
                break
        mzip.close()

        # pass

    def follow(self, mode='item'):
        """Collects data about each data using additional requests"""

        if self.config is None:
            print('Config file not found. Please run in project directory')
            return
        if not os.path.exists(self.storagedir):
            os.mkdir(self.storagedir)
        if self.storage_type != 'zip':
            print('Only zip storage supported right now')
            return

        if not os.path.exists(self.storage_file):
            print('Storage file not found')
            return

        params = None
        params_file = os.path.join(self.project_path, 'follow_params.json')
        if os.path.exists(params_file):
            f = open(params_file, 'r', encoding='utf8')
            params = json.load(f)
            f.close()
        else:
            params = {}
        if self.flat_params:
            flatten = {}
            for k, v in params.items():
                flatten[k] = str(v)

        headers_file = os.path.join(self.project_path, 'headers.json')
        if os.path.exists(headers_file):
            f = open(headers_file, 'r', encoding='utf8')
            headers = json.load(f)
            f.close()
        else:
            headers = {}

        mzip = ZipFile(self.storage_file, mode='r', compression=ZIP_DEFLATED)

        if self.follow_mode == 'item':
            allkeys = []
            logging.info('Extract unique key values from downloaded data')
            for fname in mzip.namelist():
                tf = mzip.open(fname, 'r')
                data = json.load(tf)
                tf.close()
                try:
                    for item in get_dict_value(data, self.data_key, splitter=self.field_splitter):
                        allkeys.append(item[self.follow_item_key])
#                except KeyError:
                except KeyboardInterrupt:
                    logging.info('Data key: %s not found' % (self.data_key))
            logging.info('%d allkeys to process' % (len(allkeys)))
            if mode == 'full':
                mzip = ZipFile(self.details_storage_file, mode='w', compression=ZIP_DEFLATED)
                finallist = allkeys
            elif mode == 'continue':
                mzip = ZipFile(self.details_storage_file, mode='a', compression=ZIP_DEFLATED)
                keys = []
                filenames = mzip.namelist()
                for name in filenames:
                    keys.append(int(name.rsplit('.', 1)[0]))
                logging.info('%d filenames in zip file' % (len(keys)))
                finallist = list(set(allkeys) - set(keys))
            logging.info('%d keys in final list' % (len(finallist)))

            n = 0
            total = len(finallist)
            for key in finallist:
                n += 1
                change_params = {}
                change_params[self.follow_param] = key
                params = update_dict_values(params, change_params)
                if self.follow_http_mode == 'GET':
                    if headers:
                        response = self.http.get(self.follow_pattern, params=params, headers=headers)
                    else:
                        response = self.http.get(self.follow_pattern, params=params)
                else:
                    if headers:
                        response = self.http.post(self.follow_pattern, params=params, headers=headers)
                    else:
                        response = self.http.post(self.follow_pattern, params=params)
                logging.info('Saving object with id %s. %d of %d' % (key, n, total))
                mzip.writestr('%s.json' % (key), response.content)
                time.sleep(DEFAULT_DELAY)
            mzip.close()
        elif self.follow_mode == 'url':
            allkeys = {}
            logging.info('Extract urls to follow from downloaded data')
            for fname in mzip.namelist():
                tf = mzip.open(fname, 'r')
                data = json.load(tf)
                tf.close()
#                logging.info(str(data))
                try:
                    for item in get_dict_value(data, self.data_key, splitter=self.field_splitter):
                        id = item[self.follow_item_key]
                        allkeys[id] = get_dict_value(item, self.follow_url_key, splitter=self.field_splitter)
                except KeyError:
                    logging.info('Data key: %s not found' % (self.data_key))
            if mode == 'full':
                mzip = ZipFile(self.details_storage_file, mode='w', compression=ZIP_DEFLATED)
                finallist = allkeys
                n = 0
            elif mode == 'continue':
                mzip = ZipFile(self.details_storage_file, mode='a', compression=ZIP_DEFLATED)
                keys = []
                filenames = mzip.namelist()
                for name in filenames:
                    keys.append(int(name.rsplit('.', 1)[0]))
                finallist = list(set(allkeys.keys()) - set(keys))
                n = len(keys)
            total = len(allkeys.keys())
            for key in finallist:
                n += 1
                url = allkeys[key]
                if headers:
                    response = self.http.get(url, params=params, headers=headers)
                else:
                    response = self.http.get(url, params=params)
                #                else:
                #                if http_mode == 'GET':
                #                    response = self.http.post(start_url, json=params)
                logging.info('Saving object with id %s. %d of %d' % (key, n, total))
                mzip.writestr('%s.json' % (key), response.content)
                time.sleep(DEFAULT_DELAY)
            mzip.close()
        elif self.follow_mode == 'drilldown':
            pass
        elif self.follow_mode == 'prefix':
            allkeys = []
            logging.info('Extract unique key values from downloaded data')
            for fname in mzip.namelist():
                tf = mzip.open(fname, 'r')
                data = json.load(tf)
                tf.close()
                try:
                    for item in get_dict_value(data, self.data_key, splitter=self.field_splitter):
                        allkeys.append(item[self.follow_item_key])
                except KeyboardInterrupt:
                    logging.info('Data key: %s not found' % (self.data_key))
            if mode == 'full':
                mzip = ZipFile(self.details_storage_file, mode='w', compression=ZIP_DEFLATED)
                finallist = allkeys
            elif mode == 'continue':
                mzip = ZipFile(self.details_storage_file, mode='a', compression=ZIP_DEFLATED)
                keys = []
                filenames = mzip.namelist()
                for name in filenames:
                    keys.append(name.rsplit('.', 1)[0])
                finallist = list(set(allkeys) - set(keys))

            n = 0
            total = len(finallist)
            for key in finallist:
                n += 1
                url = self.follow_pattern + str(key)
#                print(url)
                response = self.http.get(url)
                logging.info('Saving object with id %s. %d of %d' % (key, n, total))
                mzip.writestr('%s.json' % (key), response.content)
                time.sleep(DEFAULT_DELAY)
            mzip.close()
        else:
            print('Follow section not configured. Please update config file')

    def getfiles(self, be_careful=False):
        """Downloads all files associated with this API data"""
        if self.config is None:
            print('Config file not found. Please run in project directory')
            return
        if not os.path.exists(self.storagedir):
            os.mkdir(self.storagedir)
        if self.storage_type != 'zip':
            print('Only zip storage supported right now')
            return
        storage_file = os.path.join(self.storagedir, 'storage.zip')
        if not os.path.exists(storage_file):
            print('Storage file not found')
            return
        uniq_ids = set()

        allfiles_name = os.path.join(self.storagedir, 'allfiles.csv')
        if not os.path.exists(allfiles_name):
            if not self.config.has_section('follow'):
                logging.info('Extract file urls from downloaded data')
                mzip = ZipFile(storage_file, mode='r', compression=ZIP_DEFLATED)
                n = 0
                for fname in mzip.namelist():
                    n += 1
                    if n % 10 == 0:
                        logging.info('Processed %d files, uniq ids %d' % (n, len(uniq_ids)))
                    tf = mzip.open(fname, 'r')
                    data = json.load(tf)
                    tf.close()
                    try:
                        if self.data_key:
                            iterate_data = get_dict_value(data, self.data_key, splitter=self.field_splitter)
                        else:
                            iterate_data = data
                        for item in iterate_data:
                            if item:
                                for key in self.files_keys:
                                    file_data = get_dict_value(item, key, as_array=True, splitter=self.field_splitter)
                                    if file_data:
                                        for uniq_id in file_data:
                                            if uniq_id is not None:
                                                if isinstance(uniq_id, list):
                                                    uniq_ids.update(set(uniq_id))
                                                else:
                                                    uniq_ids.add(uniq_id)
                    except KeyError:
                        logging.info('Data key: %s not found' % (str(self.data_key)))
            else:
                details_storage_file = os.path.join(self.storagedir, 'details.zip')
                mzip = ZipFile(details_storage_file, mode='r', compression=ZIP_DEFLATED)
                n = 0
                for fname in mzip.namelist():
                    n += 1
                    if n % 1000 == 0:
                        logging.info('Processed %d records' % (n))
                    tf = mzip.open(fname, 'r')
                    data = json.load(tf)
                    tf.close()
                    items = []
                    if self.follow_data_key:
                        for item in get_dict_value(data, self.follow_data_key, splitter=self.field_splitter):
                            items.append(item)
                    else:
                        items = [data, ]
                    for item in items:
                        for key in self.files_keys:
                            urls = get_dict_value(item, key, as_array=True, splitter=self.field_splitter)
                            if urls is not None:
                                for uniq_id in urls:
                                    if uniq_id is not None and len(uniq_id.strip()) > 0:
                                        uniq_ids.append(uniq_id)
            mzip.close()

            logging.info('Storing all filenames')
            f = open(allfiles_name, 'w', encoding='utf8')
            for u in uniq_ids:
                f.write(str(u) + '\n')
            f.close()
        else:
            logging.info('Load all filenames')
            uniq_ids = load_file_list(allfiles_name)
        # Start download
        processed_files = []
        skipped_files_dict = {}
        files_storage_file = os.path.join(self.storagedir, 'files.zip')
        files_list_storage = os.path.join(self.storagedir, 'files.list')
        files_skipped = os.path.join(self.storagedir, 'files_skipped.list')
        if os.path.exists(files_list_storage):
            processed_files = load_file_list(files_list_storage, encoding='utf8')
            list_file = open(files_list_storage, 'a', encoding='utf8')
        else:
            list_file = open(files_list_storage, 'w', encoding='utf8')
        if os.path.exists(files_skipped):
            skipped_files_dict = load_csv_data(files_skipped, key='filename', encoding='utf8')
            skipped_file = open(files_skipped, 'a', encoding='utf8')
            skipped = csv.DictWriter(skipped_file, delimiter=';', fieldnames=['filename', 'filesize', 'reason'])
        else:
            skipped_files_dict = {}
            skipped_file = open(files_skipped, 'w', encoding='utf8')
            skipped = csv.DictWriter(skipped_file, delimiter=';', fieldnames=['filename', 'filesize', 'reason'])
            skipped.writeheader()


        use_aria2 = True if self.use_aria2 == 'True' else False
        if use_aria2:
            aria2 = aria2p.API(
                aria2p.Client(
                    host="http://localhost",
                    port=6800,
                    secret=""
                )
            )
        else:
            aria2 = None
        if self.file_storage_type == 'zip':
            fstorage = ZipFileStorage(files_storage_file, mode='a', compression=ZIP_DEFLATED)
        elif self.file_storage_type == 'filesystem':
            fstorage = FilesystemStorage(os.path.join('storage', 'files'))


        n = 0
        for uniq_id in uniq_ids:
            if self.fetch_mode == 'prefix':
                url = self.root_url + str(uniq_id)
            elif self.fetch_mode == 'pattern':
                url = self.root_url.format(uniq_id)
            n += 1
            if n % 50 == 0:
                logging.info('Downloaded %d files' % (n))
#            if url in processed_files:
#                continue
            if be_careful:
                r = self.http.head(url, timeout=DEFAULT_TIMEOUT)
                if 'content-disposition' in r.headers.keys() and self.storage_mode == 'filepath':
                    filename = r.headers['content-disposition'].rsplit('filename=', 1)[-1].strip('"')
                elif self.default_ext is not None:
                    filename = uniq_id + '.' + self.default_ext
                else:
                    filename = uniq_id
#                if not 'content-length' in r.headers.keys():
#                    logging.info('File %s skipped since content-length not found in headers' % (url))
#                    record = {'filename' : filename, 'filesize' : "0", 'reason' : 'Content-length not set in headers'}
#                    skipped_files_dict[uniq_id] = record
#                    skipped.writerow(record)
#                    continue
                if 'content-length' in r.headers.keys() and int(r.headers['content-length']) > FILE_SIZE_DOWNLOAD_LIMIT and self.file_storage_type == 'zip':
                    logging.info('File skipped with size %d and name %s' % (int(r.headers['content-length']) , url))
                    record = {'filename' : filename, 'filesize' : str(r.headers['content-length']), 'reason' : 'File too large. More than %d bytes' % (FILE_SIZE_DOWNLOAD_LIMIT)}
                    skipped_files_dict[uniq_id] = record
                    skipped.writerow(record)
                    continue
            else:
                if self.default_ext is not None:
                    filename = str(uniq_id) + '.' + self.default_ext
                else:
                    filename = str(uniq_id)
            if self.storage_mode == 'filepath':
                filename = urlparse(url).path
            logging.info('Processing %s as %s' % (url, filename))
            if fstorage.exists(filename):
                logging.info('File %s already stored' % (filename))
                continue
            if not use_aria2:
                response = self.http.get(url, timeout=DEFAULT_TIMEOUT)
                fstorage.store(filename, response.content)
                list_file.write(url + '\n')
            else:
                aria2.add_uris(uris=[url,], options={'out': filename, 'dir' : os.path.abspath(os.path.join('storage', 'files'))})


        fstorage.close()
        list_file.close()
        skipped_file.close()

    def estimate(self, mode):
        """Measures time, size and count of records"""
        if self.config is None:
            print('Config file not found. Please run in project directory')
            return
        data = []
        params = {}
        data_size = 0

        headers = None
        headers_file = os.path.join(self.project_path, 'headers.json')
        if os.path.exists(headers_file):
            f = open(headers_file, 'r', encoding='utf8')
            headers = json.load(f)
            f.close()
        else:
            headers = {}

        params_file = os.path.join(self.project_path, 'params.json')
        if os.path.exists(params_file):
            f = open(params_file, 'r', encoding='utf8')
            params = json.load(f)
            f.close()
        if self.flat_params:
            flatten = {}
            for k, v in params.items():
                flatten[k] = str(v)
            params = flatten

        url_params = None
        params_file = os.path.join(self.project_path, 'url_params.json')
        if os.path.exists(params_file):
            f = open(params_file, 'r', encoding='utf8')
            url_params = json.load(f)
            f.close()
        if len(self.total_number_key) > 0:
            start = timer()
            if self.query_mode == 'params':
                url = _url_replacer(self.start_url, url_params)
            elif self.query_mode == 'mixed':
                url = _url_replacer(self.start_url, url_params, query_mode=True)
            else:
                url = self.start_url
            if self.http_mode == 'GET':
                if self.flat_params and len(params.keys()) > 0:
                    s = []
                    for k, v in params.items():
                        s.append('%s=%s' % (k, v.replace("'", '"').replace('True', 'true')))
                    if headers:
                        start_page_data = self.http.get(url + '?' + '&'.join(s), headers=headers).json()
                    else:
                        start_page_data = self.http.get(url + '?' + '&'.join(s)).json()
                else:
                    logging.debug('Start request params: %s headers: %s' %(str(params), str(headers)))
                    if headers and len(headers.keys()) > 0:
                        if params and len(params.keys()) > 0:
                            response = self.http.get(url, params=params, headers=headers)
                        else:
                            response = self.http.get(url, headers=headers)
                    else:
                        if params and len(params.keys()) > 0:
                            response = self.http.get(url, params=params)
                        else:
                            response = self.http.get(url)

                    start_page_data = response.json()
            else:
                logging.info(url)
                if headers:
                    response = self.http.post(url, json=params, verify=False, headers=headers)
                else:
                    response = self.http.post(url, json=params, verify=False)
                start_page_data = response.json()
            total = get_dict_value(start_page_data, self.total_number_key, splitter=self.field_splitter)
            end = timer()
        else:
            print("Can't estimate without total_number_key field in config file")
            return
        request_time = end - start
        nr = 1 if total % self.page_limit > 0 else 0
        req_number = (total / self.page_limit) + nr
        if self.data_key:
            req_data = get_dict_value(start_page_data, self.data_key, splitter=self.field_splitter)
            data.extend(req_data)
        else:
            data.extend(start_page_data)
        for r in data:
            data_size += len(json.dumps(r))
        avg_size = float(data_size) / len(data)

        print('Total records: %d' % (total))
        print('Records per request: %d' % (self.page_limit))
        print('Total requests: %d' % (req_number))
        print('Average record size %.2f bytes' % (avg_size))
        print('Estimated size (json lines) %.2f MB' % ((avg_size * total) / 1000000))
        print('Avg request time, seconds %.4f ' % (request_time))
        print('Estimated all requests time, seconds %.4f ' % (request_time * req_number))

    def info(self, stats=False):
        if self.config is None:
            print('Config file not found. Please run in project directory')
            return
        pass


    def to_package(self, filename=None):
        if self.config is None:
            print('Config file not found. Please run in project directory')
            return


#        if not filename:
#            filename = 'package.zip'
#        print('Package saved as %s' % filename)
        pass
