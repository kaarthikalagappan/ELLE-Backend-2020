# ELLE Backend 2020
Backend API files for ELLE 2020 (3rd) version. <br />

## Setup
The following steps can be used to setup the backend on your local machine or a new server:
* Clone this repo
* Install all the dependencies listed in the requirements.txt file by running the command `pip install -r requirements.txt` (run in virtual environment if required)
* Setup a SQL server (this was originally developed on a MySQL database) and use the schema.sql file to create the required tables and fields
* Change the database configuration values in the config.py file to reflect the newly create database information
* Start the Flask framework by running `python3 __init__.py`
    * This starts Flask on debug mode and binded to port 3000

## API Documentation
You can find the documentation for all available APIs here: https://documenter.getpostman.com/view/11718453/Szzhdy4c
Note: The documentation is still being updated and some information presented might not be up-to-date. The current URL for the test server is `http://54.158.210.144` and the URL to hit API endpoints in the test server is `http://54.158.210.144:3000/api/+API_ENDPOINT` and for the production server it is `https://endlesslearner.com/api/+API_ENDPOINT`

## Coding Conventions
### SQL queries
* SQL keywords in capital letters
* Backticks around identifiers
* f-Strings when possible
### Functions
* Use camelCase
### Variables
* Use underscore
### Documentation within code
* Use docstring as an overall summary of the API call
* Otherwise use #
