# -*- encoding: utf-8 -*-

from flask import send_file, request, json
from flask_restful import Resource, reqparse
from flask_jwt_extended import jwt_required, get_jwt_identity, get_raw_jwt
from db import mysql
from db_utils import *
from utils import *
from datetime import datetime, timedelta
import os.path
import datetime
import time
from config import GAME_PLATFORMS

def get_module_headers():
    query = "SELECT DISTINCT moduleID, name FROM module"
    return get_from_db(query)


def query_sessions(query, parameters=None):
    result = get_from_db(query, parameters)
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
        if session['endTime'] != None and session['startTime'] != None and session['playerScore'] != None:
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
        startDateTime = session['startTime']
        # Accumulating time
        endDateTime = session['endTime']
        elapsedTime = endDateTime - startDateTime
        timeTotal += elapsedTime.seconds
    # Returning statistics object
    stat = {}
    stat['averageScore'] = scoreTotal / len(sessions)
    # Session length in minutes
    stat['averageSessionLength'] = str(datetime.timedelta(seconds = (timeTotal)))
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
        return GAME_PLATFORMS
        

# Provides the average score and session duration for the given module in every platform
class ModuleStats(Resource):
    @jwt_required
    def get(self):
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401
        
        parser = reqparse.RequestParser()
        parser.add_argument('moduleID', required=True, type=str, help="Please supply the ID of the module you wish to look up.")
        data = parser.parse_args()
        module_id = data['moduleID']
        stats = []
        for platform in GAME_PLATFORMS:
            query = f"SELECT * FROM session WHERE moduleID = {module_id} AND platform = '{platform}'"
            sessions = query_sessions(query)
            stat = get_averages(sessions)
            if not stat:
                continue
            stat['platform'] = platform
            stats.append(stat)
        return stats
        

# Provides the average score and session duration for the given module in every platform
class AllModuleStats(Resource):
    @jwt_required
    def get(self):
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401
        
        if permission == 'su':
            query = "SELECT * FROM session WHERE platform = %s"
        elif permission == 'pf':
            query = "SELECT * FROM session INNER JOIN group_user ON group_user.userID = " + str(user_id) + \
                    " INNER JOIN group_module ON group_module.groupID = group_user.groupID \
                    WHERE session.platform = %s AND session.moduleID = group_module.moduleID"
        else:
            query = "SELECT * FROM session WHERE userID = " + str(user_id) + " AND platform = %s"

        stats = []
        for platform in GAME_PLATFORMS:
            sessions = query_sessions(query, platform)
            stat = get_averages(sessions)
            if not stat:
                continue
            stat['platform'] = platform
            stats.append(stat)
        
        return stats


# # Provides the average scores and session durations for the given game
# class PlatformStats(Resource):
#     @jwt_required
#     def get(self):
#         parser = reqparse.RequestParser()
#         parser.add_argument('platform', required=True, type=str, help="Please supply the name of the platform you wish to look up.")
#         data = parser.parse_args()
#         platform = data['platform']
#         modules = get_module_headers()
#         stats = []
#         for module in modules:
#             query = f"SELECT * FROM session WHERE moduleID = {module[0]} AND platform = '{platform}'"
#             sessions = query_sessions(query)
#             stat = get_averages(sessions)
#             if not stat:
#                 continue
#             stat['module'] = module[1]
#             stats.append(stat)
#         return stats

class PlatformStats(Resource):
    @jwt_required
    def get(self):
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401

        retrieve_stats_query = """
                               SELECT `session`.* FROM session WHERE `session`.`platform` = %s
                               """
        frequency_objs = 0
        stats = {}
        for platform in GAME_PLATFORMS:
            time_spent = 0
            total_score = 0
            performance_objs = 0
            total_platform_objs = 0

            db_records = get_from_db(retrieve_stats_query, platform)
            if not db_records or not db_records:
                continue
            for record in db_records:
                if not record[6]:
                    log_time_query = f"SELECT logged_answer.log_time FROM `logged_answer` WHERE sessionID={record[0]} ORDER BY logID DESC LIMIT 1"
                    last_log_time = get_from_db(log_time_query)
                    if last_log_time and last_log_time[0] and last_log_time[0][0] != None:
                        record[6] = last_log_time[0][0]
                        if record[3] != time.strftime("%Y-%m-%d"):
                            query_update_time = f"UPDATE session SET session.endTime = '{last_log_time[0][0]}' WHERE session.sessionID = {record[0]}"
                            post_to_db(query_update_time)
                    else:
                        continue
                time_spent = time_spent + (record[6] - record[5]).seconds

                if not record[4]:
                    get_logged_answer_score = f"""
                                              SELECT SUM(logged_answer.correct) 
                                              FROM `logged_answer` 
                                              WHERE logged_answer.sessionID = {record[0]}
                                              """
                    answer_data = get_from_db(get_logged_answer_score)
                    if answer_data and answer_data[0] and answer_data[0][0] != None:
                        correct_answers = int(answer_data[0][0])
                        if record[3] != time.strftime("%Y-%m-%d"):
                            update_score_query = f"""
                                                UPDATE session SET session.playerScore = {correct_answers}
                                                WHERE session.sessionID = {record[0]}
                                                """
                            post_to_db(update_score_query)
                        record[4] = correct_answers
                    else:
                        continue
                total_score = total_score + record[4]

                total_platform_objs = total_platform_objs + 1
                frequency_objs = frequency_objs + 1
            
            stats[platform] = {'frequency' : total_platform_objs, \
                               'total_score' : total_score, \
                               'time_spent' : str(datetime.timedelta(seconds = time_spent)), \
                               'avg_score' : total_score / total_platform_objs if total_platform_objs != 0 else 0, \
                               'avg_time_spent' : str(datetime.timedelta(seconds = ((time_spent/total_platform_objs) if total_platform_objs != 0 else 0))), \
                               'total_records_avail' : total_platform_objs}
        
        for platform in GAME_PLATFORMS:
            stats[platform]['frequency'] = stats[platform]['frequency']/frequency_objs if frequency_objs != 0 else 0

        return stats


# Provides a percentage of how many modules belong to a specific language (e.g. 0.6 modules are Spanish, 0.2 are English, and 0.2 are French)
class LanguageStats(Resource):
    @jwt_required
    def get(self):
        get_module_lang_query = "SELECT module.moduleID, module.language from module"
        all_modules = get_from_db(get_module_lang_query)
        # A dictionary to hold language codes and how many times it has occured
        lang_count = {}
        total_counter = 0
        for module in all_modules:
            lang_code = module[1].lower()
            if lang_code not in lang_count:
                lang_count[lang_code] = 1
            else:
                lang_count[lang_code] = lang_count[lang_code] + 1
            total_counter = total_counter + 1
        
        for lang_code in lang_count:
            lang_count[lang_code] = lang_count[lang_code]/total_counter
        
        lang_count = {key: val for key, val in sorted(lang_count.items(), key=lambda item: item[1])}

        return lang_count, 200