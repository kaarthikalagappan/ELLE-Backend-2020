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

IMG_RETRIEVE_FOLDER = '/Images/'
AUD_RETRIEVE_FOLDER = '/Audios/'

class Answer(Resource):
    #adds an answer to the database table
    @jwt_required
    def post(self):
        answer_parser = reqparse.RequestParser()
        answer_parser.add_argument('questionID',
		                          type=str,
		                          required=False,
		                          )
        answer_parser.add_argument('termID',
		                          type=str,
		                          required=True,
		                          )
        data = answer_parser.parse_args()
        query = "INSERT INTO answer (`questionID`, `termID`) VALUES (%s, %s)"
        post_to_db(query, (int(data['questionID']), int(data['termID'])))
        return {'message':'Successfully added answer!'}, 201


class DeleteAnswer(Resource):
    #adds an answer to the database table
    @jwt_required
    def delete(self):
        answer_parser = reqparse.RequestParser()
        answer_parser.add_argument('questionID',
		                          type=str,
		                          required=True,
		                          )
        answer_parser.add_argument('termID',
		                          type=str,
		                          required=True,
		                          )
        data = answer_parser.parse_args()
        query = "DELETE FROM `answer` WHERE `questionID`=" + str(data['questionID']) + " AND `termID`=" + str(data['termID'])
        post_to_db(query)
        return{'message':'Deleted Answer'},201


#modifies a question and everything associated with it
class Modify(Resource):
    @jwt_required
    def post(self):
        question_parser = reqparse.RequestParser()
        question_parser.add_argument('questionID',
		                          type=str,
		                          required=True,
		                          )
        question_parser.add_argument('questionText',
		                          type=str,
		                          required=True,
		                          )
        question_parser.add_argument('imageID',
		                          type=str,
		                          required=True,
		                          )
        question_parser.add_argument('audioID',
		                          type=str,
		                          required=True,
		                          )
        question_parser.add_argument('type',
		                          type=str,
		                          required=True,
		                          )
        data = question_parser.parse_args()

        # differCheck = False
        # query = "SELECT * FROM module_question WHERE questionID =%s"
        # result = get_from_db(query, data['questionID'])
        # previousID = -1
        # #CHECK TO SEE IF QUESTION IS ASSOCIATED WITH MORE THAN ONE MODULE
        # for row in result:
        #     if (row[0] != previousID):
        #         if previousID == -1:
        #             pass
        #         else:
        #             differCheck = True
        #             break;
        #     previousID = row[0]
        # if differCheck:
        #     #SO WE NEED TO FIND THE MODULE ASSOCIATED WITH GROUP NOW
        #     query = "SELECT * FROM module WHERE groupID=%s"
        #     result = get_from_db(query, data['groupID'])
        #     for row in result:
        #     #AT THIS POINT WE KNOW THE MODULEID THAT WE NEED TO CHANGE THIS QUESTION FOR SO WE DUPLICATE THE # QUESTION
        #     #AND UPDATE THE QUESTION AT THIS POINT RETURNING THE NEW QUESTIONID FOR THE MODULE_QUESTION TABLE
        #         if row[1] == data['groupID']:
        #             moduleIDToChange = row[0]


        #     #GET QUESTION INFO TO DUPLICATE
        #     query = "SELECT `questionID`, `audioID`, `imageID`, `type`, `questionText` FROM `question` WHERE `questionID`=%s"
        #     result = get_from_db(query, data['questionID'])
        #     questionObject = {}
        #     for row in result:
        #         questionObject['audioID'] = row[1]
        #         questionObject['imageID'] = row[2]
        #         questionObject['type'] = row[3]
        #         questionObject['questionText'] = row[4]
        #     questionObject['questionText'] = data['questionText']
        #     questionObject['audioID'] = data['audioID']
        #     questionObject['imageID'] = data['imageID']
        #     questionObject['type'] = data['type']

        #     #MAKE A NEW QUESTION WITH THE NEW FIELDS
        #     query = "INSERT INTO question (`audioID`, `imageID`, `type`, `questionText`) VALUES (%s, %s, %s, %s)"
        #     post_to_db(query, (int(questionObject['audioID']), int(questionObject['imageID']),questionObject['type'], questionObject['questionText']))

        #     #NOW GET THE NEW QUESTIONID
        #     query = "SELECT MAX(`questionID`) FROM `question`"
        #     result = get_from_db(query)
        #     for row in result:
        #         newQuestionID=row[0]

            # #UPDATE THE PREVIOUS ID IN THE MODULE_QUESTION
            # query = "UPDATE `module_question` set `questionID=%s` WHERE `moduleID`=%s"
            # post_to_db(query, (newQuestionID,moduleIDToChange))

            # return {newQuestionID},201

        # else:
            #WE KNOW THAT THE QUESTION IS ONLY ASSOCIATED WITH ONE MODULEID SO WE CAN JUST UPDATE IT AS IS, AND NOTHING
            #NEED TO CHANGE
        query = "UPDATE `question` SET `questionText`=%s, `type`=%s, `audioID`=%s, `imageID=%s` WHERE `questionID`=%s"
        post_to_db(query, (data['questionText'], data['type'], data['audioID'], data['imageID']))

        return {'message':'Successfully modified question!'}, 201




class SearchType(Resource):
    @jwt_required
    def get(self):
        print(request.values)
        question_parser = reqparse.RequestParser()
        question_parser.add_argument('type',
		                          type=str,
		                          required=False,
		                          )
        question_parser.add_argument('language',
		                          type=str,
                                  help="Please provide language to which to search through",
		                          required=True,
		                          )
        data = question_parser.parse_args()
        if data['type']:
            query = "SELECT DISTINCT question.* FROM `question` INNER JOIN answer on answer.questionID = question.questionID \
                    INNER JOIN term on term.termID = answer.termID and term.language = %s WHERE question.type = %s"
            result = get_from_db(query, (data['language'], data['type']))
        else:
            query = "SELECT DISTINCT question.* FROM `question` INNER JOIN answer on answer.questionID = question.questionID \
                    INNER JOIN term on term.termID = answer.termID and term.language = %s"
            result = get_from_db(query, (data['language']))
        finalQuestionObject = []
        for row in result:
            newQuestionObject = {}
            newQuestionObject['questionID'] = row[0]
            newQuestionObject['audioID'] = row[1]
            newQuestionObject['imageID'] = row[2]
            newQuestionObject['type'] = row[3]
            newQuestionObject['questionText'] = row[4]

            if newQuestionObject['imageID']:
                query = "SELECT * FROM image WHERE imageID = "+ str(newQuestionObject['imageID'])
                result = get_from_db(query)
                for row in result:
                    newQuestionObject['imageLocation'] = IMG_RETRIEVE_FOLDER + row[1] if row and row[1] else None

            if newQuestionObject['audioID']:
                query = "SELECT * FROM audio WHERE audioID = "+ str(newQuestionObject['audioID'])
                result = get_from_db(query)
                for row in result:
                    newQuestionObject['audioLocation'] = AUD_RETRIEVE_FOLDER + row[1] if row and row[1] else None

            query = "SELECT * FROM answer WHERE questionID = "+ str(newQuestionObject['questionID'])
            result = get_from_db(query)
            newQuestionObject['answers'] = []
            for row in result:
                newQuestionObject['answers'].append(row[1])
            finalQuestionObject.append(newQuestionObject)
        return finalQuestionObject


class SearchText(Resource):
    @jwt_required
    def get(self):
        question_parser = reqparse.RequestParser()
        question_parser.add_argument('questionText',
		                          type=str,
		                          required=True,
		                          )
        question_parser.add_argument('language',
		                          type=str,
                                  help="Please provide language to which to search through",
		                          required=True,
		                          )
        data = question_parser.parse_args()
        query = "SELECT DISTINCT question.* FROM `question` INNER JOIN answer on answer.questionID = question.questionID \
                INNER JOIN term on term.termID = answer.termID and term.language = %s WHERE question.questionText = %s"
        result = get_from_db(query, (data['language'], data['questionText']))
        finalQuestionObject = []
        for row in result:
            newQuestionObject = {}
            newQuestionObject['questionID'] = row[0]
            newQuestionObject['audioID'] = row[1]
            newQuestionObject['imageID'] = row[2]
            newQuestionObject['type'] = row[3]
            newQuestionObject['questionText'] = row[4]

            if newQuestionObject['imageID']:
                query = "SELECT * FROM image WHERE imageID = "+ str(newQuestionObject['imageID'])
                result = get_from_db(query)
                for row in result:
                    newQuestionObject['imageLocation'] = IMG_RETRIEVE_FOLDER + row[1] if row and row[1] else None

            if newQuestionObject['audioID']:
                query = "SELECT * FROM audio WHERE audioID = "+ str(newQuestionObject['audioID'])
                result = get_from_db(query)
                for row in result:
                    newQuestionObject['audioLocation'] = AUD_RETRIEVE_FOLDER + row[1] if row and row[1] else None

            query = "SELECT * FROM answer WHERE questionID = "+ str(newQuestionObject['questionID'])
            result = get_from_db(query)
            newQuestionObject['answers'] = []
            for row in result:
                newQuestionObject['answers'].append(row[1])
            finalQuestionObject.append(newQuestionObject)
        return finalQuestionObject



class DeleteQuestion(Resource):
    #deletes a question
    @jwt_required
    def delete(self):
        question_parser = reqparse.RequestParser()
        question_parser.add_argument('questionID',
		                          type=str,
		                          required=True,
		                          )
        data = question_parser.parse_args()
        if (find_question(int(data['questionID']))):
            query = "DELETE FROM `answer` WHERE `questionID` ="+ str(data['questionID'])
            delete_from_db(query)
            query = "DELETE FROM `question` WHERE `questionID`="+ str(data['questionID'])
            delete_from_db(query)
            return {'message':'Successfully deleted question and answer set!'}, 201


        return {'message':'No question with that ID exist!'}, 201


class Question(Resource):
    #adds a question to the database table
    @jwt_required
    def post(self):
        question_parser = reqparse.RequestParser()
        question_parser.add_argument('audioID',
		                          type=str,
		                          required=False,
		                          )
        question_parser.add_argument('imageID',
		                          type=str,
		                          required=False,
		                          )
        question_parser.add_argument('type',
		                          type=str,
		                          required=True,
		                          )
        question_parser.add_argument('questionText',
		                          type=str,
		                          required=True,
		                          )
        question_parser.add_argument('moduleID',
                                  type=str,
                                  required=False,
                                  help="Pass in the ID of the module to which the question should be linked")
        data = question_parser.parse_args()
        query = "INSERT INTO question (`audioID`, `imageID`, `type`, `questionText`) VALUES (%s, %s, %s, %s)"
        post_to_db(query, (data['audioID'], data['imageID'], data['type'], data['questionText']))

        query = "SELECT MAX(questionID) FROM question"
        result = get_from_db(query, None)
        maxID = check_max_id(result) - 1

        #CHANGE: moduleID should be required in the future
        if data['moduleID']:
            query = "INSERT INTO `module_question` (`moduleID`, `questionID`) VALUES (%s, %s)"
            post_to_db(query, (data['moduleID'], str(maxID)))

        return {'message':'Successfully added question and linked it to a module!', 'questionID' : str(maxID)}, 201


    #returns the question specified with the ID and returns the question with of properties assoicatied with that question
    @jwt_required
    def get(self):
        question_parser = reqparse.RequestParser()
        question_parser.add_argument('questionID',
		                          type=int,
		                          required=False,
		                          )
        data = question_parser.parse_args()

        if (find_question(data['questionID'])):

            query = "SELECT * FROM question WHERE questionID = "+ str(data['questionID'])
            result = get_from_db(query)
            newQuestionObject = {}
            for row in result:
                newQuestionObject['questionID'] = row[0]
                newQuestionObject['audioID'] = row[1]
                newQuestionObject['imageID'] = row[2]
                newQuestionObject['type'] = row[3]
                newQuestionObject['questionText'] = row[4]

            query = "SELECT * FROM image WHERE imageID = "+ str(newQuestionObject['imageID'])
            result = get_from_db(query)
            for row in result:
                newQuestionObject['imageLocation'] = IMG_RETRIEVE_FOLDER + row[1] if row and row[1] else None

            query = "SELECT * FROM audio WHERE audioID = "+ str(newQuestionObject['audioID'])
            result = get_from_db(query)
            for row in result:
                newQuestionObject['audioLocation'] = AUD_RETRIEVE_FOLDER + row[1] if row and row[1] else None

            query = "SELECT * FROM answer WHERE questionID = "+ str(newQuestionObject['questionID'])
            result = get_from_db(query)
            newQuestionObject['answers'] = []
            for row in result:
                newQuestionObject['answers'].append(row[1])
            return newQuestionObject
        else:
            return {'message':'Question does not exist!'}, 404





def find_question(questionID):
	query = "SELECT * FROM question WHERE questionID=%s"
	result = get_from_db(query, (questionID,))
	for row in result:
		if row[0] == questionID:
			return True
	return False
