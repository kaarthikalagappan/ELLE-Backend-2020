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

class LoggedAnswer(Resource):
    @jwt_required
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('questionID',
                            required = False,
                            type = str)
        parser.add_argument('termID',
                            required = True,
                            type = str)
        parser.add_argument('sessionID',
                            required = True,
                            type = str)
        parser.add_argument('correct',
                            required = True,
                            type = str)
        data = parser.parse_args()

        user_id = get_jwt_identity()
        permission, valid_user = getUser(user_id)

        if not valid_user:
            return errorMessage("Not a valid user!"), 401
        
        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            if data['correct'] == '' or data['correct'].lower() == 'false':
                data['correct'] = '0'
            elif data['correct'].lower() == 'true':
                data['correct'] = '1'

            query = f"INSERT INTO `logged_answer` (`questionID`, `termID`, `sessionID`, `correct`) \
                VALUES ({data['questionID']},{data['termID']},{data['sessionID']},{data['correct']})"
            post_to_db(query, None, conn, cursor)
            raise ReturnSuccess("Successfully created a logged_answer record", 205)
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
        parser.add_argument('moduleID',
                            required = False,
                            type = str)
        parser.add_argument('userID',
                            required = False,
                            type = str)
        data = parser.parse_args()

        user_id = get_jwt_identity()
        permission, valid_user = getUser(user_id)

        if not valid_user:
            return errorMessage("Not a valid user!"), 401
        
        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            if not data['moduleID'] or data['moduleID'] == "":
                moduleExp = "REGEXP '.*'"
            else:
                moduleExp = " = " + str(data['moduleID'])
            
            #TODO: STUDENT USERS CAN ONLY PULL THEIR OWN RECORDS, ONLY ADMINS AND SUPER USERS
            # CAN REQUEST OTHER STUDENTS' OR ALL SESSIONS
            if (not data['userID'] or data['userID'] == "") and permission == 'ad':
                userExp = "REGEXP '.*'"
            elif permission == 'ad':
                userExp = " = " + str(data['userID'])
            else:
                userExp = " = " + str(user_id)
            
            getQuestionsQuery = f"""SELECT DISTINCT sessionID FROM session 
                                    WHERE moduleID {moduleExp} AND
                                    userID {userExp}"""
            sessionIDList = get_from_db(getQuestionsQuery, None, conn, cursor)

            getLoggedAnswerQuery = "SELECT * FROM logged_answer WHERE sessionID = %s"
            loggedAnswers = []

            for sessionID in sessionIDList:
                db_results = get_from_db(getLoggedAnswerQuery, sessionID, conn, cursor)
                for result in db_results:
                    la_record = {
                        'logID' : result[0],
                        'questionID' : result[1],
                        'termID' : result[2],
                        'sessionID' : result[3],
                        'correct' : result[4]
                    }
                    loggedAnswers.append(la_record)

            if loggedAnswers:
                raise ReturnSuccess(loggedAnswers, 200)
            else:
                raise ReturnSuccess("No associated logged answers found for that module and/or user", 200)
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