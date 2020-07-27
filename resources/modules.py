# -*- encoding: utf-8 -*-

from flask import send_file, request, json
from flask_restful import Resource, reqparse
from flask_jwt_extended import jwt_required, get_jwt_identity, get_raw_jwt
from db import mysql
from db_utils import *
from utils import *
import os.path

IMG_RETRIEVE_FOLDER = '/Images/'
AUD_RETRIEVE_FOLDER = '/Audios/'

# Gets the group associated with the current user
def get_user_group():
	user_id = get_jwt_identity()
	query = f"SELECT groupID FROM group_user WHERE userID = {user_id};"
	result = get_from_db(query)
	# Return -1 if user is not in a group
	if (result):
		return result[0][0]
	else:
		return -1

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
		query = f'''DELETE FROM module_questions
				WHERE moduleID = {module_id} AND questionID = {question_id}'''
		post_to_db(query)
		return False

# For acquiring all modules in a group
class Modules(Resource):

	@jwt_required
	# Get modules associated with user's group
	def get(self):
		# Find user's group
		group_id = get_user_group()
		# Get all modules associated with the group
		query = f"SELECT * FROM module WHERE groupID = {group_id};"
		result = get_from_db(query)
		# Attaching variable names to rows
		modules = []
		for row in result:
			module = {}
			module['moduleID'] = row[0]
			module['groupID'] = row[1]
			module['name'] = row[2]
			module['language'] = row[3]
			module['complexity'] = row[4]
			modules.append(module) 
		# Return module information
		return modules

# For acquiring the associated questions and answers with a module
class ModuleQuestions(Resource):

	# Get a list of question objects, which each contain a list of terms functioning as their answers
	# Requires moduleID
	def post(self):
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
		module_id = get_module_id()
		if not module_id:
			return {'message':'Please provide the id of a module'}, 400
		# Find user's group
		group_id = get_user_group()
		# Get all decks associated with the group
		query = f'''
				SELECT * FROM module
				WHERE groupID = {group_id}
				AND moduleID = {module_id};
				'''
		result = get_from_db(query)
		# Attaching variable names to rows
		module = {}
		module['moduleID'] = result[0][0]
		module['groupID'] = result[0][1]
		module['name'] = result[0][2]
		module['language'] = result[0][3]
		module['complexity'] = result[0][4]
		# Return module information
		return module

	@jwt_required
	# Creating a new module
	def post(self):
		group_id = get_user_group()
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
		query = f'''
				INSERT INTO module (groupID, name, language, complexity)
				VALUES ({group_id}, '{name}', '{language}', {complexity});
				'''
		post_to_db(query)
		return {'message' : 'Successfully added module!'}

	@jwt_required
	def put(self):
		group_id = get_user_group()
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
		query = f'''
				UPDATE module
				SET name = '{name}', language = '{language}', complexity = '{complexity}'
				WHERE moduleID = {module_id};
				'''
		post_to_db(query)
		return {'message' : 'Successfully updated module!'}
		

	@jwt_required
	# Deleting an existing module, requires moduleID
	def delete(self):
		module_id = get_module_id()
		if not module_id:
			return {'message' : 'Please provide the id of a module.'}
		group_id = get_user_group()
		# Determining if user is present in module's group
		query = f"SELECT groupID FROM module WHERE moduleID = {module_id};"
		result = get_from_db(query)
		if not result:
			return {'message' : 'This module id is invalid.'}
		# Failing if user is not in module's group
		if group_id != result[0][0]:
			return {'message' : 'You are not authorized to delete this module.'}
		# Deleting module
		query = f"DELETE FROM module WHERE moduleID = {module_id};"
		post_to_db(query)
		return {'message' : 'Successfully deleted module!'}


#  For attaching and detaching questions from modules
class AttachQuestion(Resource):
	@jwt_required
	def post(self):
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
		if not result or not result[0]:
			return {'message' : 'Term does not exist or MATCH question has been deleted internally.'}, 400
		question_id = result[0][0]

		# Attaching or detaching if already attached
		attached = attach_question(module_id, question_id)
		# Response
		if attached:
			return {'message' : 'Term has been linked to module.'}, 201
		else:
			return {'message' : 'Term has been unlinked from module.'}, 200