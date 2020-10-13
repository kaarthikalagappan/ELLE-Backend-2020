from flask import request, Response
from flask_restful import Resource, reqparse
from flask_jwt_extended import jwt_required, get_jwt_identity
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
                            help = "userID of whose session logs")
        parser.add_argument('moduleID',
                            required = False,
                            type = str,
                            help = "moduleID of whose session logs")
        parser.add_argument('platform',
                            required = False,
                            type = str,
                            help = "moduleID of whose session logs")
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
                    WHERE session.moduleID {data['moduleID']} 
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
        
        csv = 'Session ID, User ID, User Name, Module ID, Module Name, Session Date, Player Score, Start Time, End Time, Time Spent, Platform, Mode\n'
        query = """
                SELECT session.*, user.username, module.name FROM session 
                INNER JOIN user ON user.userID = session.userID
                INNER JOIN module on module.moduleID = session.moduleID
                """
        results = get_from_db(query)
        if results and results[0]:
            for record in results:
                if record[6]:
                    time_spent = str(record[6] - record[5])[:-3]
                else:
                    log_time_query = f"SELECT logged_answer.log_time FROM `logged_answer` WHERE sessionID={record[0]} ORDER BY logID DESC LIMIT 1"
                    last_log_time = get_from_db(log_time_query)
                    if last_log_time and last_log_time[0] and last_log_time[0][0] != None:
                        time_spent = str(last_log_time[0][0] - record[5])[:-3]
                        record[6] = str(last_log_time[0][0])
                        if record[3] != time.strftime("%Y-%m-%d"):
                            query_update_time = f"UPDATE session SET session.endTime = '{last_log_time[0][0]}' WHERE session.sessionID = {record[0]}"
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
                platform = "Mobile" if record[7] == 'mb' else "PC" if record[7] == 'pc' else "Virtual Reality"
                csv = csv + f"""{record[0]}, {record[1]}, {record[9]}, {record[2]}, {record[10]}, {record[3]}, {record[4]}, {str(record[5])[:-3]}, {str(record[6])[:-3] if record[6] else None}, {time_spent}, {platform}, {record[8]}\n"""
        return Response(
            csv,
            mimetype="text/csv",
            headers={"Content-disposition":
            "attachment; filename=Sessions.csv"})


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
