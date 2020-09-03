# -*- encoding: utf-8 -*-

from flask import send_file, request, json
from flask_restful import Resource, reqparse
from flask_jwt_extended import jwt_required, get_jwt_identity, get_raw_jwt, get_jwt_claims
from config import IMG_RETRIEVE_FOLDER, AUD_RETRIEVE_FOLDER
from db import mysql
from db_utils import *
from utils import *
import os.path


class CustomException(Exception):
    def __init__(self, msg, returnCode):
        # Error message is stored formatted in msg and response code stored in returnCode
        self.msg = errorMessage(msg)
        self.returnCode = returnCode


class ReturnSuccess(Exception):
    def __init__(self, msg, returnCode):
        # Message is stored formatted in msg and response code stored in returnCode
        if isinstance(msg, str):
            self.msg = returnMessage(msg)
        else:
            self.msg = msg
        self.returnCode = returnCode


# Gets the groupID
def get_group_id():
	parser = reqparse.RequestParser()
	parser.add_argument('groupID', type=int, required=False, help="Please pass in the groupID")
	data = parser.parse_args()
	return data['groupID']

# Gets module id from JSON
def get_module_id():
	parser = reqparse.RequestParser()
	parser.add_argument('moduleID', type=int, required=True, help="Please pass in the moduleID")
	data = parser.parse_args()
	return data['moduleID']

# Gets image location from image_id
def get_image_location(image_id):
	# If ID is null
	if image_id == None:
		return ''
	response = {}
	query = f"SELECT imageLocation FROM image WHERE imageID = {image_id};"
	result = get_from_db(query)
	if result and result[0]:
		return IMG_RETRIEVE_FOLDER + result[0][0]
	else:
		return ''

# Gets audio location from audio_id
def get_audio_location(audio_id):
	# If ID is null
	if audio_id == None:
		return ''
	query = f"SELECT audioLocation FROM audio WHERE audioID = {audio_id};"
	result = get_from_db(query)
	if result and result[0]:
		return AUD_RETRIEVE_FOLDER + result[0][0]
	else:
		return ''

# Attaches or detaches a question from the module, returning false if the question was detached
def attach_question(module_id, question_id):
	query = f"SELECT * FROM module_question WHERE moduleID = {module_id} AND questionID = {question_id}"
	result = get_from_db(query)
	# If an empty list is returned, post new link
	if not result or not result[0]:
		query = f'''INSERT INTO module_question (moduleID, questionID)
				VALUES ({module_id}, {question_id})'''
		post_to_db(query)
		return True
	else:
		# Delete link if it exists
		query = f'''DELETE FROM module_question
				WHERE moduleID = {module_id} AND questionID = {question_id}'''
		post_to_db(query)
		return False


class Modules(Resource):

	# For acquiring all modules available for the current user
	# based on the user's registered groups
	@jwt_required
	def get(self):
		user_id = get_jwt_identity()

		query = f"""
				SELECT `module`.*, `group_module`.`groupID` FROM `module` 
				INNER JOIN `group_module` ON `module`.`moduleID` = `group_module`.`moduleID` 
				INNER JOIN `group_user` ON `group_module`.`groupID` = `group_user`.`groupID` 
				WHERE `group_user`.`userID`={user_id}
				"""
		result = get_from_db(query)

		modules = []
		for row in result:
			module = {}
			module['moduleID'] = row[0]
			module['name'] = row[1]
			module['language'] = row[2]
			module['complexity'] = row[3]
			module['groupID'] = row[4]
			modules.append(module) 
		
		# Return module information
		return modules


class RetrieveGroupModules(Resource):

	# Get all modules associated with the given groupID
	@jwt_required
	def get(self):
		# Get the user's ID and check permissions
		user_id = get_jwt_identity()
		permission = get_jwt_claims()
		if not permission or permission == "":
			return "Invalid user", 401
		
		group_id = get_group_id()
		if not group_id:
			return "Please pass in a groupID", 400

		query = f"""
				SELECT `module`.* FROM `module` INNER JOIN group_module 
				ON group_module.moduleID = module.moduleID 
				WHERE group_module.groupID={group_id}
				"""
		records = get_from_db(query)
		modules = []
		for row in records:
			module = {}
			module['moduleID'] = row[0]
			module['name'] = row[1]
			module['language'] = row[2]
			module['complexity'] = row[3]
			modules.append(module) 
		
		# Return module information
		return modules


class RetrieveAllModules(Resource):

	# Get all modules in the database
	@jwt_required
	def get(self):
		# Get the user's ID and check permissions
		user_id = get_jwt_identity()
		permission = get_jwt_claims()
		if not permission or permission == "":
			return "Invalid user", 401

		if permission != 'su' and permission != 'pf':
			return "Invalid permission level", 401

		# Query to retrieve all modules
		query = f"SELECT * FROM module;"
		result = get_from_db(query)
		
		# Attaching variable names to rows
		modules = []
		for row in result:
			module = {}
			module['moduleID'] = row[0]
			# module['groupID'] = row[1]
			module['name'] = row[1]
			module['language'] = row[2]
			module['complexity'] = row[3]
			modules.append(module) 
		# Return module information
		return modules

# For acquiring the associated questions and answers with a module
class ModuleQuestions(Resource):

	# Get a list of question objects, which each contain a list of terms functioning as their answers
	# Requires moduleID
	@jwt_required
	def post(self):
		permission = get_jwt_claims()
		if not permission or permission == "":
			return "Invalid user", 401
		
		module_id = get_module_id()
		# Error response if module id is not provided
		if not module_id:
			return {'message' : 'Please provide the id of a module.'}
		# Acquiring list of module questions
		query = f'''
				SELECT question.* from question, module_question
				WHERE module_question.moduleID = {module_id}
				AND module_question.questionID = question.questionID;
				'''
		result = get_from_db(query)
		# Attaching variable names to rows
		questions = []
		for row in result:
			question = {}
			question['questionID'] = row[0]
			question['audioLocation'] = get_audio_location(row[1])
			question['imageLocation'] = get_image_location(row[2])
			question['type'] = row[3]
			question['questionText'] = row[4]
			questions.append(question) 
		# Acquiring properties associated with each question
		for question in questions:
			question_id = question['questionID']
			# Acquiring answers
			query = f'''
					SELECT term.* FROM term, answer
					WHERE answer.questionID = {question_id}
					AND answer.termID = term.termID;
					'''
			result = get_from_db(query)
			question['answers'] = []
			# Attaching variable names to terms
			for row in result:
				term = {}
				term['termID'] = row[0]
				term['imageLocation'] = get_image_location(row[1])
				term['audioLocation'] = get_audio_location(row[2])
				term['front'] = row[3]
				term['back'] = row[4]
				term['type'] = row[5]
				term['gender'] = row[6]
				term['language'] = row[7]
				question['answers'].append(term)
		return questions


# For getting individual modules		
class Module(Resource):
	@jwt_required
	# Getting an existing module
	def get(self):
		permission = get_jwt_claims()
		if not permission or permission == "":
			return "Invalid user", 401
		
		module_id = get_module_id()
		if not module_id:
			return {'message':'Please provide the id of a module'}, 400
		# Find user's userID from jwt token
		user_id = get_jwt_identity()
		# Get all decks associated with the group
		query = f'''
				SELECT module.*, group_module.groupID FROM module 
				INNER JOIN group_module ON group_module.moduleID=module.moduleID 
				INNER JOIN group_user ON group_module.groupID = group_user.groupID 
				WHERE group_user.userID={user_id} AND module.moduleID={module_id}
				'''
		result = get_from_db(query)
		# Attaching variable names to rows
		module = {}

		if result and result[0]:
			module['moduleID'] = result[0][0]
			module['name'] = result[0][1]
			module['language'] = result[0][2]
			module['complexity'] = result[0][3]
			module['groupID'] = result[0][4]
		# Return module information
		return module

	@jwt_required
	# Creating a new module
	def post(self):
		# groupID doesn't need to be passed is superadmin is creating a new module
		# and doesn't want to attach it to any groups
		group_id = get_group_id()
		user_id = get_jwt_identity()
		permission = get_jwt_claims()
		if not permission or permission == "":
			return "Invalid user", 401

		if not group_id and permission != 'su':
			return {'message':'Please provide the id of a group'}, 400

		if permission == 'st':
			query = f"""
					SELECT accessLevel from group_user 
					WHERE userID = {user_id} AND
					groupID = {group_id}
					"""
			accessLevel = get_from_db(query)
			print(accessLevel)
			if accessLevel and accessLevel[0] and accessLevel[0][0] != 'ta':
				return "User not authorized to do this", 401
		
		# Parsing JSON
		parser = reqparse.RequestParser()
		parser.add_argument('name', type=str, required=True)
		parser.add_argument('language', type=str, required=False)
		parser.add_argument('complexity', type=int, required=False)
		data = parser.parse_args()
		name = data['name']
		if (data['language']):
			language = data['language']
		else:
			language = ''
		if (data['complexity']):
			complexity = data['complexity']
		else:
			complexity = 2
		# Posting to database
		query = f"""
				INSERT INTO module (name, language, complexity)
				VALUES ('{name}', '{language}', {complexity});
				"""
		post_to_db(query)

		# Linking the newly created module to the group associated with the groupID
		query = "SELECT MAX(moduleID) from module"
		moduleID = get_from_db(query) #ADD A CHECK TO SEE IF IT RETURNED SUCCESSFULLY

		query = f"""INSERT INTO `group_module` (`moduleID`, `groupID`) 
				VALUES ({moduleID[0][0]}, {group_id})"""
		post_to_db(query)
		
		return {'message' : 'Successfully added module and linked it to the group!'}

	@jwt_required
	def put(self):
		# groupID doesn't need to be passed if professor or superadmin is updating a module
		group_id = get_group_id()

		permission = get_jwt_claims()
		if not permission or permission == "":
			return "Invalid user", 401
		
		if permission == 'st':
			if not group_id:
				return "Pass in groupID if user is a TA for the group", 400
			query = f"""
					SELECT accessLevel from group_user 
					WHERE userID = {user_id} AND
					groupID = {group_id}
					"""
			accessLevel = get_from_db(query)
			print(accessLevel)
			if accessLevel and accessLevel[0] and accessLevel[0][0] != 'ta':
				return "User not authorized to do this", 401
		
		# Parsing JSON
		parser = reqparse.RequestParser()
		parser.add_argument('moduleID', type=int, required=True)
		parser.add_argument('name', type=str, required=True)
		parser.add_argument('language', type=str, required=True)
		parser.add_argument('complexity', type=int, required=True)
		data = parser.parse_args()
		module_id = data['moduleID']
		name = data['name']
		language = data['language']
		complexity = data['complexity']
		# Updating table
		query = f"""
				UPDATE module
				SET name = '{name}', language = '{language}', complexity = '{complexity}'
				WHERE moduleID = {module_id};
				"""
		post_to_db(query)
		return {'message' : 'Successfully updated module!'}
		

	@jwt_required
	# Deleting an existing module, requires moduleID
	def delete(self):
		# groupID only needs to be passed if the user is a TA for the group
		group_id = get_group_id()
		user_id = get_jwt_identity()
		permission = get_jwt_claims()
		if not permission or permission == "":
			return "Invalid user", 401

		if permission == 'st':
			if not group_id:
				return "Pass in groupID if user is a TA for the group", 400
			query = f"""
					SELECT accessLevel from group_user 
					WHERE userID = {user_id} AND
					groupID = {group_id}
					"""
			accessLevel = get_from_db(query)
			print(accessLevel)
			if accessLevel and accessLevel[0] and accessLevel[0][0] != 'ta':
				return "User not authorized to do this", 401
		
		module_id = get_module_id()
		if not module_id:
			return {'message' : 'Please provide the id of a module.'}

		# Determining if user is present in module's group
		query = f"SELECT groupID FROM module WHERE moduleID = {module_id};"
		result = get_from_db(query)
		if not result:
			return {'message' : 'This module id is invalid.'}
		# Failing if user is not in module's group

		# Deleting module
		query = f"DELETE FROM module WHERE moduleID = {module_id};"
		post_to_db(query)
		return {'message' : 'Successfully deleted module!'}


#  For attaching and detaching questions from modules
class AttachQuestion(Resource):
	@jwt_required
	def post(self):
		# groupID only needs to be passed if the user is a TA for the group
		group_id = get_group_id()
		user_id = get_jwt_identity()
		permission = get_jwt_claims()
		if not permission or permission == "":
			return "Invalid user", 401

		if permission == 'st':
			if not group_id:
				return "Pass in groupID if user is a TA for the group", 400
			query = f"""
					SELECT accessLevel from group_user 
					WHERE userID = {user_id} AND
					groupID = {group_id}
					"""
			accessLevel = get_from_db(query)
			print(accessLevel)
			if accessLevel and accessLevel[0] and accessLevel[0][0] != 'ta':
				return "User not authorized to do this", 401
		
		# Parsing JSON
		parser = reqparse.RequestParser()
		parser.add_argument('moduleID', type=int, required=True)
		parser.add_argument('questionID', type=int, required=False)
		data = parser.parse_args()
		module_id = data['moduleID']
		question_id = data['questionID']
		# Attaching or detaching if already attached
		attached = attach_question(module_id, question_id)
		# Response
		if attached:
			return {'message' : 'Question has been linked to module.'}, 201
		else:
			return {'message' : 'Question has been unlinked from module.'}, 200


#  For attaching and detaching terms from modules
class AttachTerm(Resource):
	@jwt_required
	def post(self):
		# groupID only needs to be passed if the user is a TA for the group
		group_id = get_group_id()
		user_id = get_jwt_identity()
		permission = get_jwt_claims()
		if not permission or permission == "":
			return "Invalid user", 401

		if permission == 'st':
			if not group_id:
				return "Pass in groupID if user is a TA for the group", 400
			query = f"""
					SELECT accessLevel from group_user 
					WHERE userID = {user_id} AND
					groupID = {group_id}
					"""
			accessLevel = get_from_db(query)
			print(accessLevel)
			if accessLevel and accessLevel[0] and accessLevel[0][0] != 'ta':
				return "User not authorized to do this", 401

		# Parsing JSON
		parser = reqparse.RequestParser()
		parser.add_argument('moduleID', type=int, required=True)
		parser.add_argument('termID', type=int, required=True)
		data = parser.parse_args()
		module_id = data['moduleID']
		term_id = data['termID']
		# Finding associated MATCH question with term
		query = f'''
				SELECT question.* FROM question, answer
				WHERE question.questionID = answer.questionID
				AND answer.termID = {term_id}
				'''
		result = get_from_db(query)
		# If term or match question does not exist
		question_id = -1
		if not result or not result[0]:
			# Determining if term exists
			result = get_from_db(f"SELECT front FROM term WHERE termID = {term_id}")
			if result:
				front = result[0]
				# Creating a new MATCH question if missing (Only occurs for terms manually created through SQL)
				post_to_db(f''' INSERT INTO question (`type`, `questionText`) VALUES ("MATCH", "What is the translation of {front}?")''')
				query = "SELECT MAX(questionID) FROM question"
				id_result = get_from_db(query)
				question_id = check_max_id(id_result) - 1
				post_to_db(f"INSERT INTO answer (`questionID`, `termID`) VALUES ({question_id}, {term_id})")
			else:
				return {'message' : 'Term does not exist or MATCH question has been deleted internally.'}, 400
		# Getting question id if question already existed
		if question_id == -1:
			question_id = result[0][0]

		# Attaching or detaching if already attached
		attached = attach_question(module_id, question_id)
		# Response
		if attached:
			return {'message' : 'Term has been linked to module.'}, 201
		else:
			return {'message' : 'Term has been unlinked from module.'}, 200


#  For attaching and detaching modules from group(s)
class AddModuleGroup(Resource):
	@jwt_required
	def post(self):
		parser = reqparse.RequestParser()
		parser.add_argument('moduleID', type=int, required=True)
		parser.add_argument('groupID', type=int, required=True)
		data = parser.parse_args()

		user_id = get_jwt_identity()
		permission = get_jwt_claims()
		if not permission or permission=="":
			return "Not a valid user", 401

		if permission == 'st':
			query = f"""
					SELECT accessLevel from group_user 
					WHERE userID = {user_id} AND
					groupID = {data['groupID']}
					"""
			accessLevel = get_from_db(query)
			print(accessLevel)
			if accessLevel and accessLevel[0] and accessLevel[0][0] != 'ta':
				return "User not authorized to do this", 401
		try:
			conn = mysql.connect()
			cursor = conn.cursor()

			query = f"""
					SELECT 1 FROM `group_module` WHERE moduleID = {data['moduleID']}
					AND groupID = {data['groupID']}
					"""
			exisistingRecord = get_from_db(query, None, conn, cursor)

			# They module is already in the group, so unlink them
			if exisistingRecord and exisistingRecord[0]:
				deleteQuery = f"""
							  DELETE from `group_module` WHERE moduleID = {data['moduleID']}
							  AND groupID = {data['groupID']}
							  """
				post_to_db(deleteQuery, None, conn, cursor)
				raise ReturnSuccess("Successfully unlinked them", 200)
			
			# They aren't already linked so link them
			else:
				insertQuery = f"""
							  INSERT INTO `group_module` (`moduleID`, `groupID`)
							  VALUES ({data['moduleID']}, {data['groupID']})	
							  """
				post_to_db(insertQuery, None, conn, cursor)
				raise ReturnSuccess("Successfully added module to group", 200)
			
			raise CustomException("Something went wrong when trying to un/link the module to the group", 500)
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