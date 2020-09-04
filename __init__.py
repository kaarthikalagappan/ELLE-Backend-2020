#Some of the imports are not used; they were copied and pasted from the existing Flask app's __init__.py
from flask import Flask, render_template, Response, request, send_file, send_from_directory, jsonify
from flask_restful import Resource, Api
from flask_jwt_extended import JWTManager
from flaskext.mysql import MySQL
import config
from flask_cors import CORS
from resources.testing import Testing, JWTTest
from resources.user import UserRegister, Users, UserLogin, UserLogout, User, ResetPassword, CheckIfActive, UsersHighscores
from resources.terms import Term, Tags, Tag_Term, Tags_In_Term, Specific_Term
from resources.game_logs import GameLog
from resources.logged_answer import LoggedAnswer
from resources.sessions import Session, SearchSessions, End_Session, GetAllSessions
from resources.question import Question, Answer, SearchType, SearchText, DeleteQuestion, DeleteAnswer, Modify
from resources.modules import Modules, ModuleQuestions, Module, AttachQuestion, AttachTerm, RetrieveAllModules, RetrieveGroupModules, AddModuleGroup, SearchModules
from resources.stats import ModuleReport, ModuleStats, PlatformStats, PlatformNames
from resources.access import Access
from resources.group import Group, GroupRegister, SearchUserGroups, UsersInGroup
from db import mysql
from db_utils import *
from pathlib import Path
import os.path

app = Flask(__name__, static_folder='templates/build/static')
CORS(app)
app.config['MYSQL_DATABASE_USER'] = config.MYSQL_DATABASE_USER
app.config['MYSQL_DATABASE_PASSWORD'] = config.MYSQL_DATABASE_PASSWORD
#Change the name of the database to the new database
app.config['MYSQL_DATABASE_DB'] = config.MYSQL_DATABASE_DB
app.config['MYSQL_DATABASE_HOST'] = config.MYSQL_DATABASE_HOST
app.config['JWT_BLACKLIST_ENABLED'] = True
app.config['JWT_BLACKLIST_TOKEN_CHECKS'] = ['access']  # allow blacklisting for access tokens
app.config['UPLOAD_FOLDER'] = Path('uploads') #??
app.config['PROPOGATE_EXCEPTIONS'] = True
app.secret_key = config.SECRET_KEY
mysql.init_app(app)
api = Api(app)

jwt = JWTManager(app)

@jwt.unauthorized_loader
def unauthorized(self):
	resp = Response(render_template('/var/www/html/index.html'), mimetype='text/html')
	return resp

@app.errorhandler(404)
def page_not_found(e):
	resp = Response(render_template('/var/www/html/index.html'), mimetype='text/html')
	return resp


# Given a complex object, this returns the permossion group
# stored in it when get_jwt_identity() is called
@jwt.user_claims_loader
def add_claims_to_access_token(user):
    return user.permissionGroup


# Given a complex object, this returns the user id stored in it
# when get_jwt_claims() is called
@jwt.user_identity_loader
def user_identity_lookup(user):
    return user.user_id


class HomePage(Resource):

	def get(self):

		resp = Response(render_template('/var/www/html/index.html'), mimetype='text/html')
		return resp

@jwt.token_in_blacklist_loader
def check_if_token_in_blacklist(decrypted_token):
    jti = decrypted_token['jti']
    query = "SELECT * from tokens"
    result = get_from_db(query)

    if result and jti in result[0]:
    	return True
    else:
    	return False

api.add_resource(Testing, '/newTest')
api.add_resource(JWTTest, '/jwttest')
api.add_resource(UserRegister, '/register')
api.add_resource(Users, '/users')
api.add_resource(UserLogin, '/login')
api.add_resource(UserLogout, '/logout')
api.add_resource(User, '/user')
api.add_resource(UsersHighscores,'/highscores')
api.add_resource(ResetPassword, '/resetpassword')
api.add_resource(CheckIfActive, '/activejwt')
api.add_resource(Term, '/term')
api.add_resource(Tags, '/tags')
api.add_resource(Tag_Term, '/tag_term')
api.add_resource(Tags_In_Term, '/tags_in_term')
api.add_resource(Specific_Term, '/specificterm')
api.add_resource(Question, '/question')
api.add_resource(Answer, '/addAnswer')
api.add_resource(SearchType,'/searchbytype')
api.add_resource(SearchText,'/searchbytext')
api.add_resource(DeleteQuestion,'/deletequestion')
api.add_resource(DeleteAnswer,'/deleteanswer')
api.add_resource(Modify, '/modifyquestion')
api.add_resource(Modules,'/modules')
api.add_resource(ModuleQuestions,'/modulequestions')
api.add_resource(Module,'/module')
api.add_resource(RetrieveAllModules, '/retrievemodules')
api.add_resource(RetrieveGroupModules, '/retrievegroupmodules')
api.add_resource(AddModuleGroup, '/addmoduletogroup')
api.add_resource(SearchModules, '/searchmodules')
api.add_resource(AttachQuestion, '/attachquestion')
api.add_resource(AttachTerm, '/attachterm')
api.add_resource(LoggedAnswer, '/loggedanswer')
api.add_resource(Session, '/session')
api.add_resource(SearchSessions, '/searchsessions')
api.add_resource(End_Session, '/endsession')
api.add_resource(GameLog, '/gamelog')
api.add_resource(ModuleReport, '/modulereport')
api.add_resource(ModuleStats, '/modulestats')
api.add_resource(PlatformStats, '/platformstats')
api.add_resource(PlatformNames, '/platformnames')
api.add_resource(GetAllSessions, '/getallsessions')
api.add_resource(Access, '/elevateaccess')
api.add_resource(Group, '/group')
api.add_resource(GroupRegister, '/groupregister')
api.add_resource(SearchUserGroups, '/searchusergroups')
api.add_resource(UsersInGroup, '/usersingroup')

if __name__ == '__main__':
	app.run(host='0.0.0.0', port='3000', debug=True)
