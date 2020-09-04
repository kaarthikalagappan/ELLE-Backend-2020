from flask import request
from flask_restful import Resource, reqparse
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt_claims
from werkzeug.utils import secure_filename
from flaskext.mysql import MySQL
from db import mysql
from db_utils import *
from utils import *
import os
import string
import random

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

class GroupException(Exception):
    def __init__(self, msg, returnCode):
        # Error message is stored formatted in msg and response code stored in returnCode
        if isinstance(msg, str):
            self.msg = errorMessage(msg)
        else:
            self.msg = msg
        self.returnCode = returnCode

class Group(Resource):
    # Add a group to the database
    @jwt_required
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('groupName',
                            required = True,
                            type = str)
        data = parser.parse_args()

        user_id = get_jwt_identity()
        permission = get_jwt_claims()

        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            dupe_query = "SELECT `groupID` FROM `group` WHERE `groupName`=%s"
            dupe_results = get_from_db(dupe_query, data['groupName'], conn, cursor)

            if dupe_results:
                raise GroupException("groupName already exists.", 400)
            else:
                group_code = groupCode_generator()
                gc_query = "SELECT `groupID` FROM `group` WHERE `groupCode`=%s"
                gc_results = get_from_db(gc_query, group_code, conn, cursor)

                if gc_results:
                    raise GroupException("groupCode already exists", 400)

                query = "INSERT INTO `group` (`groupName`, `groupCode`) VALUES (%s, %s)"
                post_to_db(query, (data['groupName'], group_code), conn, cursor)

                g_query = "SELECT `groupID` FROM `group` WHERE `groupName`=%s"
                g_results = get_from_db(g_query, data['groupName'], conn, cursor)
                group_id = g_results[0][0]

                gu_query = "INSERT INTO `group_user` (`userID`, `groupID`, `accessLevel`) VALUES (%s, %s, %s)"
                post_to_db(gu_query, (user_id, group_id, 'pf'), conn, cursor)
                raise ReturnSuccess("Sucecssfully created the class.", 200)
        
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


class GroupRegister(Resource):  
    # Register for a group
    @jwt_required
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('groupCode',
                            required = True,
                            type = str)
        data = parser.parse_args()

        user_id = get_jwt_identity()
        permission = get_jwt_claims()

        if permission == 'su':
            return errorMessage("Superadmins cannot register for classes."), 402

        # REMINDER: check if superadmins can register for groups
        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            query = "SELECT `groupID` FROM `group` WHERE `groupCode` = %s"
            results = get_from_db(query, data['groupCode'], conn, cursor)

            # if groupCode exists in group table
            if results:
                group_id = results[0][0]    

                # check if the user has already registered for the gruop
                # otherwise continue with registering the user for the group
                dupe_query = "SELECT `userID` FROM `group_user` WHERE `groupID`=%s AND `userID`=%s"
                dupe_results = get_from_db(dupe_query, (group_id, user_id), conn, cursor)

                if dupe_results:
                    raise GroupException("User has already registered for the class.", 207)
                else:
                    gu_query = "INSERT INTO `group_user` (`userID`, `groupID`, `accessLevel`) VALUES (%s, %s, %s)"
                    post_to_db(gu_query, (user_id, group_id, permission), conn, cursor)
            else:
                raise GroupException("Invalid class code.", 206)

            raise ReturnSuccess("Successfully registered for group", 205)
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

class SearchUserGroups(Resource):
    # Search for the groups (classes) the user is in
    @jwt_required
    def get(self):
        parser = reqparse.RequestParser()
        data = parser.parse_args()

        user_id = get_jwt_identity()
        permission = get_jwt_claims()

        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            query = "SELECT `group`.*, `group_user`.accessLevel \
                     FROM `group` \
                     INNER JOIN `group_user` \
                     ON `group_user`.groupID = `group`.groupID \
                     WHERE `group_user`.userID=%s" 
            results = get_from_db(query, user_id, conn, cursor)
            
            groups = []
            if results and results[0]:
                for group in results:
                    groups.append(convertGroupsToJSON(group))
            
            raise ReturnSuccess(groups, 200)
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

class UsersInGroup(Resource):
    @jwt_required
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('groupID',
                            required = True,
                            type = int)
        data = parser.parse_args()

        user_id = get_jwt_identity()
        permission = get_jwt_claims()

        # should only superadmins/professors be able to search for users in a group?

        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            query = "SELECT `user`.userID, `user`.username, `group_user`.accessLevel \
                     FROM `group_user` \
                     INNER JOIN `user` \
                     ON `user`.userID = `group_user`.userID \
                     WHERE `group_user`.groupID=%s" 
            results = get_from_db(query, data['groupID'], conn, cursor)
            
            users = []
            if results and results[0]:
                for user in results:
                    users.append(convertUsersToJSON(user))
            
            raise ReturnSuccess(users, 200)
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

def convertGroupsToJSON(session):
    if len(session) < 4:
        return errorMessage("passed wrong amount of values to convertSessionsToJSON, it needs all elements in session table")
    result = {
        'groupID' : session[0],
        'groupName' : session[1],
        'groupCode' : session[2],
        'accessLevel' : session[3],
    }
    return result

def convertUsersToJSON(session):
    if len(session) < 3:
        return errorMessage("passed wrong amount of values to convertSessionsToJSON, it needs all elements in session table")
    result = {
        'userID' : session[0],
        'username' : session[1],
        'accessLevel' : session[2],
    }
    return result

def groupCode_generator(size=5, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))