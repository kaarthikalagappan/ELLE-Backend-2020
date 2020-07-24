from flask import request
from flask_restful import Resource, reqparse
from flask_jwt_extended import (
    create_access_token,
    get_jwt_identity,
    jwt_required,
    get_raw_jwt,
    get_current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from flaskext.mysql import MySQL
from db import mysql
from db_utils import *
from utils import *
import json
class Testing(Resource):
    def get(self):
        query = "SELECT * FROM user WHERE userID = 1"
        result = get_from_db(query)

        final_list = []

        for row in result:
            new_item = {}
            new_item['id'] = row[0]
            new_item['username'] = row[1] 
            new_item['permissions'] = row[4]
            final_list.append(new_item)

        return final_list