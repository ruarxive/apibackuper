# -* coding: utf-8 -*-
import logging
import os
import shutil
import json
import configparser
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED
import requests
from timeit import default_timer as timer
import time
from ..common import get_dict_value
from ..constants import DEFAULT_DELAY


class ProjectBuilder:
    """Project builder"""
    def __init__(self, project_path=None):
        self.http = requests.Session()
        self.project_path = os.getcwd() if project_path is None else project_path
        self.config_filename = os.path.join(self.project_path, 'apibackuper.cfg')
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
            config['settings'] = {'initialized' : False, 'name' : name}
            f = open(config_path, 'w', encoding='utf8')
            config.write(f)
            f.close()
            print('Projects %s created' % (name))



    def init(self, url, pagekey, pagesize, datakey, itemkey, changekey, iterateby, http_mode, work_modes):
        conf = self.__read_config(self.config_filename)
        if conf is None:
            print('Config file not found. Please run in project directory')
            return
        pass

    def export(self, format, filename):
        conf = self.__read_config(self.config_filename)
        if conf is None:
            print('Config file not found. Please run in project directory')
            return
        if format == 'jsonl':
            outfile = open(filename, 'w', encoding='utf8')
            data_key = conf.get('data', 'data_key')
            storage_file = os.path.join(self.project_path, 'storage.zip')
            if not os.path.exists(storage_file):
                print('Storage file not found')
                return
            mzip = ZipFile(storage_file, mode='r', compression=ZIP_DEFLATED)
            for fname in mzip.namelist():
                tf = mzip.open(fname, 'r')
                data = json.load(tf)
                tf.close()
                try:
                    for item in get_dict_value(data, data_key):
                        outfile.write(json.dumps(item, ensure_ascii=False)+'\n')
                except KeyError:
                    logging.info('Data key: %s not found' % (data_key))
            outfile.close()
            logging.info('Data exported to %s' % (filename))
        else:
            print("Only 'jsonl' format supported for now.")
        pass

    def run(self, mode):
        conf = self.__read_config(self.config_filename)
        if conf is None:
            print('Config file not found. Please run in project directory')
            return
        tempdir = os.path.join(self.project_path, 'temp')
        if not os.path.exists(tempdir):
            os.mkdir(tempdir)
        if conf.get('storage', 'storage_type') != 'zip':
            print('Only zip storage supported right now')
            return

        if mode == 'full':
            storage_file = os.path.join(tempdir, 'storage.zip')
            mzip = ZipFile(storage_file, mode='w', compression=ZIP_DEFLATED)
        else:
            storage_file = os.path.join(self.project_path, 'storage.zip')
            mzip = ZipFile(storage_file, mode='a', compression=ZIP_DEFLATED)
        http_mode = conf.get('project', 'http_mode')
        start_url = conf.get('project', 'url')
        page_limit = conf.getint('params', 'page_size_limit')

        start = timer()
        params = {}
        params_file = os.path.join(self.project_path, 'params.json')
        if os.path.exists(params_file):
            f = open(params_file, 'r', encoding='utf8')
            params = json.load(f)
            f.close()
        if http_mode == 'GET':
            start_page_data = self.http.get(start_url, params=params).json()
        else:
            start_page_data = self.http.post(start_url, json=params).json()
        end = timer()
        total_number_key = conf.get('data', 'total_number_key')
        try:
            pages_number_key = conf.get('data', 'pages_number_key')
        except:
            pages_number_key = ''
        data_key = conf.get('data', 'data_key')
        if len(total_number_key) > 0:
            total = get_dict_value(start_page_data, total_number_key)
            nr = 1 if total % page_limit > 0 else 0
            num_pages = (total / page_limit) + nr
        elif len(pages_number_key) > 0:
            num_pages = get_dict_value(start_page_data, pages_number_key)
            total = num_pages * page_limit
        else:
            num_pages = None
            total = None
        logging.info('Total pages %d, records %d' % (num_pages, total))
        num_pages = int(num_pages)
        page_number_param = conf.get('params', 'page_number_param')
        page_size_param = conf.get('params', 'page_size_param')
        for page in range(1, num_pages + 1):
            if len(page_size_param) > 0:
                params[page_size_param] = page_limit
                params[page_number_param] = page
            if http_mode == 'GET':
                response = self.http.get(start_url, params=params)
            else:
                response = self.http.post(start_url, json=params)
            logging.info('Saving page %d' % (page))
            mzip.writestr('page_%d.json' % (page), response.content)
            time.sleep(DEFAULT_DELAY)
        mzip.close()
        if mode == 'full':
            shutil.move(storage_file, os.path.join(self.project_path, 'storage.zip'))
        # pass

    def estimate(self, mode):
        """Measures time, size and count of records"""
        conf = self.__read_config(self.config_filename)
        if conf is None:
            print('Config file not found. Please run in project directory')
            return
        http_mode = conf.get('project', 'http_mode')
        start_url = conf.get('project', 'url')
        page_limit = conf.getint('params', 'page_size_limit')
        data = []
        params = {}
        data_size = 0
        total_number_key = conf.get('data', 'total_number_key')
        params_file = os.path.join(self.project_path, 'params.json')
        if len(total_number_key) > 0:
            start = timer()
            if http_mode == 'GET':
                if os.path.exists(params_file):
                    f = open(params_file, 'r', encoding='utf8')
                    params = json.load(f)
                    f.close()
                start_page_data = self.http.get(start_url, params=params).json()
            else:
                f = open(params_file, 'r', encoding='utf8')
                request = json.load(f)
                f.close()
                start_page_data = self.http.post(start_url, json=request).json()
            total = get_dict_value(start_page_data, total_number_key)
            end = timer()
        else:
            print("Can't estimate without total_number_key field in config file")
            return
        request_time = end - start
        nr = 1 if total % page_limit > 0 else 0
        req_number = (total / page_limit) + nr
        data_key = conf.get('data', 'data_key')
        req_data = get_dict_value(start_page_data, data_key)
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
