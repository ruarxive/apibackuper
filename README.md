---
title: apibackuper \-- a command-line tool to archive/backup API calls
---

apibackuper is a command line tool to archive/backup API calls. It\'s
goal to download all data behind REST API and to archive it to local
storage. This tool designed to backup API data, so simple as possible.

::: contents
:::

::: section-numbering
:::

# History

This tool was developed optimize backup/archival procedures for Russian
government information from E-Budget portal budget.gov.ru and some other
government IT systems too. Examples of tool usage could be found in
\"examples\" directory

# Main features

-   Any GET/POST iterative API supported
-   Allows to estimate time required to backup API
-   Stores data inside ZIP container
-   Supports export of backup data as JSON lines, gzip, or parquet files
-   **YAML and INI configuration formats** - choose the format that works best for you
-   Authentication support (Basic, Bearer, API Key, OAuth2)
-   Rate limiting to prevent API throttling
-   Retry mechanisms for handling errors
-   SSL certificate verification control
-   Python scripts support for custom data extraction
-   Comprehensive error handling with helpful messages
-   Documentation
-   Test coverage

# Installation

## Linux

Most Linux distributions provide a package that can be installed using
the system package manager, for example:

``` bash
# Debian, Ubuntu, etc.
$ apt install apibackuper
```

``` bash
# Fedora
$ dnf install apibackuper
```

``` bash
# CentOS, RHEL, ...
$ yum install apibackuper
```

``` bash
# Arch Linux
$ pacman -S apibackuper
```

## Windows, etc.

A universal installation method (that works on Windows, Mac OS X, Linux,
вЂ¦, and always provides the latest version) is to use pip:

``` bash
# Make sure we have an up-to-date version of pip and setuptools:
$ pip install --upgrade pip setuptools

$ pip install --upgrade apibackuper
```

(If `pip` installation fails for some reason, you can try
`easy_install apibackuper` as a fallback.)

## Python version

Python version 3.6 or greater is required.

# Quickstart

This example is about backup of Russian certificate authorities. List of
them published at e-trust.gosuslugi.ru and available via undocumented
API.

``` bash
$ apibackuper create etrust
$ cd etrust
```

Edit `apibackuper.yaml` (or `apibackuper.cfg` for INI format) as:

**YAML format (recommended):**

``` yaml
settings:
  initialized: true
  name: etrust

project:
  description: E-Trust UC list
  url: https://e-trust.gosuslugi.ru/app/scc/portal/api/v1/portal/ca/list
  http_mode: POST
  work_modes: full,incremental,update
  iterate_by: page

params:
  page_size_param: recordsOnPage
  page_size_limit: 100
  page_number_param: page

data:
  total_number_key: total
  data_key: data
  item_key: РеестровыйНомер
  change_key: СтатусАккредитации.ДействуетС

storage:
  storage_type: zip
```

**INI format (alternative):**

``` ini
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
```

Add file `params.json` with parameters used with POST requests:

``` json
{"page":1,"orderBy":"id","ascending":false,"recordsOnPage":100,"searchString":null,"cities":null,"software":null,"cryptToolClasses":null,"statuses":null}
```

Execute command \"estimate\" to see how long data will be collected and
how much space needed

``` bash
$ apibackuper estimate full
```

Output:

``` bash
Total records: 502
Records per request: 100
Total requests: 6
Average record size 32277.96 bytes
Estimated size (json lines) 16.20 MB
Avg request time, seconds 66.9260
Estimated all requests time, seconds 402.8947
```

Execute command \"run\" to collect the data. Result stored in
\"storage.zip\"

``` bash
$ apibackuper run full
```

Export data from storage. The format is automatically detected from the file extension, or you can specify it explicitly:

``` bash
# Export as JSON lines (auto-detected from .jsonl extension)
$ apibackuper export etrust.jsonl

# Export as gzip-compressed JSON lines
$ apibackuper export etrust.jsonl.gz

# Export as Parquet format (requires pandas and pyarrow)
$ apibackuper export etrust.parquet

# Explicitly specify format
$ apibackuper export --format jsonl etrust.jsonl
```

# Configuration

apibackuper supports both **YAML** and **INI** configuration formats. YAML is recommended for better readability and structure. The tool automatically detects `apibackuper.yaml` or `apibackuper.yml` files first, then falls back to `apibackuper.cfg` if no YAML file is found.

## Configuration Format

### YAML Format (Recommended)

``` yaml
settings:
  initialized: true
  name: <name>
  splitter: .

project:
  description: <description>
  url: <url>
  http_mode: GET  # or POST
  work_modes: full,incremental,update
  iterate_by: page  # or skip

params:
  page_size_param: <page size param>
  page_size_limit: <page size limit>
  page_number_param: <page number>
  count_skip_param: <key to iterate in skip mode>

data:
  total_number_key: <total number key>
  data_key: <data key>
  item_key: <item key>
  change_key: <change key>

follow:
  follow_mode: <type of follow mode>
  follow_pattern: <url prefix to follow links>
  follow_data_key: <follow data item key>
  follow_param: <follow param>
  follow_item_key: <follow item key>

files:
  fetch_mode: <file fetch mode>
  root_url: <file root url>
  keys: <keys with file data>
  storage_mode: <file storage mode>

storage:
  storage_type: zip
  compression: true

auth:
  type: basic  # or bearer, apikey, oauth2
  username: <username>
  password: <password>
  # Alternative: password_file: <path to file with password>

rate_limit:
  enabled: true
  requests_per_second: <number>
  requests_per_minute: <number>
  requests_per_hour: <number>
  burst_size: 5

request:
  timeout: 120
  connect_timeout: 30
  read_timeout: 120
  verify_ssl: true  # Set to false to disable SSL certificate verification
  user_agent: "apibackuper/1.0.11"
  max_redirects: 5
  allow_redirects: true
```

### INI Format (Alternative)

``` ini
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

[auth]
type = basic
username = <username>
password = <password>
# Alternative: password_file = <path to file with password>

# For Bearer token:
# type = bearer
# token = <token>
# Alternative: token_file = <path to file with token>

# For API Key:
# type = apikey
# api_key = <api_key>
# api_key_header = X-API-Key

# For OAuth2:
# type = oauth2
# token = <access_token>
# auth_url = <token_endpoint>
# refresh_token = <refresh_token>

[rate_limit]
requests_per_second = <number>
requests_per_minute = <number>
requests_per_hour = <number>
burst_size = 5

[request]
timeout = 120
connect_timeout = 30
read_timeout = 120
verify_ssl = True
user_agent = apibackuper/1.0.11
max_redirects = 5
allow_redirects = True
```

## settings

-   name - short name of the project
-   splitter - value of field splitter. Needed for rare cases when \'.\'
    is part of field name. For example for OData requests and
    \'@odata.count\' field

## project

-   description - text that explains what for is this project
-   url - API endpoint url
-   http_mode - one of HTTP modes: GET or POST
-   work_modes - type of operations: full - archive everything,
    incremental - add new records only, update - collect changed data
    only
-   iterate_by - type of iteration of records. By \'page\' - default,
    page by page or by \'skip\' if skip value provided

## params

-   page_size_param - parameter with page size
-   page_size_limit - limit of records provided by API
-   page_number_param = parameter with page number
-   count_skip_param - parameter for \'skip\' type of iteration

## data

-   total_number_key - key in data with total number of records
-   data_key - key in data with list of records
-   item_key - key in data with unique identifier of the record. Could
    be group of keys separated with comma
-   change_key - key in data that indicates that record changed. Could
    be group of keys separated with comma

## follow

-   follow_mode - mode to follow objects. Could be \'url\' or \'item\'.
    If mode is \'url\' than follow_pattern not used
-   follow_pattern - url pattern / url prefix for followed objects. Only
    for mode \'item\'\'
-   follow_data_key - if object/objects are inside array, key of this
    array
-   follow_param - parameter used in \'item\' mode
-   follow_item_key - item key

## files

-   fetch_mode - file fetch mode. Could be \'prefix\' or \'id\'. Prefix
-   root_url - root url / prefix for files
-   keys - list of keys with urls/file id\'s to search for files to save
-   storage_mode - a way how files stored in storage/files.zip. By
    default \'filepath\' and files storaged same way as they presented
    in url

## storage

-   storage_type - type of local storage. \'zip\' is local zip file is
    default one
-   compression - if True than compressed ZIP file used, less space
    used, more CPU time processing data

## auth

Authentication configuration for protected APIs. Supports multiple authentication methods:

-   type - authentication type: \'basic\', \'bearer\', \'apikey\', or \'oauth2\'
-   For Basic Auth:
    -   username - username for basic authentication
    -   password - password (or use password_file to read from file)
-   For Bearer Token:
    -   token - bearer token (or use token_file to read from file)
-   For API Key:
    -   api_key - API key value
    -   api_key_header - header name for API key (default: \'X-API-Key\')
-   For OAuth2:
    -   token - access token (or use token_file to read from file)
    -   auth_url - OAuth2 token endpoint URL
    -   refresh_token - refresh token for automatic token renewal

## rate_limit

Rate limiting configuration to prevent API throttling:

-   enabled - enable/disable rate limiting (default: true)
-   requests_per_second - maximum requests per second
-   requests_per_minute - maximum requests per minute
-   requests_per_hour - maximum requests per hour
-   burst_size - burst capacity for token bucket algorithm (default: 5)

## request

HTTP request configuration:

-   timeout - total request timeout in seconds (default: 120)
-   connect_timeout - connection timeout in seconds (default: 30)
-   read_timeout - read timeout in seconds (default: 120)
-   verify_ssl - verify SSL certificates (default: true). Set to false if you encounter SSL certificate verification errors. The tool will provide helpful error messages if SSL verification fails.
-   user_agent - custom user agent string (default: "apibackuper/1.0.11")
-   max_redirects - maximum number of redirects to follow (default: 5)
-   allow_redirects - whether to follow redirects (default: true)
-   proxies - proxy configuration (format: "http=http://proxy:8080,https=https://proxy:8080")

# Usage

Synopsis:

``` bash
$ apibackuper [flags] [command] inputfile
```

See also `apibackuper --help`.

## Examples

### Basic Usage

Create a new project:

``` bash
$ apibackuper create budgettofk
```

Estimate execution time and data size. Should be called in project dir or project dir provided via -p parameter:

``` bash
$ apibackuper estimate full -p budgettofk
```

Output:

``` bash
Total records: 12282
Records per request: 500
Total requests: 25
Average record size 1293.60 bytes
Estimated size (json lines) 15.89 MB
Avg request time, seconds 1.8015
Estimated all requests time, seconds 46.0536
```

Run the backup. Should be called in project dir or project dir provided via -p parameter:

``` bash
$ apibackuper run full
```

Export data from project:

``` bash
# Auto-detect format from extension
$ apibackuper export hhemployers.jsonl -p hhemployers

# Export as Parquet
$ apibackuper export data.parquet -p hhemployers

# Explicitly specify format
$ apibackuper export --format jsonl output.jsonl -p hhemployers
```

Get project information:

``` bash
# Text format
$ apibackuper info -p hhemployers

# JSON format
$ apibackuper info --json -p hhemployers
```

Follow each object of downloaded data and make additional requests:

``` bash
$ apibackuper follow continue
```

Download all files associated with API objects:

``` bash
$ apibackuper getfiles
```

Validate project configuration:

``` bash
$ apibackuper validate-config -p hhemployers
```

### Example Projects

The `examples/` directory contains several working examples:

- **budgetreg** - Registry of budget organizations from budget.gov.ru
- **budgetrgz** - Registry of budget tasks from budget.gov.ru
- **budgettofk** - List of Federal treasury branches from budget.gov.ru
- **budgetsclassif** - Budget classification codes from budget.gov.ru
- **etrust** - Russian certificate authorities from e-trust.gosuslugi.ru (POST API)
- **esklp** - ESKLP registration data (with SSL verification disabled)
- **fpreceivers** - Receivers of subsidies and contracts from spending.gov.ru
- **hhemployers** - Russian companies employers from hh.ru
- **subsidies** - Registry of government subsidies from budget.gov.ru
- **sozd** - Russian State Duma bills extractor with custom Python scripts

### Example: Handling SSL Certificate Issues

If you encounter SSL certificate verification errors, you'll see a helpful error message:

```
Error: SSL certificate verification failed for URL https://example.com/api.
Update the project configuration [request] section to set 'verify_ssl = False'
or provide a path to a trusted certificate bundle.
```

To fix this, add a `request` section to your config:

**YAML:**
``` yaml
request:
  verify_ssl: false
```

**INI:**
``` ini
[request]
verify_ssl = False
```

### Example: Using Authentication

**YAML format:**
``` yaml
auth:
  type: bearer
  token: your_token_here
  # Or use a file for security:
  # token_file: /path/to/token.txt
```

**INI format:**
``` ini
[auth]
type = bearer
token = your_token_here
# Or use a file:
# token_file = /path/to/token.txt
```

### Example: Rate Limiting

**YAML format:**
``` yaml
rate_limit:
  enabled: true
  requests_per_second: 10
  requests_per_minute: 600
  requests_per_hour: 36000
  burst_size: 5
```

**INI format:**
``` ini
[rate_limit]
requests_per_second = 10
requests_per_minute = 600
requests_per_hour = 36000
burst_size = 5
```

# Advanced

## Authentication

apibackuper supports multiple authentication methods to work with protected APIs:

### Basic Authentication
```ini
[auth]
type = basic
username = myuser
password = mypassword
# Or use a file for security:
# password_file = /path/to/password.txt
```

### Bearer Token
```ini
[auth]
type = bearer
token = your_bearer_token_here
# Or use a file:
# token_file = /path/to/token.txt
```

### API Key
```ini
[auth]
type = apikey
api_key = your_api_key_here
api_key_header = X-API-Key  # Optional, default is X-API-Key
```

### OAuth2
```ini
[auth]
type = oauth2
token = your_access_token
auth_url = https://api.example.com/oauth/token
refresh_token = your_refresh_token
```

## Rate Limiting

Configure rate limiting to avoid API throttling and respect API limits:

```ini
[rate_limit]
requests_per_second = 10
requests_per_minute = 100
requests_per_hour = 1000
burst_size = 5
```

The rate limiter uses a token bucket algorithm for per-second limits and sliding windows for per-minute and per-hour limits.

## Latest Updates

See [HISTORY.md](HISTORY.md) for detailed changelog. Recent updates include:

- **Version 1.0.11**: 
  - Added **YAML configuration format support** alongside existing INI format
  - Added authentication support (Basic, Bearer, API Key, OAuth2)
  - Added rate limiting functionality to prevent API throttling
  - Added request configuration section (timeouts, SSL verification, proxies)
  - Improved SSL error handling with helpful error messages
  - Enhanced export functionality with Parquet format support
  - Improved error handling and retry mechanisms
- **Version 1.0.8**: Added Python scripts support for HTML data extraction
- **Version 1.0.7**: Improved continue mode support for both "run" and "follow" commands
- **Version 1.0.6**: Added retry mechanisms with configurable delays and retry counts
