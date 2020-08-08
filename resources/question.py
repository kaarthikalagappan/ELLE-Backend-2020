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
from werkzeug.utils import secure_filename
from flaskext.mysql import MySQL
from config import (
    IMAGE_EXTENSIONS, AUDIO_EXTENSIONS, TEMP_DELETE_FOLDER,
    TEMP_UPLOAD_FOLDER, IMG_UPLOAD_FOLDER, AUD_UPLOAD_FOLDER,
    IMG_RETRIEVE_FOLDER, AUD_RETRIEVE_FOLDER
    )
from db import mysql
from db_utils import *
from utils import *
import json
import datetime
import time

DEBUG = True


class CustomException(Exception):
    pass


class QuestionsException(Exception):
    def __init__(self, msg, returnCode):
        # Error message is stored formatted in msg and response code stored in returnCode
        self.msg = errorMessage(msg, DEBUG)
        self.returnCode = returnCode


class ReturnSuccess(Exception):
    def __init__(self, msg, returnCode):
        # Message is stored formatted in msg and response code stored in returnCode
        if isinstance(msg, str):
            self.msg = returnMessage(msg, DEBUG)
        else:
            self.msg = msg
        self.returnCode = returnCode

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

#REMOVE THIS METHOD AS DELETING ANSWER WILL BE HANDLED WITHIN MODIFY QUESTION IN THE FUTURE
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
        parser = reqparse.RequestParser()
        parser.add_argument('questionID',
		                          type=str,
		                          required=True,
		                          )
        parser.add_argument('questionText',
		                          type=str,
		                          required=True,
		                          )
        parser.add_argument('type',
		                          type=str,
		                          required=True,
		                          )
        parser.add_argument('removeAudio',
		                          type=str,
		                          required=False,
		                          )
        parser.add_argument('removeImage',
		                          type=str,
		                          required=False,
		                          )
        data = parser.parse_args()

        data['imageID'] = None
        data['audioID'] = None

        maxID = -1

        user_id = get_jwt_identity()
        permission, valid_user = getUser(user_id)

        if not valid_user:
            return errorMessage("Not a valid user!"), 401

        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            #If an image was provided to upload
            if 'image' in request.files:
                if DEBUG:
                    print("Found image to upload, uploading them")
                    print(request.files['image'])

                #if data['imageID'] already has a value, then we have already uploaded an image
                if data['imageID'] is not None:
                        raise QuestionsException("Uploading two images, can only upload one per question", 403)

                dateTime = time.strftime("%d%m%y%H%M%S")

                file = request.files['image']
                if not file:
                    raise QuestionsException("Image file not recieved properly", 500)

                filename, extension = os.path.splitext(file.filename)
                filename = secure_filename(filename) + str(dateTime)
                fullFileName = str(filename) + str(extension)

                #making sure the passed in image has an acceptable extension before moving forward
                if extension[1:] in IMAGE_EXTENSIONS:
                    #saving the image to a temporary folder
                    file.save(cross_plat_path(TEMP_UPLOAD_FOLDER + fullFileName))

                    if DEBUG:
                        print("Uploading image: " + fullFileName)

                    query = "INSERT INTO image (imageLocation) VALUES (%s)"
                    post_to_db(query, fullFileName, conn, cursor)

                    #moving the image to the Images folder upon successfully creating a record
                    os.rename(cross_plat_path(TEMP_UPLOAD_FOLDER + fullFileName), cross_plat_path(IMG_UPLOAD_FOLDER + fullFileName))

                    #get the inserted image's imageID
                    query = "SELECT imageID from image WHERE imageLocation = %s"
                    imageID = get_from_db(query, fullFileName, conn, cursor)
                    data['imageID'] = imageID[0][0]
                else:
                    raise QuestionsException("File format of " + filename + extension + " is not supported. \
                            Please upload an image format of jpeg, jpg, or png format.", 415)

            if 'audio' in request.files:
                if DEBUG:
                    print("Found audio to upload, uploading them")
                    print(request.files['audio'])

                #if data['audioID'] already has a value, then we have already uploaded an audio            
                if data['audioID'] is not None:
                            raise QuestionsException("Uploading two audio files, can only upload one per question", 403)

                dateTime = time.strftime("%d%m%y%H%M%S")

                file = request.files['audio']
                if not file:
                    raise QuestionsException("Audio file not recieved properly", 500)

                filename, extension = os.path.splitext(file.filename)
                filename = secure_filename(filename) + str(dateTime)
                fullFileName = str(filename) + str(extension)

                if extension[1:] in AUDIO_EXTENSIONS:
                    #saving the audio to a temporary folder
                    file.save(cross_plat_path(TEMP_UPLOAD_FOLDER + fullFileName))

                    if DEBUG:
                        print("Uploading audio: " + fullFileName)

                    query = "INSERT INTO audio (audioLocation) VALUES (%s)"
                    post_to_db(query, fullFileName, conn, cursor)

                    #moving the audio to the Audio folder upon successfully creating a record
                    os.rename(cross_plat_path(TEMP_UPLOAD_FOLDER + fullFileName), cross_plat_path(AUD_UPLOAD_FOLDER + fullFileName))

                    #get the inserted audio's audioID
                    query = "SELECT audioID from audio WHERE audioLocation = %s"
                    audioID = get_from_db(query, str(fullFileName), conn, cursor)
                    data['audioID'] = audioID[0][0]
                else:
                    raise QuestionsException("File format of " + str(filename) + str(extension) + " is not supported. \
                            Please upload an audio of format of wav, ogg, or mp3", 415)

            # Modify an existing existing
            # 4 cases: there are new file in only audio, new file in only image
            #          new files in both audio and image, or no new files
            if data['audioID'] is not None  and data['imageID'] is not None:
                query = "UPDATE question SET audioID = %s, imageID = %s, type = %s, questionText = %s WHERE questionID = %s"
                post_to_db(query, (data['audioID'], data['imageID'], data['type'], data['questionText'], data['questionID']), conn, cursor)
            elif data['audioID'] is None and data['imageID'] is not None:
                query = "UPDATE question SET imageID = %s, type = %s, questionText = %s WHERE questionID = %s"
                post_to_db(query, (data['imageID'], data['type'], data['questionText'], data['questionID']), conn, cursor)
            elif data['audioID'] is not None and data['imageID'] is None:
                query = "UPDATE question SET audioID = %s, type = %s, questionText = %s WHERE questionID = %s"
                post_to_db(query, (data['audioID'], data['type'], data['questionText'], data['questionID']), conn, cursor)
            else:
                query = "UPDATE question SET type = %s, questionText = %s WHERE questionID = %s"
                post_to_db(query, (data['type'], data['questionText'], data['questionID']), conn, cursor)
            
            if data['removeAudio']:
                query = "UPDATE question SET audioID = %s WHERE questionID = %s"
                post_to_db(query, (None, data['questionID']), conn, cursor)

            if data['removeImage']:
                query = "UPDATE question SET imageID = %s WHERE questionID = %s"
                post_to_db(query, (None, data['questionID']), conn, cursor)

            # Modify existing question's answers
            new_ans_list = request.form.getlist('new_answers')
            new_ans_list = json.loads(new_ans_list[0])
            query = "SELECT * FROM `answer` WHERE questionID = %s"
            result = get_from_db(query, data['questionID'], conn, cursor)
            old_ans_list = [ans[1] for ans in result]
            dif_list = list(set(old_ans_list) ^ set(new_ans_list))

            # Look through differenes between the two lists
            # If a term exists in the old_ans_list and the dif_list, that means to delete that answer
            # Otherwise add that answer
            for ans in dif_list:
                if ans in old_ans_list:
                    query = "DELETE FROM `answer` WHERE questionID = %s AND termID = %s"
                    post_to_db(query, (data['questionID'], ans), conn, cursor)
                else:
                    query = "INSERT INTO `answer` (questionID, termID) VALUES (%s, %s)"
                    post_to_db(query, (data['questionID'], ans), conn, cursor)

            term_obj_list = request.form.getlist('arr_of_terms')
            
            # Creating new terms that will be linked to the question based on the objects passed in
            for term_obj in term_obj_list:
                term_obj = json.loads(term_obj)
                for term in term_obj:
                    query = "INSERT INTO `term` (front, back, language) VALUES (%s, %s, %s)"
                    post_to_db(query, (term['front'], term['back'], term['language']), conn, cursor)
                    term_query = "SELECT MAX(termID) FROM `term`"
                    result = get_from_db(term_query, None, conn, cursor)
                    termID = check_max_id(result) - 1
                    answer_query = "INSERT INTO `answer` (questionID, termID) VALUES (%s, %s)"
                    post_to_db(answer_query, (data['questionID'], termID), conn, cursor)

                    for t in term['tags']:
                        tag_query = "SELECT * FROM `tag` WHERE termID = %s AND tagName = %s"
                        tag_result = get_from_db(tag_query, (termID, str(t).lower()), conn, cursor)
                        if not tag_result:
                            query = "INSERT INTO `tag` (termID, tagName) VALUES (%s, %s)"
                            post_to_db(query, (termID, str(t).lower()), conn, cursor)

            raise ReturnSuccess({"Message" : "Successfully modified the question", "questionID" : int(data['questionID'])}, 201)
    
        except QuestionsException as error:
            conn.rollback()
            return error.msg, error.returnCode
        except ReturnSuccess as success:
            conn.commit()
            return success.msg, success.returnCode
        except Exception as error:
            conn.rollback()
            return errorMessage(str(error), DEBUG), 500
        finally:
            if(conn.open):
                cursor.close()
                conn.close()


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
        parser = reqparse.RequestParser()
        parser.add_argument('type',
		                          type=str,
		                          required=True,
		                          )
        parser.add_argument('questionText',
		                          type=str,
		                          required=True,
		                          )
        parser.add_argument('moduleID',
                                  type=str,
                                  required=True,
                                  help="Pass in the ID of the module to which the question should be linked")
        data = parser.parse_args()

        data['imageID'] = None
        data['audioID'] = None

        maxID = -1

        user_id = get_jwt_identity()
        permission, valid_user = getUser(user_id)

        if not valid_user:
            return errorMessage("Not a valid user!"), 401

        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            #If an image was provided to upload
            if 'image' in request.files:
                if DEBUG:
                    print("Found image to upload, uploading them")
                    print(request.files['image'])

                #if data['imageID'] already has a value, then we have already uploaded an image
                if data['imageID'] is not None:
                        raise QuestionsException("Uploading two images, can only upload one per question", 403)

                dateTime = time.strftime("%d%m%y%H%M%S")

                file = request.files['image']
                if not file:
                    raise QuestionsException("Image file not recieved properly", 500)

                filename, extension = os.path.splitext(file.filename)
                filename = secure_filename(filename) + str(dateTime)
                fullFileName = str(filename) + str(extension)

                #making sure the passed in image has an acceptable extension before moving forward
                if extension[1:] in IMAGE_EXTENSIONS:
                    #saving the image to a temporary folder
                    file.save(cross_plat_path(TEMP_UPLOAD_FOLDER + fullFileName))

                    if DEBUG:
                        print("Uploading image: " + fullFileName)

                    query = "INSERT INTO image (imageLocation) VALUES (%s)"
                    post_to_db(query, fullFileName, conn, cursor)

                    #moving the image to the Images folder upon successfully creating a record
                    os.rename(cross_plat_path(TEMP_UPLOAD_FOLDER + fullFileName), cross_plat_path(IMG_UPLOAD_FOLDER + fullFileName))

                    #get the inserted image's imageID
                    query = "SELECT imageID from image WHERE imageLocation = %s"
                    imageID = get_from_db(query, fullFileName, conn, cursor)
                    data['imageID'] = imageID[0][0]
                else:
                    raise QuestionsException("File format of " + filename + extension + " is not supported. \
                            Please upload an image format of jpeg, jpg, or png format.", 415)

            if 'audio' in request.files:
                if DEBUG:
                    print("Found audio to upload, uploading them")
                    print(request.files['audio'])

                #if data['audioID'] already has a value, then we have already uploaded an audio            
                if data['audioID'] is not None:
                            raise QuestionsException("Uploading two audio files, can only upload one per question", 403)

                dateTime = time.strftime("%d%m%y%H%M%S")

                file = request.files['audio']
                if not file:
                    raise QuestionsException("Audio file not recieved properly", 500)

                filename, extension = os.path.splitext(file.filename)
                filename = secure_filename(filename) + str(dateTime)
                fullFileName = str(filename) + str(extension)

                if extension[1:] in AUDIO_EXTENSIONS:
                    #saving the audio to a temporary folder
                    file.save(cross_plat_path(TEMP_UPLOAD_FOLDER + fullFileName))

                    if DEBUG:
                        print("Uploading audio: " + fullFileName)

                    query = "INSERT INTO audio (audioLocation) VALUES (%s)"
                    post_to_db(query, fullFileName, conn, cursor)

                    #moving the audio to the Audio folder upon successfully creating a record
                    os.rename(cross_plat_path(TEMP_UPLOAD_FOLDER + fullFileName), cross_plat_path(AUD_UPLOAD_FOLDER + fullFileName))

                    #get the inserted audio's audioID
                    query = "SELECT audioID from audio WHERE audioLocation = %s"
                    audioID = get_from_db(query, str(fullFileName), conn, cursor)
                    data['audioID'] = audioID[0][0]
                else:
                    raise QuestionsException("File format of " + str(filename) + str(extension) + " is not supported. \
                            Please upload an audio of format of wav, ogg, or mp3", 415)

            # Add new question   
            if DEBUG:
                print("Adding a new question")
                
            if permission != 'ad':
                raise QuestionsException("Not an admin to add questions", 401)

            if DEBUG:
                print("Adding the question with questionID: " + str(maxID))

            query = "INSERT INTO question (`audioID`, `imageID`, `type`, `questionText`) VALUES (%s, %s, %s, %s)"
            post_to_db(query, (data['audioID'], data['imageID'], data['type'], data['questionText']), conn, cursor)

            query = "SELECT MAX(questionID) FROM question"
            result = get_from_db(query, None, conn, cursor)
            maxID = check_max_id(result) - 1

            if data['moduleID']:
                query = "INSERT INTO `module_question` (`moduleID`, `questionID`) VALUES (%s, %s)"
                post_to_db(query, (data['moduleID'], str(maxID)), conn, cursor)
            
            raise ReturnSuccess({"Message" : "Successfully created a question", "questionID" : int(maxID)}, 201)
    
        except QuestionsException as error:
            conn.rollback()
            return error.msg, error.returnCode
        except ReturnSuccess as success:
            conn.commit()
            return success.msg, success.returnCode
        except Exception as error:
            conn.rollback()
            return errorMessage(str(error), DEBUG), 500
        finally:
            if(conn.open):
                cursor.close()
                conn.close()

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
