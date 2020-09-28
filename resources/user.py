from flask import request
from flask_restful import Resource, reqparse
from flask_jwt_extended import (
    create_access_token,
    get_jwt_identity,
    jwt_required,
    get_raw_jwt,
    get_current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from flaskext.mysql import MySQL
from db import mysql
from db_utils import *
from utils import *
from random_username.generate import generate_username
import json
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


class UserException(Exception):
    def __init__(self, msg, returnCode):
        # Error message is stored formatted in msg and response code stored in returnCode
        if isinstance(msg, str):
            self.msg = errorMessage(msg)
        else:
            self.msg = msg
        self.returnCode = returnCode

def find_by_name(username):

    query = "SELECT * FROM user WHERE username=%s"
    result = get_from_db(query, (username,))

    for row in result:
        if row[1] == username:
            return True, row

    return False, None

def find_by_token(token):

    query = "SELECT * FROM tokens WHERE expired=%s"
    result = get_from_db(query, (token,))

    for row in result:
        if row[0] == token:
            return False

    return True

def check_user_db(_id):

    query = "SELECT * FROM user WHERE userID=%s"
    result = get_from_db(query, (_id,))

    for row in result:
        if row[0] == _id:
            return True

    return False



# A complex object that stores the user's userID and permissionGroup
# that'll be stored in the JWT token
class UserObject:
    def __init__(self, user_id, permissionGroup):
        self.user_id = user_id
        self.permissionGroup = permissionGroup



#TODO: GOT TO CHANGE THIS LOGIC AS GROUPID ISN'T REQUIRED - JUST THE groupCode
def check_group_db(id, password):
    query = "SELECT * FROM `group` WHERE `groupID`=%s"
    result = get_from_db(query, (id,))

    for row in result:
        if row[0] == id:
            if row[2] == password:
                return True
    return False


#returns list of all the users
class Users(Resource):
    @jwt_required
    def get(self):
        permission, user_id = validate_permissions()
        if not permission or not user_id or permission != 'su':
            return "Invalid user", 401

        query = "SELECT * FROM user"
        result = get_from_db(query)

        final_list_users = []
        for row in result:
            new_item = {}
            new_item['userID'] = row[0]
            new_item['username'] = row[1]
            new_item['permissionGroup'] = row[4]
            final_list_users.append(new_item)
        
        get_group_query = """SELECT `group`.* FROM `group` JOIN `group_user` 
                                ON `group_user`.`groupID`=`group`.`groupID` 
                                WHERE `group_user`.`userID`= %s"""
        for user in final_list_users:
            if user['permissionGroup'] == 'pf':
                groups = get_from_db(get_group_query, user['userID'])
                groups_list = []
                if groups and groups[0]:
                    for indv_groupID in groups:
                        groups_list.append({'groupID' : indv_groupID[0], 'groupName' : indv_groupID[1], 'groupCode' : indv_groupID[2]})
                user['groups'] = groups_list
        return final_list_users



class User(Resource):
    @jwt_required
    def get(self):
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401

        query = "SELECT * FROM user WHERE userID = "+ str(user_id)
        result = get_from_db(query)
        for row in result:
            newUserObject = {}
            newUserObject['id'] = row[0]
            newUserObject['username'] = row[1]
            newUserObject['permissionGroup'] = row[4]
            newUserObject['lastToken'] = row[5]
        return newUserObject





#logs user out and sets their lastToken to null
class UserLogout(Resource):
    @jwt_required
    def post(self):
        permission, user_id = validate_permissions()

        if not permission or not user_id:
            return "Invalid user", 401

        put_in_blacklist(user_id)
        return{"message":"Successfully logged out"}, 200



#logs the user in and assigns them a jwt access token
class UserLogin(Resource):
    def post(self):
        user_parser = reqparse.RequestParser()
        user_parser.add_argument('username',
                                  type=str,
                                  required=True,
                                  )
        user_parser.add_argument('password',
                                  type=str,
                                  required=True,
                                  )
        data = user_parser.parse_args()

        data['username'] = data['username'].lower()
        find_user, user = find_by_name(data['username'])
        if find_user:
            if check_password_hash(user[2], data['password']):
                put_in_blacklist(user[0])
                expires = datetime.timedelta(days=14)
                user_obj = UserObject(user_id=user[0], permissionGroup=user[4])
                access_token = create_access_token(identity=user_obj, expires_delta=expires)
                query = "UPDATE `user` SET `lastToken`=%s WHERE `userID` =%s"
                post_to_db(query, (access_token , user[0]))
                return {
                    'access_token': access_token,
                    'id':user[0]
                }, 200
            else:
                return{'message':'Incorrect Password. Try again'}, 401
        return{'message':'User Not Found!'}, 401



#register the user to the database
class UserRegister(Resource):
    def post(self):
        user_parser = reqparse.RequestParser()
        user_parser.add_argument('username',
                                  type=str,
                                  required=True,
                                  )
        user_parser.add_argument('password',
                                  type=str,
                                  required=True,
                                  )
        user_parser.add_argument('password_confirm',
                                  type=str,
                                  required=True,
                                  )
        user_parser.add_argument('groupCode',
                                  type=str,
                                  required=False,
                                  )
        data = user_parser.parse_args()
        
        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            #adds user to the database if passwords match and username isn't taken
            if data['password'] != data['password_confirm']:
                raise UserException("Password do not match.", 401)

            data['username'] = data['username'].lower()

            find_user, user = find_by_name(data['username'])
            if find_user == True:
                raise UserException("Username already exists.", 401)

            query = "INSERT INTO user (`username`, `password`, `permissionGroup`) VALUES (%s, %s, %s)"
            salted_password = generate_password_hash(data['password'])

            post_to_db(query, (data['username'], salted_password,'st'), conn, cursor)

            query = "SELECT `userID` FROM `user` WHERE `username`=%s"
            results = get_from_db(query, data['username'], conn, cursor)
            user_id = results[0][0]

            if data['groupCode']:
                gc_query = "SELECT `groupID` FROM `group` WHERE `groupCode`=%s"
                results = get_from_db(gc_query, data['groupCode'], conn, cursor)
                if results:
                    group_id = results[0][0]
                    gu_query = "INSERT INTO `group_user` (`userID`, `groupID`, `accessLevel`) VALUES (%s, %s, %s)"
                    post_to_db(gu_query, (user_id, group_id, 'st'), conn, cursor)
          
            raise ReturnSuccess("Successfully registered!", 201)
        except ReturnSuccess as success:
            conn.commit()
            return success.msg, success.returnCode
        except UserException as error:
            conn.rollback()
            return error.msg, error.returnCode
        except Exception as error:
            conn.rollback()
            return errorMessage(str(error)), 500
        finally:
            if(conn.open):
                cursor.close()
                conn.close()

#resets password for the given UserID
class ResetPassword(Resource):
    def post(self):
        user_parser = reqparse.RequestParser()
        user_parser.add_argument('userID',
                                  type=int,
                                  required=True,
                                  )
        user_parser.add_argument('pw',
                                  type=str,
                                  required=True,
                                  )
        user_parser.add_argument('confirm',
                                  type=str,
                                  required=True,
                                  )
        data = user_parser.parse_args()

        if data['pw'] != data['confirm']:
            return {'message':'Passwords do not match!'},400

        pw = generate_password_hash(data['pw'])

        query = "UPDATE user SET password=%s WHERE userID=" + str(data['userID'])

        post_to_db(query, (pw,))

        return {'message':'Successfully reset the password'}, 201

#Checks to see whether given token is active or not
class CheckIfActive(Resource):
    @jwt_required
    def post(self):
        user_parser = reqparse.RequestParser()
        user_parser.add_argument('token',
                                  type=str,
                                  required=True,
                                  )
        data = user_parser.parse_args()

        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401

        if find_by_token(data['token']):
            return user_id
        return -1, 400



class UsersHighscores(Resource):
    def post(self):
        user_parser = reqparse.RequestParser()
        user_parser.add_argument('moduleID',
                                  type=str,
                                  required=True,
                                  )
        user_parser.add_argument('platform',
                                  type=str,
                                  required=True,
                                  )
        data = user_parser.parse_args()

        query = "SELECT `userID`,`playerScore` FROM `session` WHERE `moduleID`=%s AND`platform`=%s ORDER BY LENGTH(`playerScore`),`playerScore`"
        result = get_from_db(query, (data['moduleID'], data['platform']))
        user = []

        for row in result:
            userscores = {}
            userscores['score'] = row[1]
            query = "SELECT `username` FROM `user` WHERE `userID`=%s"
            name = get_from_db(query, row[0])
            for row2 in name:
                userscores['usernames'] = name[0][0]
            user.append(userscores)
        return user

class UserLevels(Resource):
    @jwt_required
    def get(self):
        user_parser = reqparse.RequestParser()
        data = user_parser.parse_args()

        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401
        
        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            query = "SELECT `group`.groupID, `group`.groupName, `group_user`.accessLevel \
                     FROM `group_user` \
                     INNER JOIN `group` \
                     ON `group`.groupId = `group_user`.groupID \
                     WHERE `group_user`.userID=%s" 
            results = get_from_db(query, user_id, conn, cursor)

            userLevels = []
            for userLevel in results:
                userLevels.append(convertUserLevelsToJSON(userLevel))
          
            raise ReturnSuccess(userLevels, 201)
        except ReturnSuccess as success:
            conn.commit()
            return success.msg, success.returnCode
        except UserException as error:
            conn.rollback()
            return error.msg, error.returnCode
        except Exception as error:
            conn.rollback()
            return errorMessage(str(error)), 500
        finally:
            if(conn.open):
                cursor.close()
                conn.close()

class GenerateUsername(Resource):
    def get(self):
        return {"username" : generate_username(1)[0]}

class GetUsernames(Resource):
    @jwt_required
    def get(self):
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401
        
        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            query = "SELECT `username` FROM `user`" 
            results = get_from_db(query, None, conn, cursor)

            usernames = []
            for username in results:
                usernames.append(username[0])
          
            raise ReturnSuccess(usernames, 201)
        except ReturnSuccess as success:
            conn.commit()
            return success.msg, success.returnCode
        except UserException as error:
            conn.rollback()
            return error.msg, error.returnCode
        except Exception as error:
            conn.rollback()
            return errorMessage(str(error)), 500
        finally:
            if(conn.open):
                cursor.close()
                conn.close()

def convertUserLevelsToJSON(userLevel):
    if len(userLevel) < 3:
        return errorMessage("passed wrong amount of values to convertUserLevelsToJSON")
    result = {
        'groupID' : userLevel[0],
        'groupName' : userLevel[1],
        'accessLevel' : userLevel[2],
    }
    return result