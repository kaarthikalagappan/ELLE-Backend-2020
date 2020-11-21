from flask import request
from flask_restful import Resource, reqparse
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from flaskext.mysql import MySQL
from db import mysql
from db_utils import *
from utils import *
from exceptions_util import *
import os

class GameLog(Resource):
    @jwt_required
    def post(self):
        data = {}
        data['userID'] = getParameter("userID", str, False, "")
        data['moduleID'] = getParameter("moduleID", str, True, "")
        data['correct'] = getParameter("correct", str, True, "")
        data['incorrect'] = getParameter("incorrect", str, True, "")
        data['platform'] = getParameter("platform", str, True, "")
        data['time'] = getParameter("time", str, False, "")
        data['gameName'] = getParameter("gameName", str, False, "")
        
        # Validate the user
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return errorMessage("Invalid user"), 401

        data['platform'] = data['platform'].lower()

        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            if(data['platform'] == "mb" or data['platform'] == "pc"):
                data['gameName'] = data['platform']
            elif not data['gameName'] or data['gameName'] == '':
                raise CustomException("If game is in VR platform, then need to specify gamename when creating game_log", 400)

            query = f"INSERT INTO `game_log` (`userID`, `moduleID`, `correct`, `incorrect`, `platform`, `time`) \
                VALUES ({data['userID']},{data['moduleID']},{data['correct']},{data['incorrect']},'{data['platform'][:3]}','{data['time']}')"
            post_to_db(query, None, conn, cursor)
            raise ReturnSuccess("Successfully created a game_log record", 206)
        except CustomException as error:
            conn.rollback()
            return error.msg, error.returnCode
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
        data = {}
        data['userID'] = getParameter("userID", str, False, "")
        data['moduleID'] = getParameter("moduleID", str, False, "")

        # Validate the user
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return errorMessage("Invalid user"), 401

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
        except CustomException as error:
            conn.rollback()
            return error.msg, error.returnCode
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