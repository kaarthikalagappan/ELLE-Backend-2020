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


class GameLog(Resource):
    @jwt_required
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('userID',
                            required = False,
                            type = str)
        parser.add_argument('moduleID',
                            required = True,
                            type = str)
        parser.add_argument('correct',
                            required = True,
                            type = str)
        parser.add_argument('incorrect',
                            required = True,
                            type = str)
        parser.add_argument('platform',
                            required = True,
                            type = str)
        parser.add_argument('time',
                            required = False,
                            type = str)
        parser.add_argument('gameName',
                            required = False,
                            type = str)
        data = parser.parse_args()

        user_id = get_jwt_identity()
        permission, valid_user = getUser(user_id)

        if not valid_user:
            return errorMessage("Not a valid user!"), 401

        data['platform'] = data['platform'].lower()

        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            if(data['platform'] == "mb" or data['platform'] == "pc"):
                data['gameName'] = data['platform']
            elif not data['gameName'] or data['gameName'] == '':
                raise Exception("If game is in VR platform, then need to specify gamename when creating game_log")

            query = f"INSERT INTO `game_log` (`userID`, `moduleID`, `correct`, `incorrect`, `platform`, `time`) \
                VALUES ({data['userID']},{data['moduleID']},{data['correct']},{data['incorrect']},'{data['platform'][:3]}','{data['time']}')"
            post_to_db(query, None, conn, cursor)
            raise ReturnSuccess("Successfully created a game_log record", 206)
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
        parser.add_argument('userID',
                            required = False,
                            type = str,
                            help = "ID of user optional search option")
        parser.add_argument('moduleID',
                            required = False,
                            type = str,
                            help = "ID of module option search option")
        data = parser.parse_args()

        user_id = get_jwt_identity()
        permission, valid_user = getUser(user_id)

        if not valid_user:
            return errorMessage("Not a valid user accessing this information!"), 401

        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            #no parameters passed, search for all game_logs
            if not data['userID'] and not data['moduleID']:
                query = f"SELECT * from `game_log`"
                results = get_from_db(query, None, conn, cursor)
                records = []
                if results and results[0]:
                    for game_log in results:
                        records.append(convertGameLogsToJSON(game_log))
                if records:
                    raise ReturnSuccess(records, 200)
                else:
                    raise ReturnSuccess("No game_logs found", 204)
            #userID has no value in JSON, search using user's jwt token as parameter
            elif len(data['userID']) == 0 and not data['moduleID']:
                query = f"SELECT * from `game_log` WHERE `userID` = {user_id}"
                results = get_from_db(query, None, conn, cursor)
                records = []
                if results and results[0]:
                    for game_log in results:
                        records.append(convertGameLogsToJSON(game_log))
                if records:
                    raise ReturnSuccess(records, 200)
                else:
                    raise ReturnSuccess("No game_logs found for the chosen user", 205)
            #only userID passed in, search only for given userID
            elif data['userID'] and not data['moduleID']:
                query = f"SELECT * from `game_log` WHERE `userID` = {data['userID']}"
                results = get_from_db(query, None, conn, cursor)
                records = []
                if results and results[0]:
                    for game_log in results:
                        records.append(convertGameLogsToJSON(game_log))
                if records:
                    raise ReturnSuccess(records, 200)
                else:
                    raise ReturnSuccess("No game_logs found for the chosen user", 206)
            #only moduleID passed in, search only for given moduleID
            elif data['moduleID'] and not data['userID']:
                query = f"SELECT * from `game_log` WHERE `moduleID` = {data['moduleID']}"
                results = get_from_db(query, None, conn, cursor)
                records = []
                if results and results[0]:
                    for game_log in results:
                        records.append(convertGameLogsToJSON(game_log))
                if records:
                    raise ReturnSuccess(records, 200)
                else:
                    raise ReturnSuccess("No game_logs found for the chosen module", 207)

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



def convertGameLogsToJSON(game_log):
    if len(game_log) < 6:
        return errorMessage("passed wrong amount of values to convertSessionsToJSON, it needs all elements in session table")
    result = {
        'logID' : game_log[0],
        'userID' : game_log[1],
        'moduleID' : game_log[2],
        'correct' : game_log[3],
        'incorrect' : game_log[4],
        'platform' : game_log[5],
        'time' : game_log[6].__str__(),
        'gameName' : game_log[7]
    }
    return result
