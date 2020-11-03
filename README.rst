==============================================================
apibackuper -- a command-line tool to archive/backup API calls
==============================================================


apibackuper is a command line tool to archive/backup API calls.
It's goal to download all data behind REST API and to archive it to local storage.
This tool designed to backup API data, so simple as possible.


.. contents::

.. section-numbering::


History
=======
This tool was developed optimize backup/archival procedures for Russian government information from E-Budget portal budget.gov.ru and
some other government IT systems too. Examples of tool usage could be found in "examples" directory

Main features
=============


* Any GET/POST iterative API supported
* Allows to estimate time required to backup API
* Stores data inside ZIP container
* Supports export of backup data as JSON lines file
* Documentation
* Test coverage



Installation
============

Linux
-----

Most Linux distributions provide a package that can be installed using the
system package manager, for example:

.. code-block:: bash

    # Debian, Ubuntu, etc.
    $ apt install apibackuper

.. code-block:: bash

    # Fedora
    $ dnf install apibackuper

.. code-block:: bash

    # CentOS, RHEL, ...
    $ yum install apibackuper

.. code-block:: bash

    # Arch Linux
    $ pacman -S apibackuper


Windows, etc.
-------------

A universal installation method (that works on Windows, Mac OS X, Linux, вЂ¦,
and always provides the latest version) is to use pip:


.. code-block:: bash

    # Make sure we have an up-to-date version of pip and setuptools:
    $ pip install --upgrade pip setuptools

    $ pip install --upgrade apibackuper


(If ``pip`` installation fails for some reason, you can try
``easy_install apibackuper`` as a fallback.)


Python version
--------------

Python version 3.6 or greater is required.


Quickstart
==========

This example is about backup of Russian certificate authorities.
List of them published at e-trust.gosuslugi.ru and available via undocumented API.

.. code-block:: bash

    $ apibackuper create etrust
    $ cd etrust

Edit apibackuper.cfg as:

.. code-block:: bash

    [settings]
    initialized = True
    name = etrust

    [project]
    description = E-Trust UC list
    url = https://e-trust.gosuslugi.ru/app/scc/portal/api/v1/portal/ca/list
    http_mode = POST
    work_modes = full,incremental,update
    iterate_by = page

    [params]
    page_size_param = recordsOnPage
    page_size_limit = 100
    page_number_param = page

    [data]
    total_number_key = total
    data_key = data
    item_key = РеестровыйНомер
    change_key = СтатусАккредитации.ДействуетС

    [storage]
    storage_type = zip

Add file params.json with parameters used with POST requests

.. code-block:: json

    {"page":1,"orderBy":"id","ascending":false,"recordsOnPage":100,"searchString":null,"cities":null,"software":null,"cryptToolClasses":null,"statuses":null}

Execute command "estimate" to see how long data will be collected and how much space needed

.. code-block:: bash

    $ apibackuper estimate full

Output:

.. code-block:: bash

    Total records: 502
    Records per request: 100
    Total requests: 6
    Average record size 32277.96 bytes
    Estimated size (json lines) 16.20 MB
    Avg request time, seconds 66.9260
    Estimated all requests time, seconds 402.8947

Execute command "run" to collect the data. Result stored in "storage.zip"

.. code-block:: bash

    $ apibackuper run full

Exports data from storage and saves as jsonl file called "etrust.jsonl"

.. code-block:: bash

    $ apibackuper export jsonl etrust.jsonl


Config options
==============

Example config file

.. code-block:: bash

    [settings]
    initialized = True
    name = <name>
    splitter = .

    [project]
    description = <description>
    url = <url>
    http_mode = <GET or POST>
    work_modes = <combination of full,incremental,update>
    iterate_by = <page or skip>

    [params]
    page_size_param = <page size param>
    page_size_limit = <page size limit>
    page_number_param = <page number>
    count_skip_param = <key to iterate in skip mode>


    [data]
    total_number_key = <total number key>
    data_key = <data key>
    item_key = <item key>
    change_key = <change key>

    [follow]
    follow_mode = <type of follow mode>
    follow_pattern = <url prefix to follow links>
    follow_data_key = <follow data item key>
    follow_param = <follow param>
    follow_item_key = <follow item key>

    [files]
    fetch_mode = <file fetch mode>
    root_url = <file root url>
    keys = <keys with file data>
    storage_mode = <file storage mode>


    [storage]
    storage_type = zip
    compression = True


settings
--------
* name - short name of the project
* splitter - value of field splitter. Needed for rare cases when '.' is part of field name. For example for OData requests and '@odata.count' field

project
-------
* description - text that explains what for is this project
* url - API endpoint url
* http_mode - one of HTTP modes: GET or POST
* work_modes - type of operations: full - archive everything, incremental - add new records only, update - collect changed data only
* iterate_by - type of iteration of records. By 'page' - default, page by page or by 'skip' if skip value provided

params
------

* page_size_param - parameter with page size
* page_size_limit - limit of records provided by API
* page_number_param = parameter with page number
* count_skip_param - parameter for 'skip' type of iteration

data
----
* total_number_key - key in data with total number of records
* data_key - key in data with list of records
* item_key - key in data with unique identifier of the record. Could be group of keys separated with comma
* change_key - key in data that indicates that record changed. Could be group of keys separated with comma

follow
------
* follow_mode - mode to follow objects. Could be 'url' or 'item'. If mode is 'url' than follow_pattern not used
* follow_pattern - url pattern / url prefix for followed objects. Only for mode 'item''
* follow_data_key - if object/objects are inside array, key of this array
* follow_param - parameter used in 'item' mode
* follow_item_key - item key


files
-----
* fetch_mode - file fetch mode. Could be 'prefix' or 'id'. Prefix
* root_url - root url / prefix  for files
* keys - list of keys with urls/file id's to search for files to save
* storage_mode - a way how files stored in storage/files.zip. By default 'filepath' and files storaged same way as they presented in url

storage
-------
* storage_type - type of local storage. 'zip' is local zip file is default one
* compression - if True than compressed ZIP file used, less space used, more CPU time processing data

Usage
=====

Synopsis:

.. code-block:: bash

    $ apibackuper [flags] [command] inputfile


See also ``apibackuper --help``.


Examples
--------

Create project "budgettofk":

.. code-block:: bash

    $ apibackuper create budgettofk


Estimate execution time for 'budgettofk' project. Should be called in project dir or project dir provided via -p parameter:

.. code-block:: bash

    $ apibackuper estimate full -p budgettofk

Output

.. code-block:: bash

    Total records: 12282
    Records per request: 500
    Total requests: 25
    Average record size 1293.60 bytes
    Estimated size (json lines) 15.89 MB
    Avg request time, seconds 1.8015
    Estimated all requests time, seconds 46.0536


Run project. Should be called in project dir or project dir provided via -p parameter

.. code-block:: bash

    $ apibackuper run full

Export data from project. Should be called in project dir or project dir provided via -p parameter

.. code-block:: bash

    $ apibackuper export jsonl hhemployers.jsonl -p hhemployers


Follows each object of downloaded data and does requests for each objects
.. code-block:: bash

    $ apibackuper follow continue

Downloads all files associated with API objects
.. code-block:: bash

    $ apibackuper getfiles



Advanced
========

TBD
