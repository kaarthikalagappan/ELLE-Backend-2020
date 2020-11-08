from flask import request
from flask_restful import Resource, reqparse
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    get_jwt_claims,
    jwt_required,
    jwt_refresh_token_required,
    get_raw_jwt,
    get_current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from flaskext.mysql import MySQL
from flask_mail import Message
from db import mysql
from db_utils import *
from utils import *
from random_username.generate import generate_username
import json
import datetime
import string
import random
from config import HAND_PREFERENCES

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
        if row[1].lower() == username:
            return True, row

    return False, None

def find_by_email(email):

    query = "SELECT user.userID FROM user WHERE email=%s"
    result = get_from_db(query, email)

    if result and result[0]:
            return True, result[0][0]

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

        query = f"SELECT * FROM user WHERE user.userID != {user_id}"
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
            # newUserObject['lastToken'] = row[5]
            newUserObject['email'] = row[7]
        return newUserObject

    @jwt_required
    def put(self):
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401
        
        user_parser = reqparse.RequestParser()
        user_parser.add_argument('newEmail',
                                  type=str,
                                  required=True,
                                  )
        data = user_parser.parse_args()

        try:
            conn = mysql.connect()
            cursor = conn.cursor()
            if data['newEmail'] == '':
                data['newEmail'] = None
            update_email_query = f"UPDATE `user` SET `email` = '{data['newEmail']}' WHERE `user`.`userID` = {user_id}"
            post_to_db(update_email_query)

            raise ReturnSuccess("Successfully changed email", 200)
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
                refresh_token = create_refresh_token(identity=user_obj)
                query = "UPDATE `user` SET `lastToken`=%s WHERE `userID` =%s"
                post_to_db(query, (access_token , user[0]))
                return {
                    'access_token': access_token,
                    'refresh_token' : refresh_token,
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
        user_parser.add_argument('email',
                                  type=str,
                                  required=False,
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

            if not data['email']:
                data['email'] = ''
            else:
                data['email'] = data['email'].lower()
                find_email, _ = find_by_email(data['email'])
                if find_email:
                    raise UserException("Email already exists.", 401)
 
            query = "INSERT INTO user (`username`, `password`, `permissionGroup`, `email`) VALUES (%s, %s, %s, %s)"
            salted_password = generate_password_hash(data['password'])
            # print(data['email'])
            post_to_db(query, (data['username'], salted_password, 'st', data['email']), conn, cursor)

            query = "SELECT `userID` FROM `user` WHERE `username`=%s"
            results = get_from_db(query, data['username'], conn, cursor)
            user_id = results[0][0]

            add_preferences = f"INSERT INTO user_preferences (userID) VALUES ('{user_id}')"
            post_to_db(add_preferences, None, conn, cursor)

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
        user_parser.add_argument('email',
                                  type=str,
                                  required=True,
                                  )
        user_parser.add_argument('resetToken',
                                  type=str,
                                  required=True,
                                  )
        user_parser.add_argument('password',
                                  type=str,
                                  required=True,
                                  )
        user_parser.add_argument('confirmPassword',
                                  type=str,
                                  required=True,
                                  )
        data = user_parser.parse_args()

        if data['password'] != data['confirmPassword']:
            return {'Message':'Passwords do not match!'}, 400

        get_associated_user = f"""SELECT user.userID, user.pwdResetToken FROM user 
                              WHERE user.email = '{data['email'].lower()}'
                              """
        print(data)
        associated_user = get_from_db(get_associated_user)

        if not associated_user or not associated_user[0] \
           or not associated_user[0][1] \
           or not check_password_hash(associated_user[0][1], data['resetToken']):
            return {"Message" : "No records match what was provided"}, 404
        
        try:
            conn = mysql.connect()
            cursor = conn.cursor()
            
            password = generate_password_hash(data['password'])
            query = f"UPDATE user SET pwdResetToken = NULL, password = '{password}' WHERE userID = {associated_user[0][0]}"
            post_to_db(query, None, conn, cursor)

            raise ReturnSuccess("Successfully reset password", 200)
        except ReturnSuccess as success:
            conn.commit()
            return success.msg, success.returnCode
        except Exception as error:
            conn.rollback()
            return errorMessage(str(error))
        finally:
            if(conn.open):
                cursor.close()
                conn.close()


# Send a reset token to the email for user to reset password
class ForgotPassword(Resource):
    def __init__(self, **kwargs):
        # smart_engine is a black box dependency
        self.mail = kwargs['mail']

    def post(self):
        user_parser = reqparse.RequestParser()
        user_parser.add_argument('email',
                                  type=str,
                                  required=True,
                                  )
        data = user_parser.parse_args()
        data['email'] = data['email'].lower()

        returnMessage = {"Message" : "Processed"}

        get_user = f"SELECT user.userID FROM user WHERE user.email = '{data['email']}'"
        associated_user = get_from_db(get_user)
        if not associated_user or not associated_user[0]:
            return returnMessage, 202
        
        resetToken = otc_generator(20, string.hexdigits + '!#_@')
        check_token_query = f"SELECT user.userID FROM user WHERE user.pwdResetToken = '{resetToken}'"
        if_exist = get_from_db(check_token_query)
        print(resetToken)
        while if_exist and if_exist[0]:
            resetToken = otc_generator(20, string.hexdigits + '!#_@')
            check_token_query = f"SELECT user.userID FROM user WHERE user.pwdResetToken = '{resetToken}'"
            if_exist = get_from_db(check_token_query)

        update_pwdToken_query = f"UPDATE user SET pwdResetToken = '{generate_password_hash(resetToken)}' WHERE userID = {associated_user[0][0]}"
        post_to_db(update_pwdToken_query)

        # msg = Message("Hello",
        #             sender="endless@endlesslearner.com",
        #             recipients=[data['email']])
        # msg.body = f"""You are recieving this email because you requested to reset your Endlesslearner password.
        #             Please visit https://endlesslearner.com/resetpassword and use the token {resetToken} to reset your password.
        #             If you did not request to reset your password, ignore this email."""
        # self.mail.send(msg)

        return returnMessage, 202


class ChangePassword(Resource):
    # This API to used to reset another user's password or the current user's password
    @jwt_required
    def post(self):
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Unauthorized user", 401

        user_parser = reqparse.RequestParser()
        user_parser.add_argument('userID',
                                  type=str,
                                  required=False,
                                  )
        user_parser.add_argument('password',
                                  type=str,
                                  required=True,
                                  )
        data = user_parser.parse_args()
        print(data)
        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            if permission == 'pf' and data['userID'] and data['userID'] != '':
                get_user_status = f"SELECT user.permissionGroup FROM user WHERE user.userID = {data['userID']}"
                user_status = get_from_db(get_user_status, None, conn, cursor)
                if not user_status or not user_status[0]:
                    raise UserException("Referred user not found", 400)
                if user_status[0][0] != 'st':
                    raise UserException("A professor cannot reset non-student users' password", 400)

            # Only superadmins and professors can reset another user's password
            if permission != 'su' and permission != 'pf' and data['userID']:
                raise UserException("Cannot reset another user's password", 400)
            elif ((permission == 'su' or permission == 'pf') and (not data['userID'] or data['userID'] == '')) or permission == 'st':
                data['userID'] = user_id
 
            password = generate_password_hash(data['password'])
            query = f"UPDATE user SET password = '{password}' WHERE userID = {data['userID']}"
            post_to_db(query, None, conn, cursor)
          
            raise ReturnSuccess("Successfully reset password", 200)
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


# Send a reset token to the email for user to reset password
class ForgotUsername(Resource):
    def __init__(self, **kwargs):
        # smart_engine is a black box dependency
        self.mail = kwargs['mail']

    def post(self):
        user_parser = reqparse.RequestParser()
        user_parser.add_argument('email',
                                  type=str,
                                  required=True,
                                  )
        data = user_parser.parse_args()
        data['email'] = data['email'].lower()

        returnMessage = {"Message" : "Processed"}

        get_user = f"SELECT user.username FROM user WHERE user.email = '{data['email']}'"
        username = get_from_db(get_user)
        if not username or not username[0]:
            return returnMessage, 202

        msg = Message("Hello",
                    sender="endless@endlesslearner.com",
                    recipients=[data['email']])
        msg.body = f"""You are recieving this email because you requested to receive your Endlesslearner username.
                    The username associated with this email is {username[0][0]}.
                    Please visit https://endlesslearner.com/login to login with that username."""
        self.mail.send(msg)

        return returnMessage, 202


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
            return user_id, 200
        return -1, 401



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


class GenerateOTC(Resource):
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

            otc = otc_generator()
            query = "UPDATE `user` SET `otc`=%s WHERE `userID`=%s"
            results = post_to_db(query, (otc, user_id), conn, cursor)

            raise ReturnSuccess({"otc" : otc}, 200)
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


class OTCLogin(Resource):
    def post(self):
        user_parser = reqparse.RequestParser()
        user_parser.add_argument('otc',
                                  type=str,
                                  required=True,
                                )
        data = user_parser.parse_args()
        
        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            query = "SELECT * FROM `user` WHERE `otc`=%s"
            results = get_from_db(query, data['otc'], conn, cursor)
            
            # Remove the otc from user after logging in
            if results and results[0]:
                put_in_blacklist(results[0][0])
                query = "UPDATE `user` SET `otc`=%s WHERE `userID`=%s"
                post_to_db(query, (None,results[0][0]), conn, cursor)
            else:
                raise UserException("Invalid otc", 400)

            expires = datetime.timedelta(days=14)
            user_obj = UserObject(user_id=results[0][0], permissionGroup=results[0][4])
            access_token = create_access_token(identity=user_obj, expires_delta=expires)
            refresh_token = create_refresh_token(identity=user_obj)
            query = "UPDATE `user` SET `lastToken`=%s WHERE `userID` =%s"
            post_to_db(query, (access_token , results[0][0]), conn, cursor)

            raise ReturnSuccess({"access_token" : access_token, "refresh_token" : refresh_token, "id" : results[0][0]}, 200)
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


class User_Preferences(Resource):
    #Get current user's preferences
    @jwt_required
    def get(self):
        # Validate the user
        permission, user_id = validate_permissions()
        print(permission)
        if not permission or not user_id:
            return "Invalid user", 401

        query = f"SELECT * from user_preferences WHERE userID = {user_id}"
        user_preference = get_from_db(query)
        if not user_preference or not user_preference[0]:
            return "An error occured", 500
        return userPreferencesToJSON(user_preference[0])

    #Update the user preferences
    @jwt_required
    def put(self):
        # Validate the user
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401
        
        parser = reqparse.RequestParser()
        parser.add_argument('preferredHand',
                            required = True,
                            type = str,
                            help = "preferred hand of each user is required. R for right hand, L for Left, or A for Ambidextrous")
        parser.add_argument('vrGloveColor',
                            required = True,
                            type = str,
                            help = "Specify a glove value that represents a glove color in VR game. Max 15 characters")
        data = parser.parse_args()

        if data['preferredHand'] not in HAND_PREFERENCES:
            return "Please pass in either R, L, or A for hand preferences", 400

        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            update_query = f"""
                            UPDATE user_preferences SET
                            preferredHand = '{data['preferredHand']}', vrGloveColor = '{data['vrGloveColor']}'
                            WHERE user_preferences.userID = {user_id}
                            """
            post_to_db(update_query, None, conn, cursor)
            
            raise ReturnSuccess("Successfully updated preferences", 200)
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


class Refresh(Resource):
    @jwt_refresh_token_required
    def post(self):
        user_id = get_jwt_identity()
        query = f"SELECT `permissionGroup`, `email` FROM `user` WHERE `userID`= {user_id}"
        permission = get_from_db(query)
        print(permission[0][0])

        user_obj = UserObject(user_id=user_id, permissionGroup=permission[0][0])
        return { 'access_token': create_access_token(identity=user_obj), 'user_id' : user_id }, 200
    
        

#Convert user_preferences information returned from the database into JSON obj
def userPreferencesToJSON(data):
    # Update this as the user_preferences table is updated
    return {
        'userPreferenceID' : data[0],
        'userID' : data[1],
        'preferredHand' : data[2],
        'vrGloveColor' : data[3]
    }


def otc_generator(size=6, chars=string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

def convertUserLevelsToJSON(userLevel):
    if len(userLevel) < 3:
        return errorMessage("passed wrong amount of values to convertUserLevelsToJSON")
    result = {
        'groupID' : userLevel[0],
        'groupName' : userLevel[1],
        'accessLevel' : userLevel[2],
    }
    return result