# -*- encoding: utf-8 -*-

from flask import send_file, request, json
from flask_restful import Resource, reqparse
from flask_jwt_extended import jwt_required, get_jwt_identity, get_raw_jwt
from db import mysql
from db_utils import *
from utils import *
import os.path

class ModuleStats(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('moduleID', required=True, type=str, help="Please supply the ID of the module you wish to look up.")
        data = parser.parse_args()
        module_id = data['moduleID']
        # Getting all sessions associated with a module
        query = f"SELECT * FROM session WHERE moduleID = '{module_id}'"
        result = get_from_db(query)
        sessions = []
        for row in result:
            session = {}
            session['sessionID'] = row[0]
            session['userID'] = row[1]
            session['moduleID'] = row[2]
            session['sessionDate'] = row[3]
            session['playerScore'] = row[4]
            session['startTime'] = row[5]
            session['endTime'] = row[6]
            session['platform'] = row[7]
            sessions.append(session)
        # Getting all logged_answers associated with each session
        for session in sessions:
            session_id = session['sessionID']
            query = f"SELECT * FROM logged_answer WHERE sessionID = '{session_id}'"
            result = get_from_db(query)
            session['logged_answers'] = []
            for row in result:
                logged_answer = {}
                logged_answer['logID'] = row[0]
                logged_answer['questionID'] = row[1]
                logged_answer['termID'] = row[2]
                logged_answer['sessionID'] = row[3]
                logged_answer['correct'] = row[4]
                session['logged_answers'].append(logged_answer)
        return sessions


