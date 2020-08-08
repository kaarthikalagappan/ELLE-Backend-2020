# Database configurations
MYSQL_DATABASE_USER = 'DB_USERNAME'
MYSQL_DATABASE_PASSWORD = 'DB_PASSWORD'
MYSQL_DATABASE_DB = 'DB_NAME'
MYSQL_DATABASE_HOST = 'DB_HOST(LOCALHOST)'
SECRET_KEY = 'SECRET_KEY'

# Allowed image and audio extensions
IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'PNG', 'JPEG', 'JPG']
AUDIO_EXTENSIONS = ['ogg', 'wav', 'mp3']

# Path to folders - change accordingly
TEMP_UPLOAD_FOLDER = 'uploads/'
TEMP_DELETE_FOLDER = 'deletes/'
IMG_UPLOAD_FOLDER = '/var/www/html/Images/'
AUD_UPLOAD_FOLDER = '/var/www/html/Audios/'

# That path to append to the URL so the media
# is accessible publicly (https://endlesslearner.com/Images/...)
IMG_RETRIEVE_FOLDER = '/Images/'
AUD_RETRIEVE_FOLDER = '/Audios/'