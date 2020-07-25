from flask import request
from flask_restful import Resource, reqparse
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from flaskext.mysql import MySQL
from db import mysql
from db_utils import *
from utils import *
import os


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
        parser.add_argument('startTime',
                            required = True,
                            help = "Need the start time of the session",
                            type = str)
        parser.add_argument('platform',
                            required = True,
                            help = "Need to specify what platform this session was played on (pc, mob, or vr)",
                            type = str)
        data = parser.parse_args()

        if 'sessionDate' not in data or not data['sessionDate']:
            data['sessionDate'] = time.strftime("%D")

        user_id = get_jwt_identity()
        permission, valid_user = getUser(user_id)

        if not valid_user:
            return errorMessage("Not a valid user!"), 401
        
        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            query = "SELECT MAX(sessionID) FROM session"
            result = get_from_db(query, None, conn, cursor)
            sessionID = check_max_id(result)

            query = f"INSERT INTO `session` (`sessionID`, `userID`, `moduleID`, `sessionDate`, `startTime`, `platform`) \
                VALUES ({sessionID}, {user_id},{data['moduleID']},'{data['sessionDate']}','{data['startTime']}', \
                '{data['platform'][:3]}')"
            post_to_db(query, None, conn, cursor)
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
    def put(self):
        parser = reqparse.RequestParser()
        parser.add_argument('sessionID',
                            required = True,
                            type = str,
                            help = "ID of the session to end is required")
        parser.add_argument('endTime',
                            required=True,
                            type=str,
                            help="session's end time required, in HH:MM format (24 Hour format)")
        parser.add_argument('playerScore',
                            required = True,
                            help = "Need to specify what's the score of the user in this session",
                            type = str)
        data = parser.parse_args()

        user_id = get_jwt_identity()
        permission, valid_user = getUser(user_id)
        if not valid_user:
            return errorMessage("Not a valid user!"), 401
        
        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            query = f"SELECT * from session WHERE sessionID = {data['sessionID']}"
            result = get_from_db(query, None, conn, cursor)
            if not result or not result[0]:
                raise SessionException("Session not found for provided ID", 400)
            elif result[0][6]:
                    raise SessionException("Wrong session ID provided", 400)

            query = f"UPDATE `session` SET `endTime` = '{data['endTime']}', `playerScore` = '{data['playerScore']}' WHERE `session`.`sessionID` = {data['sessionID']}"
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

    @jwt_required
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('sessionID',
                            required = True,
                            type = str,
                            help = "ID of session needed to retrieve is required")
        
        data = parser.parse_args()

        user_id = get_jwt_identity()
        permission, valid_user = getUser(user_id)
        if not valid_user:
            return errorMessage("Not a valid user accessing this information!"), 401

        try:
            conn = mysql.connect()
            cursor = conn.cursor()
            sessionData = {"session" : [], "logged_answers" : []}

            query = f"SELECT * from `session` WHERE `sessionID` = {data['sessionID']}"
            results = get_from_db(query, None, conn, cursor)
            if results and results[0]:
                sessionData['session'].append(convertSessionsToJSON(results[0]))
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
                        'correct' : log[4]
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
        

class SearchSessions(Resource):
    @jwt_required
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('userID',
                            required = False,
                            type = str,
                            help = "userID of whose session logs are needed")
        parser.add_argument('moduleID',
                            required = False,
                            type = str,
                            help = "moduleID of whose session logs are needed is required")
        data = parser.parse_args()

        user_id = get_jwt_identity()
        permission, valid_user = getUser(user_id)
        if not valid_user:
            return errorMessage("Not a valid user accessing this information!"), 401

        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            #only moduleID is passed, in so retrieve all sessions that match the given moduleID
            if data['moduleID'] and not data['userID']:
                query = f"SELECT * from `session` WHERE `moduleID` = {data['moduleID']}"
                results = get_from_db(query, None, conn, cursor)
                records = []
                if results and results[0]:
                    for session in results:
                        records.append(convertSessionsToJSON(session))
                if records:
                    raise ReturnSuccess(records, 200)
                else:
                    raise ReturnSuccess("No sessions found for the chosen module", 204)
            #both userID and moduleID was passed in, so retrieve session logs that match both of them
            elif data['moduleID'] and data['userID']:
                query = f"SELECT * from `session` WHERE `userID` = {data['userID']} AND `moduleID` = {data['moduleID']}"
                results = get_from_db(query, None, conn, cursor)
                records = []
                if results and results[0]:
                    for session in results:
                        records.append(convertSessionsToJSON(session))
                if records:
                    raise ReturnSuccess(records, 200)
                else:
                    raise ReturnSuccess("No sessions found for chosen user who has played with the chosen module", 204)
            #only userID was passed in or the current user is getting their own session logs
            else:
                if not data['userID']:
                    data['userID'] = user_id
                query = f"SELECT * from `session` WHERE `userID` = {data['userID']}"
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


def convertSessionsToJSON(session):
    if len(session) < 8:
        return errorMessage("passed wrong amount of values to convertSessionsToJSON, it needs all elements in session table")
    result = {
        'sessionID' : session[0],
        'userID' : session[1],
        'moduleID' : session[2],
        'sessionDate' : session[3],
        'playerScore' : session[4],
        'startTime' : session[5],
        'endTime' : session[6],
        'platform' : session[7]
    }
    return result
