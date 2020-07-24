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
import json
import datetime

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
        query = "SELECT * FROM user"
        result = get_from_db(query)

        final_list_users = []
        for row in result:
            new_item = {}
            new_item['userID'] = row[0]
            new_item['username'] = row[1]
            new_item['permissionGroup'] = row[4]
            final_list_users.append(new_item)

        return final_list_users



class User(Resource):
    @jwt_required
    def get(self):
        id = get_jwt_identity()
        query = "SELECT * FROM user WHERE userID = "+ str(id)
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
        user_id = get_jwt_identity();
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

        find_user, user = find_by_name(data['username'])
        if find_user:
            if check_password_hash(user[2], data['password']):
                put_in_blacklist(user[0])
                expires = datetime.timedelta(days=14)
                access_token = create_access_token(identity=user[0], expires_delta=expires)
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
        user_parser.add_argument('groupID',
		                          type=int,
		                          required=False,
		                          )
        user_parser.add_argument('groupPassword',
		                          type=str,
		                          required=False,
		                          )
        data = user_parser.parse_args()


        #adds user to the database if passwords match and username isn't taken
        if data['password'] != data['password_confirm']:
            return {'message':'Passwords do not match.'},400

        find_user, user = find_by_name(data['username'])
        if find_user == True:
            return {'message':'Username exists, try again.'},400

        query = "INSERT INTO user (`username`, `password`, `permissionGroup`) VALUES (%s, %s, %s)"
        salted_password = generate_password_hash(data['password'])

        post_to_db(query, (data['username'], salted_password,'us'))

        #logic to deal if user is requesting to join a group, and checks validation
        if data['groupID'] != None:
            checkGroup = check_group_db(data['groupID'],data['groupPassword'])
            if checkGroup == True:
                find_user, user = find_by_name(data['username'])
                query = "INSERT INTO `group_user` (`userID`, `groupID`, `isAdmin`) VALUES (%s, %s, %s)"
                post_to_db(query, (user[0], data['groupID'], 0))


        return {'message':'Successfully registered!'}, 201

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
			return{'message':'Passwords do not match!'},400

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
        id = get_jwt_identity()
        if find_by_token(data['token']):
            return id
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
