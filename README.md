# ELLE Backend 2020
Backend API files for ELLE 2020 (3rd) version. <br />
To add database credentials, create the config.py file, add the following data to the config files, and replace the variable values to the correct information:
```
MYSQL_DATABASE_USER = DATABASE_USERNAME
MYSQL_DATABASE_PASSWORD = DATABASE_USER_PASSWORD
MYSQL_DATABASE_DB = DATABASE_NAME
MYSQL_DATABASE_HOST = HOST_NAME #usually localhost
SECRET_KEY = RANDOM_SECRET_KEY #some random string to act as secret key for Python Flask
```