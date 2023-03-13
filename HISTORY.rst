.. :changelog:

History
=======

1.0.8 (2023-03-13)
-----------------
* Added Python scripts support to extract data from HTML web pages and 'sozd' example with scripts usage.

1.0.7 (2021-11-4)
-----------------
* Fixed "continue" mode. Now supports continue not only for "follow" command but for "run" command too. Use "apibackuper run continue" if it was stopped by error or user input.

1.0.6 (2021-11-1)
-----------------
* Added "default_delay", 'retry_delay' and "retry_count" to manage error handling
* If get HTTP status 500 or 503 starts retrying latest request till HTTP status 200 or retry_count ends

1.0.5 (2021-05-31)
------------------
* Minor fixes

1.0.4 (2021-05-31)
------------------
* Added "start_page" in case if start_page is not 1 (could be 0 sometimes)
* Added support of data returned as JSON array, not JSON dict and data_key not provided
* Added initial code to implement Frictionless Data packaging

1.0.3 (2020-10-28)
------------------
* Added several new options
* Added aria2 download support for files downloading


1.0.2 (2020-09-20)
------------------
* Using permanent storage dir "storage" instead of temporary "temp" dir
* Added logic to do requests to get addition info on retrieved objects, command "follow"
* Added logic to retrieve files linked with retrieved objects, command "getfiles"

1.0.1 (2020-08-14)
------------------
* First public release on PyPI and updated github code


