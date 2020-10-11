from flask import request, Response
from flask_restful import Resource, reqparse
from flask_jwt_extended import (
    create_access_token,
    get_jwt_identity,
    jwt_required,
    get_raw_jwt,
    get_current_user,
    get_jwt_claims
)
from werkzeug.security import generate_password_hash, check_password_hash
from flaskext.mysql import MySQL
from config import (
    IMAGE_EXTENSIONS, AUDIO_EXTENSIONS, TEMP_DELETE_FOLDER,
    TEMP_UPLOAD_FOLDER, IMG_UPLOAD_FOLDER, AUD_UPLOAD_FOLDER,
    IMG_RETRIEVE_FOLDER, AUD_RETRIEVE_FOLDER
    )
from db import mysql
from db_utils import *
from utils import *
import json
import dateutil.parser as dateutil
import datetime

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
        final_list.append(IMAGE_EXTENSIONS)
        final_list.append(AUDIO_EXTENSIONS)
        final_list.append(IMG_RETRIEVE_FOLDER)
        final_list.append(AUD_RETRIEVE_FOLDER)
        final_list.append(IMG_UPLOAD_FOLDER)
        final_list.append(AUD_UPLOAD_FOLDER)
        final_list.append(TEMP_DELETE_FOLDER)
        final_list.append(TEMP_UPLOAD_FOLDER)

        return final_list
    
    def post(self):
        # print(request.data)
        parser = reqparse.RequestParser()
        parser.add_argument('questionID',
		                          type=str,
		                          required=True,
		                          )
        data = parser.parse_args()

        array_of_objectss = request.form.getlist('array_of_objects')
        # print(array_of_objectss)
        for s in array_of_objectss:
            # print("s: ", s)
            s = json.loads(s)
            print(s)
            for _s in s:
                print(_s)
                # print(_s['city'])
                # print(_s['people'])
                for p in _s['people']:
                    print(p)
                # print(_s['population'])

        # answer_list = request.form.getlist('new_answers')
        # answer_list = json.loads(answer_list[0])
        # for a in answer_list:
        #     print(a)
        # return answer_list

        # print([json.loads(s) for s in array_of_objects])

        # req = request.get_json().get('array_of_objects')
        # # questionID = request.get_json().get('questionID')
        # answer_list = request.get_json().get('answers')
        # # print(req)
        # # print(questionID)

        # for r in req:
        #     print(r)
        #     print(r['city'])
        #     print(r['people'])
        #     for p in r['people']:
        #         print(p)
        #     print(r['population'])

        # query = "SELECT * FROM `answer` WHERE questionID = %s"
        # result = get_from_db(query, data['questionID'])
        # # print(result)
        # res = [row[1] for row in result]
        # print(res)

        # dif_list = list(set(res) ^ set(answer_list))
        # return (dif_list)

        # for e in dif_list:
        #     if e in res:
        #         print("remove ", e)
        #     else:
        #         print("add", e)




        # print([json.loads(s) for s in array_of_objects])

class JWTTest(Resource):
    @jwt_required
    def get(self):
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401

        return {"user_id": user_id, "permission" : permission}


class GetLoggedAnswersCSV(Resource):
    @jwt_required
    def get(self):
        permission, user_id = validate_permissions()
        if not permission or not user_id or permission != 'su':
            return "Invalid user", 401
        
        csv = 'Session ID, User ID, User Name, Module ID, Module Name, Session Date, Player Score, Start Time, End Time, Platform, Mode\n'
        query = """
                SELECT session.*, user.username, module.name FROM session 
                INNER JOIN user ON user.userID = session.userID
                INNER JOIN module on module.moduleID = session.moduleID
                """
        results = get_from_db(query)
        if results and results[0]:
            for record in results:
                platform = "Mobile" if record[7] == 'mb' else "PC" if record[7] == 'pc' else "Virtual Reality"
                csv = csv + f"""{record[0]}, {record[1]}, {record[9]}, {record[2]}, {record[10]}, {record[3]}, {record[4]}, {record[5]}, {record[6]}, {platform}, {record[8]}\n"""
        return Response(
            csv,
            mimetype="text/csv",
            headers={"Content-disposition":
            "attachment; filename=Sessions.csv"})