# -*- encoding: utf-8 -*-

from flask import send_file, request, json
from flask_restful import Resource, reqparse
from flask_jwt_extended import jwt_required, get_jwt_identity, get_raw_jwt
from db import mysql
from db_utils import *
from utils import *
from datetime import datetime, timedelta
from config import REDIS_CHARSET, REDIS_HOST, REDIS_PORT
import os.path
import datetime
import time
import redis
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
            query = "SELECT DISTINCT moduleID FROM module"
        elif permission == 'pf':
            query = "SELECT DISTINCT module.moduleID FROM module" \
                    " INNER JOIN group_user ON group_user.userID = " + str(user_id) + \
                    " INNER JOIN group_module ON group_module.groupID = group_user.groupID"
        else:
            query = "SELECT DISTINCT module.moduleID FROM module" \
                    " INNER JOIN group_user ON group_user.userID = " + str(user_id) + \
                    " INNER JOIN group_module ON group_module.groupID = group_user.groupID"
        
        moduleIDs = get_from_db(query)
        if permission != 'su' and permission != 'pf':
            query = "SELECT * FROM session WHERE moduleID = %s AND userID = %s"
        else:
            query = "SELECT * FROM session WHERE moduleID = %s"

        stats = []
        for moduleID in moduleIDs:
            if permission != 'su' and permission != 'pf':
                sessions = query_sessions(query, (moduleID, user_id))
            else:
                sessions = query_sessions(query, moduleID)
            stat = get_averages(sessions)
            if not stat:
                continue
            mn_query = f"SELECT name FROM module WHERE moduleID = {moduleID[0]}"
            module_name = get_from_db(mn_query)
            stat['moduleID'] = moduleID[0]
            stat['name'] = module_name[0][0]
            stats.append(stat)

        stats.sort(reverse=True, key=lambda s: s['averageScore'])
        return stats


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

                            try:
                                # Since we changed the sessions data on db, invalidate Redis cache
                                redis_conn = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, charset=REDIS_CHARSET, decode_responses=True)
                                redis_conn.delete('sessions_csv')
                            except redis.exceptions.ConnectionError:
                                pass
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
                            try:
                                # Since we changed the sessions data on db, invalidate Redis cache
                                redis_conn = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, charset=REDIS_CHARSET, decode_responses=True)
                                redis_conn.delete('sessions_csv')
                            except redis.exceptions.ConnectionError:
                                pass
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
            if platform in stats:
                stats[platform]['frequency'] = stats[platform]['frequency']/frequency_objs if frequency_objs != 0 else 0
            else:
                stats[platform] = {'frequency' : 0.0, \
                                   'total_score' : 0, \
                                   'time_spent' : "0:00:00", \
                                   'avg_score' : 0.00, \
                                   'avg_time_spent' : "0:00:00", \
                                   'total_records_avail' : 0}

        return stats


class TermsPerformance(Resource):
    @jwt_required
    def get(self):
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401
        print(user_id)
        user_parser = reqparse.RequestParser()
        user_parser.add_argument('userID',
                                  type=str,
                                  required=False,
                                  )
        user_parser.add_argument('groupID',
                                  type=str,
                                  required=False,
                                  )
        user_parser.add_argument('moduleID',
                                  type=str,
                                  required=False,
                                  )
        user_parser.add_argument('includeOwnStats',
                                  type=bool,
                                  required=False,
                                  )
        data = user_parser.parse_args()

        if permission != 'su':
            get_associated_groups = f"""
                                    SELECT group_user.groupID FROM group_user WHERE userID = {user_id}
                                    """
        else:
            get_associated_groups = f"""
                                     SELECT group_user.groupID FROM group_user
                                     """
        if not data['groupID']:
            groupID_list = []
            groupID_from_db = get_from_db(get_associated_groups)
            for groupID in groupID_from_db:
                groupID_list.append(groupID[0])
            groupID_list = convertListToSQL(groupID_list)
        else:
            if permission != 'su':
                # If PF or ST accessing this API, then they can only retrieve stats for groups they are associated with
                check_if_in_group = f"SELECT 1 FROM group_user WHERE userID = {user_id} AND groupID = {data['groupID']}"
                is_in_group = get_from_db(check_if_in_group)
                if not is_in_group or not is_in_group[0]:
                    return {"Message" : "Not associated with that group"}, 400
            groupID_list = "= " + str(data['groupID'])

        get_associated_group_users = f"""
                                      SELECT group_user.userID FROM group_user WHERE group_user.groupID {groupID_list}
                                      """
        # If student user, they can only retrieve their own records
        if permission != 'su' and permission != 'pf':
            group_userID_list = "= " + str(user_id)
        
        # If professor or superadmin
        else:
            if data['userID']:
                # PF and SU can access other students' records
                group_userID_list = "= " + str(data['userID'])
            else:
                group_userID_from_db = get_from_db(get_associated_group_users)
                group_userID_list = []
                for userID in group_userID_from_db:
                    # Since the current user is the professor/SU, ignore any of his/her/their data
                    if data['includeOwnStats']:
                        group_userID_list.append(userID[0])
                    else:
                        if userID[0] != user_id:
                            group_userID_list.append(userID[0])
                group_userID_list = convertListToSQL(group_userID_list)


        get_associated_modules = f"""
                                  SELECT group_module.moduleID FROM group_module WHERE group_module.groupID {groupID_list}
                                  """
        if data['moduleID']:
            moduleID_list = "= " + str(data['moduleID'])
        else:
            moduleID_list = []
            moduleID_from_db = get_from_db(get_associated_modules)
            for moduleID in moduleID_from_db:
                moduleID_list.append(moduleID[0])
            moduleID_list = convertListToSQL(moduleID_list)

        # # If want to include stats for deleted information
        # query = f"""
        #          SELECT logged_answer.*, module.moduleID, module.name, deleted_module.moduleID, deleted_module.name from logged_answer
		# 		 INNER JOIN session ON session.sessionID = logged_answer.sessionID
        #          LEFT JOIN module ON session.moduleID = module.moduleID
        #          LEFT JOIN deleted_module on session.moduleID = deleted_module.moduleID
        #          WHERE logged_answer.sessionID IN 
        #          (SELECT sessionID from `session` WHERE moduleID {moduleID_list} AND userID {group_userID_list})
        #          """

        query = f"""
                 SELECT logged_answer.*, module.moduleID, module.name from logged_answer
				 INNER JOIN session ON session.sessionID = logged_answer.sessionID
                 INNER JOIN module ON session.moduleID = module.moduleID
                 WHERE logged_answer.sessionID IN 
                 (SELECT sessionID from `session` WHERE moduleID {moduleID_list} AND userID {group_userID_list})
                 """
        print(query)
        loggedAnswers = get_from_db(query)

        termCorrectness = {}
        for loggedAns in loggedAnswers:
            if loggedAns[0]:
                if loggedAns[2] in termCorrectness:
                    termCorrectness[loggedAns[2]]['count'] = termCorrectness[loggedAns[2]]['count'] + 1
                    termCorrectness[loggedAns[2]]['correctness'] = termCorrectness[loggedAns[2]]['correctness'] + loggedAns[4]
                    if loggedAns[9] not in termCorrectness[loggedAns[2]]['modules']:
                        termCorrectness[loggedAns[2]]['modules'][loggedAns[9]] = loggedAns[10]
                else:
                    termCorrectness[loggedAns[2]] = {
                                                    'correctness' : loggedAns[4], 
                                                    'count' : 1,
                                                    'modules' : {loggedAns[9] : loggedAns[10]}}
        
        for termID in termCorrectness:
            termCorrectness[termID]['correctness'] = termCorrectness[termID]['correctness'] / termCorrectness[termID]['count']
            get_term = f"""SELECT term.termID, term.front, term.back, term.type, term.gender, term.language 
                        FROM term WHERE termID = {termID}"""
            term_info = get_from_db(get_term)
            if not term_info and not term_info[0]:
                # # If want to include deleted terms information
                # get_term = f"SELECT * from deleted_term WHERE termID = {termID}"
                # term_info = get_from_db(get_term)
                # if not term_info and not term_info[0]:
                #     continue
                continue
            
            termCorrectness[termID]['front'] = term_info[0][1]
            termCorrectness[termID]['back'] = term_info[0][2]
            termCorrectness[termID]['type'] = term_info[0][3]
            termCorrectness[termID]['gender'] = term_info[0][4]
            termCorrectness[termID]['language'] = term_info[0][5]

        if termCorrectness:
            terms_stats = {k : v for k, v in sorted(termCorrectness.items(), key = lambda item : item[1]['correctness'])}
            return terms_stats, 200
        else:
            return {"Message" : "No records found"}, 200


def convertListToSQL(list):
    if len(list) <= 0:
        return "= ''"
    if len(list) < 2:
        return "= " + str(list[0])
    else:
        return "IN " + str(tuple(list))


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
        
        lang_count = {key: val for key, val in sorted(lang_count.items(), key=lambda item: item[1], reverse=True)}

        return lang_count, 200