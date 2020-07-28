# -*- encoding: utf-8 -*-

from flask import send_file, request, json
from flask_restful import Resource, reqparse
from flask_jwt_extended import jwt_required, get_jwt_identity, get_raw_jwt
from db import mysql
from db_utils import *
from utils import *
from datetime import datetime, timedelta
import os.path

def get_platforms():
    query = "SELECT DISTINCT platform FROM session"
    return get_from_db(query)

def get_module_headers():
    query = "SELECT DISTINCT moduleID, name FROM module"
    return get_from_db(query)

def query_sessions(query):
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
        # Ignoring unfinished sessions
        if session['endTime'] != None:
            sessions.append(session)
    return sessions

def get_averages(sessions):
    if len(sessions) == 0:
        return None
    scoreTotal = 0
    timeTotal = 0
    for session in sessions:
        # Accumulating score
        scoreTotal += session['playerScore']
        startDateTime = datetime.strptime(session['startTime'], '%H:%M')
        # Accumulating time
        endDateTime = datetime.strptime(session['endTime'], '%H:%M')
        elapsedTime = endDateTime - startDateTime
        timeTotal += elapsedTime.total_seconds()
    # Returning statistics object
    stat = {}
    stat['averageScore'] = scoreTotal / len(sessions)
    # Session length in minutes
    stat['averageSessionLength'] = timeTotal * 60 / len(sessions)
    return stat
        


# Returns a list of sessions associated with the given module
class ModuleReport(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('moduleID', required=True, type=str, help="Please supply the ID of the module you wish to look up.")
        data = parser.parse_args()
        module_id = data['moduleID']
        # Getting all sessions associated with a module
        query = f"SELECT * FROM session WHERE moduleID = '{module_id}'"
        sessions = query_sessions(query)
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

# Provides a list of all platform names currently used by sessions in the database
class PlatformNames(Resource):
    @jwt_required
    def get(self):
        result = get_platforms()
        return result
        

# Provides the average score and session duration for the given module
class ModuleStats(Resource):
    @jwt_required
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('moduleID', required=True, type=str, help="Please supply the ID of the module you wish to look up.")
        data = parser.parse_args()
        module_id = data['moduleID']
        platforms = get_platforms()
        stats = []
        for platform in platforms:
            query = f"SELECT * FROM session WHERE moduleID = {module_id} AND platform = '{platform[0]}'"
            sessions = query_sessions(query)
            stat = get_averages(sessions)
            if not stat:
                continue
            stat['platform'] = platform[0]
            stats.append(stat)
        return stats
        



# Provides the average scores and session durations for the given game
class PlatformStats(Resource):
    @jwt_required
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('platform', required=True, type=str, help="Please supply the name of the platform you wish to look up.")
        data = parser.parse_args()
        platform = data['platform']
        modules = get_module_headers()
        stats = []
        for module in modules:
            query = f"SELECT * FROM session WHERE moduleID = {module[0]} AND platform = '{platform}'"
            sessions = query_sessions(query)
            stat = get_averages(sessions)
            if not stat:
                continue
            stat['module'] = module[1]
            stats.append(stat)
        return stats
