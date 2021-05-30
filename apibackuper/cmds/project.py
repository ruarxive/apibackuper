# -* coding: utf-8 -*-
import configparser
import json
import logging
import os
import csv
import urllib.request
import shutil
import time
from timeit import default_timer as timer
from zipfile import ZipFile, ZIP_DEFLATED
from urllib.parse import urlparse
import requests
import xmltodict
try:
    import aria2p
except ImportError:
    pass

from ..common import get_dict_value, set_dict_value, update_dict_values
from ..constants import DEFAULT_DELAY, FIELD_SPLITTER
from ..storage import FilesystemStorage, ZipFileStorage

FILE_SIZE_DOWNLOAD_LIMIT = 270000000
DEFAULT_TIMEOUT = 10
PARAM_SPLITTER = ';'

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


def _url_replacer(url, params):
    """Replaces urp params"""
    parsed = urlparse(url)
    finalparams = []
    for k, v in params.items():
        finalparams.append('%s=%s' % (str(k), str(v)))
    return parsed.geturl() + ';' + PARAM_SPLITTER.join(finalparams)



class ProjectBuilder:
    """Project builder"""

    def __init__(self, project_path=None):
        self.http = requests.Session()
        self.project_path = os.getcwd() if project_path is None else project_path
        self.config_filename = os.path.join(self.project_path, 'apibackuper.cfg')
        self.storagedir = os.path.join(self.project_path, 'storage')
        pass

    def __read_config(self, filename):
        if os.path.exists(self.config_filename):
            config = configparser.ConfigParser()
            config.read(filename)
            return config
        return None

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
        conf = self.__read_config(self.config_filename)
        field_splitter = conf.get('settings', 'splitter') if conf.has_option('settings', 'splitter') else FIELD_SPLITTER
        if conf is None:
            print('Config file not found. Please run in project directory')
            return
        if format == 'jsonl':
            outfile = open(filename, 'w', encoding='utf8')
            data_key = conf.get('data', 'data_key')
            details_file = os.path.join(self.storagedir, 'details.zip')
            if conf.has_section('follow') and os.path.exists(details_file):
                follow_data_key = conf.get('follow', 'follow_data_key') if conf.has_option('follow', 'follow_data_key') else None
                mzip = ZipFile(details_file, mode='r', compression=ZIP_DEFLATED)
                for fname in mzip.namelist():
                    tf = mzip.open(fname, 'r')
                    data = json.load(tf)
                    tf.close()
                    try:
                        if follow_data_key:
                            for item in get_dict_value(data, follow_data_key, splitter=field_splitter):
                                outfile.write(json.dumps(item, ensure_ascii=False) + '\n')
                        else:
                            outfile.write(json.dumps(data, ensure_ascii=False) + '\n')
                    except KeyError:
                        logging.info('Data key: %s not found' % (data_key))
            else:
                storage_file = os.path.join(self.storagedir, 'storage.zip')
                if not os.path.exists(storage_file):
                    print('Storage file not found')
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
                        for item in get_dict_value(data, data_key, splitter=field_splitter):
                            outfile.write(json.dumps(item, ensure_ascii=False) + '\n')
                    except KeyError:
                        logging.info('Data key: %s not found' % (data_key))
            outfile.close()
            logging.info('Data exported to %s' % (filename))
        else:
            print("Only 'jsonl' format supported for now.")
        pass

    def run(self, mode):
        conf = self.__read_config(self.config_filename)
        field_splitter = conf.get('settings', 'splitter') if conf.has_option('settings', 'splitter') else FIELD_SPLITTER
        if conf is None:
            print('Config file not found. Please run in project directory')
            return
        if not os.path.exists(self.storagedir):
            os.mkdir(self.storagedir)
        if conf.get('storage', 'storage_type') != 'zip':
            print('Only zip storage supported right now')
            return
        storage_file = os.path.join(self.storagedir, 'storage.zip')
        if mode == 'full':
            mzip = ZipFile(storage_file, mode='w', compression=ZIP_DEFLATED)
        else:
            mzip = ZipFile(storage_file, mode='a', compression=ZIP_DEFLATED)
        http_mode = conf.get('project', 'http_mode')
        start_url = conf.get('project', 'url')
        page_limit = conf.getint('params', 'page_size_limit')
        resp_type = conf.get('project', 'resp_type') if conf.has_option('project', 'resp_type') else 'json'
        iterate_by = conf.get('project', 'iterate_by') if conf.has_option('project', 'iterate_by') else 'page'

        query_mode = conf.get('params', 'query_mode') if conf.has_option('params', 'query_mode') else "query"
        flat_params = conf.getboolean('params', 'force_flat_params') if conf.has_option('params', 'force_flat_params') else False


        start = timer()
        params = None
        params_file = os.path.join(self.project_path, 'params.json')
        if os.path.exists(params_file):
            f = open(params_file, 'r', encoding='utf8')
            params = json.load(f)
            f.close()
        if flat_params:
            flatten = {}
            for k, v in params.items():
                flatten[k] = str(v)

        url_params = None
        params_file = os.path.join(self.project_path, 'url_params.json')
        if os.path.exists(params_file):
            f = open(params_file, 'r', encoding='utf8')
            url_params = json.load(f)
            f.close()
        url = start_url if query_mode != 'params' else _url_replacer(start_url, url_params)
        if http_mode == 'GET':
            if flat_params and len(params.keys()) > 0:
                s = []
                for k, v in flatten.items():
                    s.append('%s=%s' % (k, v.replace("'", '"').replace('True', 'true')))
                response = self.http.get(url + '?' + '&'.join(s))
            else:
                response = self.http.get(url, params=params)
            if resp_type == 'json':
                start_page_data = response.json()
            else:
                start_page_data = xmltodict.parse(response.content)
        else:
#            if flat_params and len(params.keys()) > 0:
#                response = self.http.post(url, json=flatten)
#            else:
            response = self.http.post(url, json=params)
            if resp_type == 'json':
                start_page_data = response.json()
            else:
                start_page_data = xmltodict.parse(response.content)


#        print(json.dumps(start_page_data, ensure_ascii=False))
        end = timer()
        try:
            total_number_key = conf.get('data', 'total_number_key')
        except:
            total_number_key = None
        try:
            pages_number_key = conf.get('data', 'pages_number_key')
        except:
            pages_number_key = ''
        data_key = conf.get('data', 'data_key')
        if len(total_number_key) > 0:
            total = get_dict_value(start_page_data, total_number_key, splitter=field_splitter)
            nr = 1 if total % page_limit > 0 else 0
            num_pages = (total / page_limit) + nr
        elif len(pages_number_key) > 0:
            num_pages = get_dict_value(start_page_data, pages_number_key, splitter=field_splitter)
            total = num_pages * page_limit
        else:
            num_pages = None
            total = None
        logging.info('Total pages %d, records %d' % (num_pages, total))
        num_pages = int(num_pages)

        change_params = {}
        page_number_param = conf.get('params', 'page_number_param') if conf.has_option('params', 'page_number_param') else None
        count_skip_param = conf.get('params', 'count_skip_param') if conf.has_option('params', 'count_skip_param') else None
        count_from_param = conf.get('params', 'count_from_param') if conf.has_option('params', 'count_from_param') else None
        count_to_param = conf.get('params', 'count_to_param') if conf.has_option('params', 'count_to_param') else None
        page_size_param = conf.get('params', 'page_size_param')
        for page in range(1, num_pages + 1):
            if len(page_size_param) > 0:
                change_params[page_size_param] = page_limit
            if iterate_by == 'page':
                change_params[page_number_param] = page
            elif iterate_by == 'skip':
                change_params[count_skip_param] = (page-1) * page_limit
            elif iterate_by == 'range':
                change_params[count_from_param] = (page-1) * page_limit
                change_params[count_to_param] = page * page_limit
            url = start_url if query_mode != 'params' else _url_replacer(start_url, url_params)
            if query_mode == 'params':
                url_params.update(change_params)
            else:
                params = update_dict_values(params, change_params)
                if flat_params and len(params.keys()) > 0:
                    for k, v in params.items():
                        flatten[k] = str(v)
            if http_mode == 'GET':
                if flat_params and len(params.keys()) > 0:
                    s = []
                    for k, v in flatten.items():
                        s.append('%s=%s' % (k, v.replace("'", '"').replace('True', 'true')))
                    response = self.http.get(url + '?' + '&'.join(s))
                else:
                    response = self.http.get(url, params=params)
            else:
#                if flat_params and len(params.keys()) > 0:
#                    response = self.http.post(url, json=flatten)
#                else:
                response = self.http.post(url, json=params)
            logging.info('Saving page %d' % (page))
            if resp_type == 'json':
                outdata = response.content
            elif resp_type == 'xml':
                outdata = json.dump(xmltodict.parse(response.content))
            mzip.writestr('page_%d.json' % (page), outdata)
            time.sleep(DEFAULT_DELAY)
        mzip.close()

        # pass

    def follow(self, mode='item'):
        """Collects data about each data using additional requests"""
        conf = self.__read_config(self.config_filename)
        field_splitter = conf.get('settings', 'splitter') if conf.has_option('settings', 'splitter') else FIELD_SPLITTER

        if conf is None:
            print('Config file not found. Please run in project directory')
            return
        if not os.path.exists(self.storagedir):
            os.mkdir(self.storagedir)
        if conf.get('storage', 'storage_type') != 'zip':
            print('Only zip storage supported right now')
            return
        storage_file = os.path.join(self.storagedir, 'storage.zip')
        details_storage_file = os.path.join(self.storagedir, 'details.zip')
        if not os.path.exists(storage_file):
            print('Storage file not found')
            return
        data_key = conf.get('data', 'data_key')
        follow_item_key = conf.get('follow', 'follow_item_key')
        mzip = ZipFile(storage_file, mode='r', compression=ZIP_DEFLATED)
        follow_mode = conf.get('follow', 'follow_mode')
        if follow_mode == 'item':
            allkeys = []
            logging.info('Extract unique key values from downloaded data')
            for fname in mzip.namelist():
                tf = mzip.open(fname, 'r')
                data = json.load(tf)
                tf.close()
                try:
                    for item in get_dict_value(data, data_key, splitter=field_splitter):
                        allkeys.append(item[follow_item_key])
#                except KeyError:
                except KeyboardInterrupt:
                    logging.info('Data key: %s not found' % (data_key))
            logging.info('%d allkeys to process' % (len(allkeys)))
            if mode == 'full':
                mzip = ZipFile(details_storage_file, mode='w', compression=ZIP_DEFLATED)
                finallist = allkeys
            elif mode == 'continue':
                mzip = ZipFile(details_storage_file, mode='a', compression=ZIP_DEFLATED)
                keys = []
                filenames = mzip.namelist()
                for name in filenames:
                    keys.append(int(name.rsplit('.', 1)[0]))
                logging.info('%d filenames in zip file' % (len(keys)))
                finallist = list(set(allkeys) - set(keys))
            logging.info('%d keys in final list' % (len(finallist)))
            follow_param = conf.get('follow', 'follow_param')
            follow_pattern = conf.get('follow', 'follow_pattern')
            n = 0
            total = len(finallist)
            for key in finallist:
                n += 1
                params = {follow_param : key}
#                if http_mode == 'GET':
                response = self.http.get(follow_pattern, params=params)
#                else:
#                    response = self.http.post(start_url, json=params)
                logging.info('Saving object with id %s. %d of %d' % (key, n, total))
                mzip.writestr('%s.json' % (key), response.content)
                time.sleep(DEFAULT_DELAY)
            mzip.close()
        elif follow_mode == 'url':
            follow_url_key = conf.get('follow', 'follow_url_key')
            allkeys = {}
            logging.info('Extract urls to follow from downloaded data')
            for fname in mzip.namelist():
                tf = mzip.open(fname, 'r')
                data = json.load(tf)
                tf.close()
                try:
                    for item in get_dict_value(data, data_key, splitter=field_splitter):
                        id = item[follow_item_key]
                        allkeys[id] = get_dict_value(item, follow_url_key, splitter=field_splitter)
                except KeyError:
                    logging.info('Data key: %s not found' % (data_key))
            if mode == 'full':
                mzip = ZipFile(details_storage_file, mode='w', compression=ZIP_DEFLATED)
                finallist = allkeys
                n = 0
            elif mode == 'continue':
                mzip = ZipFile(details_storage_file, mode='a', compression=ZIP_DEFLATED)
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
                #                if http_mode == 'GET':
                response = self.http.get(url)
                #                else:
                #                    response = self.http.post(start_url, json=params)
                logging.info('Saving object with id %s. %d of %d' % (key, n, total))
                mzip.writestr('%s.json' % (key), response.content)
                time.sleep(DEFAULT_DELAY)
            mzip.close()
        elif follow_mode == 'drilldown':
            pass
        elif follow_mode == 'prefix':
            allkeys = []
            logging.info('Extract unique key values from downloaded data')
            for fname in mzip.namelist():
                tf = mzip.open(fname, 'r')
                data = json.load(tf)
                tf.close()
                try:
                    for item in get_dict_value(data, data_key, splitter=field_splitter):
                        allkeys.append(item[follow_item_key])
                except KeyboardInterrupt:
                    logging.info('Data key: %s not found' % (data_key))
            if mode == 'full':
                mzip = ZipFile(details_storage_file, mode='w', compression=ZIP_DEFLATED)
                finallist = allkeys
            elif mode == 'continue':
                mzip = ZipFile(details_storage_file, mode='a', compression=ZIP_DEFLATED)
                keys = []
                filenames = mzip.namelist()
                for name in filenames:
                    keys.append(name.rsplit('.', 1)[0])
                finallist = list(set(allkeys) - set(keys))
            follow_pattern = conf.get('follow', 'follow_pattern')
            n = 0
            total = len(finallist)
            for key in finallist:
                n += 1
                url = follow_pattern + str(key)
                print(url)
                response = self.http.get(url)
                logging.info('Saving object with id %s. %d of %d' % (key, n, total))
                mzip.writestr('%s.json' % (key), response.content)
                time.sleep(DEFAULT_DELAY)
            mzip.close()
        else:
            print('Follow section not configured. Please update config file')

    def getfiles(self, be_careful=False):
        """Downloads all files associated with this API data"""
        conf = self.__read_config(self.config_filename)
        field_splitter = conf.get('settings', 'splitter') if conf.has_option('settings', 'splitter') else FIELD_SPLITTER
        if conf is None:
            print('Config file not found. Please run in project directory')
            return
        if not os.path.exists(self.storagedir):
            os.mkdir(self.storagedir)
        if conf.get('storage', 'storage_type') != 'zip':
            print('Only zip storage supported right now')
            return
        storage_file = os.path.join(self.storagedir, 'storage.zip')
        if not os.path.exists(storage_file):
            print('Storage file not found')
            return
        uniq_ids = []
        fetch_mode = conf.get('files', 'fetch_mode')
        default_ext = conf.get('files', 'default_ext') if conf.has_option('files', 'default_ext') else None
        files_keys = conf.get('files', 'keys').split(',')
        root_url = conf.get('files', 'root_url')
        allfiles_name = os.path.join(self.storagedir, 'allfiles.csv')
        if not os.path.exists(allfiles_name):
            if not conf.has_section('follow'):
                logging.info('Extract file urls from downloaded data')
                data_key = conf.get('data', 'data_key')
                mzip = ZipFile(storage_file, mode='r', compression=ZIP_DEFLATED)
                n = 0
                for fname in mzip.namelist():
                    n += 1
                    if n % 10 == 0:
                        logging.info('Processed %d files' % (n))
                    tf = mzip.open(fname, 'r')
                    data = json.load(tf)
                    tf.close()
                    try:
                        for item in get_dict_value(data, data_key, splitter=field_splitter):
                            if item:
                                for key in files_keys:
                                    file_data = get_dict_value(item, key, as_array=True, splitter=field_splitter)
                                    if file_data:
                                        for uniq_id in file_data:
                                            if uniq_id is not None:
                                                uniq_ids.append(uniq_id)
                    except KeyError:
                        logging.info('Data key: %s not found' % (data_key))
            else:
                follow_mode = conf.get('follow', 'follow_mode')
                logging.info('Extract file urls from detailed data')
                if conf.has_option('follow', 'follow_data_key'):
                    follow_data_key = conf.get('follow', 'follow_data_key')
                else:
                    follow_data_key = None
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
                    if follow_data_key:
                        for item in get_dict_value(data, follow_data_key, splitter=field_splitter):
                            items.append(item)
                    else:
                        items = [data, ]
                    for item in items:
                        for key in files_keys:
                            urls = get_dict_value(item, key, as_array=True, splitter=field_splitter)
                            if urls is not None:
                                for uniq_id in urls:
                                    if uniq_id is not None and len(uniq_id.strip()) > 0:
                                        uniq_ids.append(uniq_id)
            mzip.close()

            logging.info('Storing all filenames')
            f = open(allfiles_name, 'w', encoding='utf8')
            for u in uniq_ids:
                f.write(u + '\n')
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


        storage_type = conf.get('files', 'file_storage_type') if conf.has_option('files', 'file_storage_type') else 'zip'
        use_aria2 = conf.get('files', 'use_aria2') if conf.has_option('files', 'use_aria2') else 'False'
        use_aria2 = True if use_aria2 == 'True' else False
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
        if storage_type == 'zip':
            fstorage = ZipFileStorage(files_storage_file, mode='a', compression=ZIP_DEFLATED)
        elif storage_type == 'filesystem':
            fstorage = FilesystemStorage(os.path.join('storage', 'files'))


        n = 0
        storage_mode = conf.get('files', 'storage_mode') if conf.has_option('files', 'storage_mode') else 'filepath'
        for uniq_id in uniq_ids:
            if fetch_mode == 'prefix':
                url = root_url + uniq_id
            elif fetch_mode == 'pattern':
                url = root_url.format(uniq_id)
            n += 1
            if n % 50 == 0:
                logging.info('Downloaded %d files' % (n))
#            if url in processed_files:
#                continue
            if be_careful:
                r = self.http.head(url, timeout=DEFAULT_TIMEOUT)
                if 'content-disposition' in r.headers.keys() and storage_mode == 'filepath':
                    filename = r.headers['content-disposition'].rsplit('filename=', 1)[-1].strip('"')
                elif default_ext is not None:
                    filename = uniq_id + '.' + default_ext
                else:
                    filename = uniq_id
#                if not 'content-length' in r.headers.keys():
#                    logging.info('File %s skipped since content-length not found in headers' % (url))
#                    record = {'filename' : filename, 'filesize' : "0", 'reason' : 'Content-length not set in headers'}
#                    skipped_files_dict[uniq_id] = record
#                    skipped.writerow(record)
#                    continue
                if 'content-length' in r.headers.keys() and int(r.headers['content-length']) > FILE_SIZE_DOWNLOAD_LIMIT and storage_type == 'zip':
                    logging.info('File skipped with size %d and name %s' % (int(r.headers['content-length']) , url))
                    record = {'filename' : filename, 'filesize' : str(r.headers['content-length']), 'reason' : 'File too large. More than %d bytes' % (FILE_SIZE_DOWNLOAD_LIMIT)}
                    skipped_files_dict[uniq_id] = record
                    skipped.writerow(record)
                    continue
            else:
                if default_ext is not None:
                    filename = uniq_id + '.' + default_ext
                else:
                    filename = uniq_id
            if storage_mode == 'filepath':
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
        conf = self.__read_config(self.config_filename)
        field_splitter = conf.get('settings', 'splitter') if conf.has_option('settings', 'splitter') else FIELD_SPLITTER
        if conf is None:
            print('Config file not found. Please run in project directory')
            return
        http_mode = conf.get('project', 'http_mode')
        start_url = conf.get('project', 'url')
        page_limit = conf.getint('params', 'page_size_limit')
        query_mode = conf.get('params', 'query_mode') if conf.has_option('params', 'query_mode') else "query"
        flat_params = conf.getboolean('params', 'force_flat_params') if conf.has_option('params', 'force_flat_params') else False
        data = []
        params = {}
        data_size = 0
        total_number_key = conf.get('data', 'total_number_key')
        params_file = os.path.join(self.project_path, 'params.json')
        if os.path.exists(params_file):
            f = open(params_file, 'r', encoding='utf8')
            params = json.load(f)
            f.close()
        if flat_params:
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
        if len(total_number_key) > 0:
            start = timer()
            url = start_url if query_mode != 'params' else _url_replacer(start_url, url_params)
            if http_mode == 'GET':
                if flat_params and len(params.keys()) > 0:
                    s = []
                    for k, v in params.items():
                        s.append('%s=%s' % (k, v.replace("'", '"').replace('True', 'true')))
                    start_page_data = self.http.get(url + '?' + '&'.join(s)).json()
                else:
                    start_page_data = self.http.get(url, params=params).json()
            else:
                start_page_data = self.http.post(url, json=params).json()
            total = get_dict_value(start_page_data, total_number_key, splitter=field_splitter)
            end = timer()
        else:
            print("Can't estimate without total_number_key field in config file")
            return
        request_time = end - start
        nr = 1 if total % page_limit > 0 else 0
        req_number = (total / page_limit) + nr
        data_key = conf.get('data', 'data_key')
        req_data = get_dict_value(start_page_data, data_key, splitter=field_splitter)
        data.extend(req_data)
        for r in data:
            data_size += len(json.dumps(r))
        avg_size = float(data_size) / len(data)

        print('Total records: %d' % (total))
        print('Records per request: %d' % (page_limit))
        print('Total requests: %d' % (req_number))
        print('Average record size %.2f bytes' % (avg_size))
        print('Estimated size (json lines) %.2f MB' % ((avg_size * total) / 1000000))
        print('Avg request time, seconds %.4f ' % (request_time))
        print('Estimated all requests time, seconds %.4f ' % (request_time * req_number))

    def info(self, stats=False):
        conf = self.__read_config(self.config_filename)
        if conf is None:
            print('Config file not found. Please run in project directory')
            return
        pass
