from flask import request, Response
from flask_restful import Resource, reqparse
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from flaskext.mysql import MySQL
from db import mysql
from db_utils import *
from utils import *
import os
import datetime


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
    # Create a logged_answer that stores if the user got the question correct
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
        parser.add_argument('mode',
                            required = False,
                            type = str)
        data = parser.parse_args()

        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401
        
        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            if data['correct'] == '' or data['correct'].lower() == 'false':
                data['correct'] = '0'
            elif data['correct'].lower() == 'true':
                data['correct'] = '1'

            formatted_time = datetime.datetime.now().time().strftime('%H:%M')

            if data['mode']:
                query = f"INSERT INTO `logged_answer` (`questionID`, `termID`, `sessionID`, `correct`, `mode`, `log_time`) \
                    VALUES ({data['questionID']},{data['termID']},{data['sessionID']},{data['correct']},'{data['mode']}','{formatted_time}')"
                post_to_db(query, None, conn, cursor)
            else:
                query = f"INSERT INTO `logged_answer` (`questionID`, `termID`, `sessionID`, `correct`, `log_time`) \
                    VALUES ({data['questionID']},{data['termID']},{data['sessionID']},{data['correct']}, '{formatted_time}')"
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

    # Pull a user's logged_answers based on a given module
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

        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401
        
        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            if not data['moduleID'] or data['moduleID'] == "":
                moduleExp = "REGEXP '.*'"
            else:
                moduleExp = " = " + str(data['moduleID'])
            
            #TODO: STUDENT USERS CAN ONLY PULL THEIR OWN RECORDS, ONLY ADMINS AND SUPER USERS
            # CAN REQUEST OTHER STUDENTS' OR ALL SESSIONS
            if (not data['userID'] or data['userID'] == "") and (permission == 'pf' or permission == 'su'):
                userExp = "REGEXP '.*'"
            elif (permission == 'pf' or permission == 'su'):
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
                        'correct' : result[4],
                        'mode' : result[5]
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

class GetLoggedAnswerCSV(Resource):
    # @jwt_required
    def get(self):
        # permission, user_id = validate_permissions()
        # if not permission or not user_id or permission != 'su':
        #     return "Invalid user", 401
        
        csv = 'Log ID, User ID, Username, Module ID, Module Name, Question ID, Term ID, Session ID, Correct, Timestamp, Mode\n'
        query = """
                SELECT logged_answer.*, session.userID, user.username, module.moduleID, module.name FROM logged_answer 
                INNER JOIN session ON session.sessionID = logged_answer.sessionID
                INNER JOIN user ON user.userID = session.userID
                INNER JOIN module on module.moduleID = session.moduleID
                """
        results = get_from_db(query)
        if results and results[0]:
            for record in results:
                csv = csv + f"""{record[0]}, {record[7]}, {record[8]}, {record[9]}, {record[10]}, {record[1]}, {record[2]}, {record[3]}, {record[4]}, {str(record[6])}, {record[5]}\n"""
        return Response(
            csv,
            mimetype="text/csv",
            headers={"Content-disposition":
            "attachment; filename=Logged_Answers.csv"})