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