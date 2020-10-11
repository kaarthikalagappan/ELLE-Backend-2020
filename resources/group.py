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

        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401

        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            if permission != 'pf':
                raise GroupException("User cannot create classes.", 400)

            # Checks if the groupName already exists
            dupe_query = "SELECT `groupID` FROM `group` WHERE `groupName`=%s"
            dupe_results = get_from_db(dupe_query, data['groupName'], conn, cursor)

            if dupe_results:
                raise GroupException("groupName already exists.", 400)
            else:
                # Randomly generate 6-long string of numbers and letters
                # String must be unique for each class
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

                # Users who creates a class have their accesLevel default to 'pf'
                gu_query = "INSERT INTO `group_user` (`userID`, `groupID`, `accessLevel`) VALUES (%s, %s, %s)"
                post_to_db(gu_query, (user_id, group_id, 'pf'), conn, cursor)

                raise ReturnSuccess("Successfully created the class.", 200)
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

    # Edit a group
    @jwt_required
    def put(self):
        parser = reqparse.RequestParser()
        parser.add_argument('groupID',
                            required = True,
                            type = int)
        parser.add_argument('groupName',
                            required = False,
                            type = str)
        parser.add_argument('groupCode',
                            required = False,
                            type = str)
        data = parser.parse_args()

        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401

        if 'groupName' not in data or not data['groupName']:
            data['groupName'] = None

        if 'groupCode' not in data or not data['groupCode']:
            data['groupCode'] = None

        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            # Only professors and superadmins can edit groups
            if permission == 'st':
                raise GroupException("Invalid permissions.", 400)
        
            # Checking groupName and make sure it is unique
            if data['groupName'] is not None:
                gn_query = "SELECT `groupID` FROM `group` WHERE `groupName`=%s"
                gn_results = get_from_db(gn_query, data['groupName'], conn, cursor)
            
                if gn_results:
                    raise GroupException("groupName already in use.", 400)

            # Checking groupCode and make sure it is unique
            if data['groupCode'] is not None:
                gc_query = "SELECT `groupID` FROM `group` WHERE `groupCode`=%s"
                gc_results = get_from_db(gc_query, data['groupCode'], conn, cursor)
            
                if gc_results:
                    raise GroupException("groupCode already in use.", 400)
        
            if data['groupCode'] is not None and data['groupName'] is None:
                query ="UPDATE `group` SET `groupCode`=%s WHERE `groupID`=%s"
                results = post_to_db(query, (data['groupCode'], data['groupID']), conn, cursor)
            elif data['groupCode'] is None and data['groupName'] is not None:
                query ="UPDATE `group` SET `groupName`=%s WHERE `groupID`=%s"
                results = post_to_db(query, (data['groupName'], data['groupID']), conn, cursor)
            elif data['groupCode'] is not None and data['groupName'] is None:
                query ="UPDATE `group` SET `groupName`=%s, `groupCode`=%s WHERE `groupID`=%s"
                results = post_to_db(query, (data['groupName'], data['groupCode'], data['groupID']), conn, cursor)
            else:
                raise ReturnSuccess("No values passed in, nothing changed.", 200)

            raise ReturnSuccess("Successfully updated group.", 200)
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

    # Delete a group
    @jwt_required
    def delete(self):
        parser = reqparse.RequestParser()
        parser.add_argument('groupID',
                            required = True,
                            type = int)
        data = parser.parse_args()

        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401

        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            # Only professors and superadmins can delete groups
            if permission == 'st':
                raise GroupException("Invalid permissions.", 400)

            query = "DELETE FROM `group` WHERE `groupID` = %s"
            delete_from_db(query, data['groupID'], conn, cursor)
        
            raise ReturnSuccess("Successfully deleted group.", 200)
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

        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401

        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            if permission == 'su':
                return GroupException("Superadmins cannot register for classes."), 400

            query = "SELECT `groupID` FROM `group` WHERE `groupCode` = %s"
            results = get_from_db(query, data['groupCode'], conn, cursor)

            # if groupCode exists in group table
            if results:
                group_id = results[0][0]    

                # Check if the user has already registered for the group
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

        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401

        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            # Get the group's information and append the user's accessLevel in the group
            query = "SELECT `group`.*, `group_user`.accessLevel \
                     FROM `group` \
                     INNER JOIN `group_user` \
                     ON `group_user`.groupID = `group`.groupID \
                     WHERE `group_user`.userID=%s" 
            results = get_from_db(query, user_id, conn, cursor)
            
            # Get all users in the group
            get_group_users_query = "SELECT `user`.userID, `user`.username, `group_user`.accessLevel \
                                    FROM `group_user` \
                                    INNER JOIN `user` \
                                    ON `user`.userID = `group_user`.userID \
                                    WHERE `group_user`.groupID=%s" 

            groups = []
            if results and results[0]:
                for group in results:
                    groupObj = convertGroupsToJSON(group)

                    if permission == 'pf' or permission == 'su':
                        group_users = []
                        group_users_from_db = get_from_db(get_group_users_query, groupObj['groupID'], conn, cursor)
                        for indv_group_user in group_users_from_db:
                            group_users.append(convertUsersToJSON(indv_group_user))
                        groupObj['group_users'] = group_users

                    groups.append(groupObj)
            
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
    # Get's all the users in a specific group
    @jwt_required
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('groupID',
                            required = True,
                            type = int)
        data = parser.parse_args()

        permission, user_id = validate_permissions()

        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            # Only superadmins/professors can search for users in a group
            if permission == 'st':
                raise GroupException("User cannot search for users in a group.", 400)

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

class GenerateGroupCode(Resource):
    @jwt_required
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('groupID',
                            required = True,
                            type = int)
        data = parser.parse_args()

        permission, user_id = validate_permissions()

        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            if permission == 'st':
                raise GroupException("User cannot generate new group codes.", 400)

            group_code = groupCode_generator()
            while True:
                gc_query = "SELECT `groupID` FROM `group` WHERE `groupCode`=%s"
                gc_results = get_from_db(gc_query, group_code)

                if gc_results:
                    group_code = groupCode_generator()
                else:
                    break
            
            query = "UPDATE `group` SET `groupCode`=%s WHERE `groupID`=%s"
            results = post_to_db(query, (group_code, data['groupID']), conn, cursor)

            raise ReturnSuccess({"groupCode" : group_code}, 200)
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