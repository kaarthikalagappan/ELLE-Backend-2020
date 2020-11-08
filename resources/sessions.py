from flask import request, Response
from flask_restful import Resource, reqparse
from flask_jwt_extended import jwt_required, get_jwt_identity
import redis
from config import REDIS_CHARSET, REDIS_HOST, REDIS_PORT
from werkzeug.utils import secure_filename
from flaskext.mysql import MySQL
from db import mysql
from db_utils import *
from utils import *
import os
import dateutil.parser as dateutil
import datetime
import time


class CustomException(Exception):
    pass


class ReturnSuccess(Exception):
    def __init__(self, msg, returnCode):
        # Message is stored formatted in msg and response code stored in returnCode
        if isinstance(msg, str):
            self.msg = returnMessage(msg)
        else:
            self.msg = msg
        self.returnCode = returnCode


class SessionException(Exception):
    def __init__(self, msg, returnCode):
        # Error message is stored formatted in msg and response code stored in returnCode
        if isinstance(msg, str):
            self.msg = errorMessage(msg)
        else:
            self.msg = msg
        self.returnCode = returnCode


class Session(Resource):
    @jwt_required
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('moduleID',
                            required = True,
                            type = str,
                            help = "moduleID of module used in session required")
        parser.add_argument('sessionDate',
                            required = False,
                            type = str)
        parser.add_argument('platform',
                            required = True,
                            help = "Need to specify what platform this session was played on (pc, mob, or vr)",
                            type = str)
        parser.add_argument('mode',
                            required = False,
                            type = str)
        data = parser.parse_args()

        if 'sessionDate' not in data or not data['sessionDate']:
            data['sessionDate'] = time.strftime("%m/%d/%Y")

        # Validate the user
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401
        
        try:
            print(data)
            conn = mysql.connect()
            cursor = conn.cursor()

            formatted_date = dateutil.parse(data['sessionDate']).strftime('%Y-%m-%d')
            formatted_time = datetime.datetime.now().time().strftime('%H:%M')

            if data['mode']:
                query = f"INSERT INTO `session` (`userID`, `moduleID`, `sessionDate`, `startTime`, `mode`, `platform`) \
                    VALUES ({user_id},{data['moduleID']},'{formatted_date}','{formatted_time}','{data['mode']}', \
                    '{data['platform'][:3]}')"
                post_to_db(query, None, conn, cursor)
                sessionID = cursor.lastrowid
            else:
                query = f"INSERT INTO `session` (`userID`, `moduleID`, `sessionDate`, `startTime`, `platform`) \
                    VALUES ({user_id},{data['moduleID']},'{formatted_date}','{formatted_time}', \
                    '{data['platform'][:3]}')"
                post_to_db(query, None, conn, cursor)
                sessionID = cursor.lastrowid
            raise ReturnSuccess({'sessionID' : sessionID}, 201)
        except ReturnSuccess as success:
            conn.commit()
            return success.msg, success.returnCode
        except Exception as error:
            conn.rollback()
            return errorMessage(str(error)), 500
        finally:
            if(conn.open):
                cursor.close()
                conn.close()

    
    @jwt_required
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('sessionID',
                            required = True,
                            type = str,
                            help = "ID of session needed to retrieve is required")
        
        data = parser.parse_args()

        # Validate the user
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401

        try:
            conn = mysql.connect()
            cursor = conn.cursor()
            sessionData = {"session" : [], "logged_answers" : []}

            query = f"SELECT session.*, module.name from `session` INNER JOIN module ON module.moduleID = session.moduleID WHERE \
                      session.sessionID = {data['sessionID']}"
            results = get_from_db(query, None, conn, cursor)
            if results and results[0]:
                sessionData['session'].append(convertSessionsToJSON(results[0]))
                if permission == 'st' and sessionData['session']['userID'] != user_id:
                    raise SessionException("Unauthorized to access this session", 400)
            else:
                raise SessionException("No sessions found for the given ID", 400)

            query = f"SELECT * from logged_answer WHERE `sessionID` = {data['sessionID']}"
            results = get_from_db(query, None, conn, cursor)
            if results and results[0]:
                for log in results:
                    record = {
                        'logID' : log[0],
                        'questionID' : log[1],
                        'termID' : log[2],
                        'sessionID' : log[3],
                        'correct' : log[4],
                        'mode' : log[5]
                    }
                    sessionData['logged_answers'].append(record)
            raise ReturnSuccess(sessionData, 200)
        except ReturnSuccess as success:
            conn.commit()
            return success.msg, success.returnCode
        except SessionException as error:
            conn.rollback()
            return error.msg, error.returnCode
        except Exception as error:
            conn.rollback()
            return errorMessage(str(error)), 500
        finally:
            if(conn.open):
                cursor.close()
                conn.close()

class End_Session(Resource):
    @jwt_required
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('sessionID',
                            required = True,
                            type = str,
                            help = "ID of the session to end is required")
        parser.add_argument('playerScore',
                            required = True,
                            help = "Need to specify what's the score of the user in this session",
                            type = str)
        data = parser.parse_args()

        # Validate the user
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401
        
        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            formatted_time = datetime.datetime.now().time().strftime('%H:%M')

            query = f"SELECT * from session WHERE sessionID = {data['sessionID']}"
            result = get_from_db(query, None, conn, cursor)
            if not result or not result[0]:
                raise SessionException("Session not found for provided ID", 400)
            elif result[0][6]:
                    raise SessionException("Wrong session ID provided", 400)

            query = f"UPDATE `session` SET `endTime` = '{formatted_time}', `playerScore` = '{data['playerScore']}' WHERE `session`.`sessionID` = {data['sessionID']}"
            post_to_db(query, None, conn, cursor)
            raise ReturnSuccess("Session successfully ended", 200)
        except ReturnSuccess as success:
            conn.commit()
            return success.msg, success.returnCode
        except SessionException as error:
            conn.rollback()
            return error.msg, error.returnCode
        except Exception as error:
            conn.rollback()
            return errorMessage(str(error)), 500
        finally:
            if(conn.open):
                cursor.close()
                conn.close()
        

class SearchSessions(Resource):
    @jwt_required
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('userID',
                            required = False,
                            type = str,
                            help = "userID of whose session logs needed to retrieve")
        parser.add_argument('userName',
                            required = False,
                            type = str,
                            help = "userName of whose session logs needed to retrieve")
        parser.add_argument('moduleID',
                            required = False,
                            type = str,
                            help = "moduleID of whose session logs needed to retrieve")
        parser.add_argument('platform',
                            required = False,
                            type = str,
                            help = "moduleID of whose session logs needed to retrieve")
        parser.add_argument('sessionDate',
                            required = False,
                            type = str,
                            help = "date to retrieve sessions from (YYYY-MM-DD format)")
        data = parser.parse_args()

        # Validate the user
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401

        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            # If any data is not provided, change it to a regular expression
            # that selects everything in order to ignore that as a condition
            # "REGEXP '.*'" selects everything
            if not data['moduleID'] or data['moduleID'] == '':
                data['moduleID'] = "REGEXP '.*'"
            else:
                data['moduleID'] = "= '" + str(data['moduleID']) + "'"

            if not data['userName'] or data['userName'] == '':
                data['userName'] = "REGEXP '.*'"
            else:
                data['userName'] = "= '" + str(data['userName']) + "'"
            
            # Students (and TAs) cannot pull another user's session data
            if permission != 'su' and permission != 'pf':
                data['userID'] = "= '" + str(user_id) + "'"
            elif data['userID'] and data['userID'] != '':
                data['userID'] = "= '" + str(data['userID']) + "'"
            else:
                data['userID'] = "REGEXP '.*'"

            if not data['platform'] or data['platform'] == '':
                data['platform'] = "REGEXP '.*'"
            else:
                data['platform'] = "= '" + str(data['platform']) + "'"

            if not data['sessionDate'] or data['sessionDate'] == '':
                data['sessionDate'] = "REGEXP '.*'"
            else:
                data['sessionDate'] = "= '" + str(data['sessionDate']) + "'"

            query = f"""SELECT session.*, module.name from `session`
                    INNER JOIN module on module.moduleID = session.moduleID
                    INNER JOIN user on user.userID = session.userID
                    WHERE session.moduleID {data['moduleID']}
                    AND user.userName {data['userName']}
                    AND session.userID {data['userID']} 
                    AND session.platform {data['platform']}
                    AND session.sessionDate {data['sessionDate']}"""
            # print(query)
            results = get_from_db(query, None, conn, cursor)
            records = []
            if results and results[0]:
                for session in results:
                    records.append(convertSessionsToJSON(session))
            if records:
                raise ReturnSuccess(records, 200)
            else:
                raise ReturnSuccess("No sessions found for the user", 204)

        except ReturnSuccess as success:
            conn.commit()
            return success.msg, success.returnCode
        except Exception as error:
            conn.rollback()
            return errorMessage(str(error)), 500
        finally:
            if(conn.open):
                cursor.close()
                conn.close()

class GetAllSessions(Resource):
    @jwt_required
    def get(self):
        # Validate the user
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401
        
        if permission != 'su':
            return "Unauthorized user", 401

        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            query = f"SELECT session.*, module.name from `session` INNER JOIN module ON module.moduleID = session.moduleID"
            results = get_from_db(query, None, conn, cursor)
            records = []
            if results and results[0]:
                for session in results:
                    records.append(convertSessionsToJSON(session))
            if records:
                raise ReturnSuccess(records, 200)
            else:
                raise ReturnSuccess("No sessions found for the chosen module", 210)
        except ReturnSuccess as success:
            conn.commit()
            return success.msg, success.returnCode
        except Exception as error:
            conn.rollback()
            return errorMessage(str(error)), 500
        finally:
            if(conn.open):
                cursor.close()
                conn.close()


class GetSessionCSV(Resource):
    # @jwt_required
    def get(self):
        # permission, user_id = validate_permissions()
        # if not permission or not user_id or permission != 'su':
        #     return "Invalid user", 401
        try:
            redis_conn = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, charset=REDIS_CHARSET, decode_responses=True)
            redis_sessions_chksum = redis_conn.get('sessions_checksum')
            redis_sesssions_csv = redis_conn.get('sessions_csv')
            redis_lastseen_sessionID = redis_conn.get('lastseen_sessionID')
            redis_session_count = redis_conn.get('session_count')
        except redis.exceptions.ConnectionError:
            redis_conn = None
            redis_sessions_chksum = None
            redis_sesssions_csv = None
            redis_lastseen_sessionID = None
            redis_session_count = None

        get_max_sessionID = "SELECT MAX(session.sessionID) FROM session"
        get_sessions_chksum = "CHECKSUM TABLE session"
        max_sessionID = get_from_db(get_max_sessionID)
        chksum_session = get_from_db(get_sessions_chksum)
        
        if max_sessionID and max_sessionID[0] and chksum_session and chksum_session[0]:
            max_sessionID = str(max_sessionID[0][0])
            chksum_session = str(chksum_session[0][1])
        else:
            return {"Error" : "Error retrieving data"}, 500

        if not redis_session_count or not redis_sessions_chksum or not redis_sesssions_csv or not redis_lastseen_sessionID or redis_sessions_chksum != chksum_session:
            if redis_session_count and redis_sessions_chksum and redis_sesssions_csv and redis_sessions_chksum != chksum_session:
                #if the checksum values don't match, then something changed
                get_sub_session_count = f"SELECT COUNT(session.sessionID) FROM session WHERE session.sessionID <= {redis_lastseen_sessionID}"
                get_all_session_count = f"SELECT COUNT(session.sessionID) FROM session"
                sub_session_count = get_from_db(get_sub_session_count)
                all_session_count = get_from_db(get_all_session_count)
                print(redis_lastseen_sessionID)
                if sub_session_count and sub_session_count[0] and all_session_count and all_session_count[0]:
                    sub_session_count = str(sub_session_count[0][0])
                    all_session_count = str(all_session_count[0][1])
                else:
                    return {"Error" : "Error retrieving data"}, 500
                
                if all_session_count != redis_session_count and sub_session_count == redis_session_count:
                    # The only time we want to just fetch newly added values is when the subcount is the same
                    # as cached (meaning nothing that we cached has changed).
                    csv = redis_sesssions_csv
                    query = f"""
                        SELECT session.*, user.username, module.name FROM session 
                        INNER JOIN user ON user.userID = session.userID
                        INNER JOIN module on module.moduleID = session.moduleID
                        WHERE session.sessionID > {redis_lastseen_sessionID}
                        """
                else:
                    csv = 'Session ID, User ID, User Name, Module ID, Module Name, Session Date, Player Score, Start Time, End Time, Time Spent, Platform, Mode\n'
                    query = """
                            SELECT session.*, user.username, module.name FROM session 
                            INNER JOIN user ON user.userID = session.userID
                            INNER JOIN module on module.moduleID = session.moduleID
                            """
            else:
                csv = 'Session ID, User ID, User Name, Module ID, Module Name, Session Date, Player Score, Start Time, End Time, Time Spent, Platform, Mode\n'
                query = """
                        SELECT session.*, user.username, module.name FROM session 
                        INNER JOIN user ON user.userID = session.userID
                        INNER JOIN module on module.moduleID = session.moduleID
                        """
            
            get_max_session_count = "SELECT COUNT(session.sessionID) FROM session"
            max_session_count = get_from_db(get_max_session_count)
            if max_session_count and max_session_count[0]:
                max_session_count = str(max_session_count[0][0])
            else:
                return {"Error" : "Error retrieving data"}, 500
            
            results = get_from_db(query)
            if results and results[0]:
                for record in results:
                    if record[6]:
                        time_spent, _ = getTimeDiffFormatted(record[5], record[6])
                    else:
                        log_time_query = f"SELECT logged_answer.log_time FROM `logged_answer` WHERE sessionID={record[0]} ORDER BY logID DESC LIMIT 1"
                        last_log_time = get_from_db(log_time_query)
                        if last_log_time and last_log_time[0] and last_log_time[0][0] != None:
                            time_spent, _ = getTimeDiffFormatted(record[5], last_log_time[0][0])
                            record[6], _ = getTimeDiffFormatted(time_obj = last_log_time[0][0])
                            if record[3] != time.strftime("%Y-%m-%d"):
                                query_update_time = f"UPDATE session SET session.endTime = '{mysqlDateTime(last_log_time[0][0])}' WHERE session.sessionID = {record[0]}"
                                post_to_db(query_update_time)
                        else:
                            time_spent = None
                    if not record[4]:
                        get_logged_answer_score = f"""
                                                SELECT logged_answer.correct
                                                FROM logged_answer
                                                WHERE logged_answer.sessionID = {record[0]}
                                                """
                        answer_data = get_from_db(get_logged_answer_score)
                        if answer_data and answer_data[0]:
                            correct_answers = 0
                            for answer_record in answer_data:
                                correct_answers = correct_answers + answer_record[0]
                            update_score_query = f"""
                                                UPDATE session SET session.playerScore = {correct_answers}
                                                WHERE session.sessionID = {record[0]}
                                                """
                            post_to_db(update_score_query)
                            record[4] = correct_answers
                    platform = "Mobile" if record[7] == 'mb' else "PC" if record[7] == 'cp' else "Virtual Reality"
                    csv = csv + f"""{record[0]}, {record[1]}, {record[9]}, {record[2]}, {record[10]}, {record[3]}, {record[4]}, {getTimeDiffFormatted(time_obj = record[5])[0]}, {getTimeDiffFormatted(time_obj = record[6])[0] if record[6] else None}, {time_spent}, {platform}, {record[8]}\n"""
                if redis_conn:
                    redis_conn.set('sessions_csv', csv)
                    redis_conn.set('sessions_checksum', chksum_session)
                    redis_conn.set('lastseen_sessionID', max_sessionID)
                    redis_conn.set('session_count', max_session_count)
            return Response(
                csv,
                mimetype="text/csv",
                headers={"Content-disposition":
                "attachment; filename=Sessions.csv"})
        elif max_sessionID == redis_lastseen_sessionID and chksum_session == redis_sessions_chksum:
            return Response(
                redis_sesssions_csv,
                mimetype="text/csv",
                headers={"Content-disposition":
                "attachment; filename=Sessions.csv"})
        else:
            return {"Error" : "Something went wrong with computing CSV"}, 500


def getTimeDiffFormatted(time_1 = None, 
                        time_2 = None, 
                        str_format = "{days} day {hours}:{minutes}:{seconds}",
                        time_obj = None):
    # if time_1 and time_2 provided, it calculates the time different between two time objects formats them CSV-friendly
    # if time_obj is provided, formats that CSV-friendly
    if time_1 and time_2:
        time_delta = time_2 - time_1
    elif time_obj:
        time_delta = time_obj
    else:
        return None, None
    if time_delta.days != 0:  
        d = {"days": time_delta.days}
        d["hours"], rem = divmod(time_delta.seconds, 3600)
        d["minutes"], d["seconds"] = divmod(rem, 60)
        if d['days'] != 1 and d['days'] != -1:
            str_format = "{days} days {hours}:{minutes}:{seconds}"
        time_spent_str = str_format.format(**d)
    else:
        time_spent_str = str(time_delta)[:-3]
    return time_spent_str, time_delta


def mysqlDateTime(time_delta):
    # Takes in a timedelta object and formats it MySQL friendly
    str_format = "{hours}:{minutes}:{seconds}"
    if time_delta.days != 0:
        d = {}
        d["hours"], rem = divmod(time_delta.seconds, 3600)
        d['hours'] = d['hours'] + (time_delta.days*24)
        d["minutes"], d["seconds"] = divmod(rem, 60)
        time_spent_str = str_format.format(**d)
    else:
        time_spent_str = str(time_delta)[:-3]
    return time_spent_str


def convertSessionsToJSON(session):
    if len(session) < 10:
        return errorMessage("passed wrong amount of values to convertSessionsToJSON, it needs all elements in session table")
    result = {
        'sessionID' : session[0],
        'userID' : session[1],
        'moduleID' : session[2],
        'sessionDate' : str(session[3]),
        'playerScore' : session[4],
        'startTime' : str(session[5]),
        'endTime' : str(session[6]),
        'platform' : session[7],
        'mode' : session[8],
        'moduleName' : session[9]
    }
    return result
