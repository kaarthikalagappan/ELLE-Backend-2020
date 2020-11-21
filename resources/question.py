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
from exceptions_util import *
import json
import datetime
import time

DEBUG = True

class Answer(Resource):
    #adds an answer to the database table
    @jwt_required
    def post(self):
        data = {}
        data['questionID'] = getParameter("questionID", str, False, "")
        data['termID'] = getParameter("termID", str, True, "")
        data['groupID'] = getParameter("groupID", str, False, "groupID")

        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return errorMessage("Invalid user"), 401

        if permission == 'st' and not is_ta(user_id, data['groupID']):
            return errorMessage("User not authorized to      answers."), 400
        
        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            query = f"INSERT INTO answer (`questionID`, `termID`) VALUES (%s, %s)"
            post_to_db(query, (int(data['questionID']), int(data['termID'])), conn, cursor)

            raise ReturnSuccess({'message':'Successfully added answer!'}, 201)
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


#REMOVE THIS METHOD AS DELETING ANSWER WILL BE HANDLED WITHIN MODIFY QUESTION IN THE FUTURE
class DeleteAnswer(Resource):
    #adds an answer to the database table
    @jwt_required
    def delete(self):
        data = {}
        data['questionID'] = getParameter("questionID", str, True, "")
        data['termID'] = getParameter("termID", str, True, "")
        data['groupID'] = getParameter("groupID", str, False, "groupID is required if student is TA")

        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return errorMessage("Invalid user"), 401

        if permission == 'st' and not is_ta(user_id, data['groupID']):
            return errorMessagE("User not authorized to delete answers."), 400
        
        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            query = f"DELETE FROM `answer` WHERE `questionID`= {data['questionID']} AND `termID` = {data['termID']}" 
            post_to_db(query, None, conn, cursor)

            raise ReturnSuccess({'message':'Deleted Answer'}, 201)
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


#modifies a question and everything associated with it
class Modify(Resource):
    @jwt_required
    def post(self):
        data = {}
        data['questionID'] = getParameter("questionID", str, True, "")
        data['questionText'] = getParameter("questionText", str, True, "")
        data['type'] = getParameter("type", str, True, "")
        data['removeAudio'] = getParameter("removeAudio", str, False, "")
        data['removeImage'] = getParameter("removeImage", str, False, "")
        data['groupID'] = getParameter("groupID", str, False, "groupID is required if student is TA")
        data['imageID'] = None
        data['audioID'] = None

        maxID = -1

        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return errorMessage("Invalid user"), 401

        if permission == 'st' and not is_ta(user_id, data['groupID']):
            return errorMessage("User not authorized to modify questions."), 400

        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            #If an image was provided to upload
            if 'image' in request.files:
                #if data['imageID'] already has a value, then we have already uploaded an image
                if data['imageID'] is not None:
                        raise CustomException("Uploading two images, can only upload one per question", 403)

                dateTime = time.strftime("%d%m%y%H%M%S")

                file = request.files['image']
                if not file:
                    raise CustomException("Image file not recieved properly", 500)

                filename, extension = os.path.splitext(file.filename)
                filename = secure_filename(filename) + str(dateTime)
                full_file_name = str(filename) + str(extension)

                #making sure the passed in image has an acceptable extension before moving forward
                if extension[1:] in IMAGE_EXTENSIONS:
                    #saving the image to a temporary folder
                    file.save(cross_plat_path(TEMP_UPLOAD_FOLDER + full_file_name))

                    query = f"INSERT INTO image (imageLocation) VALUES ({full_file_name})"
                    post_to_db(query, None, conn, cursor)

                    #moving the image to the Images folder upon successfully creating a record
                    os.rename(cross_plat_path(TEMP_UPLOAD_FOLDER + full_file_name), cross_plat_path(IMG_UPLOAD_FOLDER + full_file_name))

                    #get the inserted image's imageID
                    query = f"SELECT imageID from image WHERE imageLocation = {full_file_name}"
                    imageID = get_from_db(query, None, conn, cursor)
                    data['imageID'] = imageID[0][0]
                else:
                    raise CustomException("File format of " + filename + extension + " is not supported. \
                            Please upload an image format of jpeg, jpg, or png format.", 415)

            if 'audio' in request.files:
                #if data['audioID'] already has a value, then we have already uploaded an audio            
                if data['audioID'] is not None:
                    raise CustomException("Uploading two audio files, can only upload one per question", 403)

                dateTime = time.strftime("%d%m%y%H%M%S")

                file = request.files['audio']
                if not file:
                    raise CustomException("Audio file not recieved properly", 500)

                filename, extension = os.path.splitext(file.filename)
                filename = secure_filename(filename) + str(dateTime)
                full_file_name = str(filename) + str(extension)

                if extension[1:] in AUDIO_EXTENSIONS:
                    #saving the audio to a temporary folder
                    file.save(cross_plat_path(TEMP_UPLOAD_FOLDER + full_file_name))

                    query = f"INSERT INTO audio (audioLocation) VALUES ({full_file_name})"
                    post_to_db(query, None, conn, cursor)

                    #moving the audio to the Audio folder upon successfully creating a record
                    os.rename(cross_plat_path(TEMP_UPLOAD_FOLDER + full_file_name), cross_plat_path(AUD_UPLOAD_FOLDER + full_file_name))

                    #get the inserted audio's audioID
                    query = f"SELECT audioID from audio WHERE audioLocation = {str(full_file_name)}"
                    audioID = get_from_db(query, None, conn, cursor)
                    data['audioID'] = audioID[0][0]
                else:
                    raise CustomException("File format of " + str(filename) + str(extension) + " is not supported. \
                            Please upload an audio of format of wav, ogg, or mp3", 415)

            # Modify an existing existing
            # 4 cases: there are new file in only audio, new file in only image
            #          new files in both audio and image, or no new files
            if data['audioID'] is not None  and data['imageID'] is not None:
                query = f"UPDATE question SET audioID = {data['audioID']}, imageID = {data['imageID']}, type = {data['type']}, questionText = {data['questionText']} WHERE questionID = {data['questionID']}"
                post_to_db(query, None, conn, cursor)
            elif data['audioID'] is None and data['imageID'] is not None:
                query = f"UPDATE question SET imageID = {data['imageID']}, type = {data['type']}, questionText = {data['questionText']} WHERE questionID = {data['questionID']}"
                post_to_db(query, None, conn, cursor)
            elif data['audioID'] is not None and data['imageID'] is None:
                query = f"UPDATE question SET audioID = {data['audioID']}, type = {data['type']}, questionText = {data['questionText']} WHERE questionID = {data['questionID']}"
                post_to_db(query, None, conn, cursor)
            else:
                query = f"UPDATE question SET type = {data['type']}, questionText = {data['questionText']} WHERE questionID = {data['questionID']}"
                post_to_db(query, None, conn, cursor)
            
            if data['removeAudio']:
                query = "UPDATE question SET audioID = %s WHERE questionID = %s"
                post_to_db(query, (None, data['questionID']), conn, cursor)

            if data['removeImage']:
                query = "UPDATE question SET imageID = %s WHERE questionID = %s"
                post_to_db(query, (None, data['questionID']), conn, cursor)

            # Modify existing question's answers
            new_ans_list = request.form.getlist('new_answers')
            new_ans_list = json.loads(new_ans_list[0])
            query = f"SELECT * FROM `answer` WHERE questionID = {data['questionID']}"
            result = get_from_db(query, None, conn, cursor)
            old_ans_list = [ans[1] for ans in result]
            dif_list = list(set(old_ans_list) ^ set(new_ans_list))

            # Look through differenes between the two lists
            # If a term exists in the old_ans_list and the dif_list, that means to delete that answer
            # Otherwise add that answer
            for ans in dif_list:
                if ans in old_ans_list:
                    query = f"DELETE FROM `answer` WHERE questionID = {data['questionID']} AND termID = {ans}"
                    post_to_db(query, None, conn, cursor)
                else:
                    query = f"INSERT INTO `answer` (questionID, termID) VALUES ({data['questionID']}, {ans})"
                    post_to_db(query, None, conn, cursor)

            term_obj_list = request.form.getlist('arr_of_terms')
            
            # Creating new terms that will be linked to the question based on the objects passed in
            for term_obj in term_obj_list:
                term_obj = json.loads(term_obj)
                for term in term_obj:
                    query = f"INSERT INTO `term` (front, back, language) VALUES ({term['front']}, {term['back']}, {term['language']})"
                    post_to_db(query, None, conn, cursor)
                    term_query = "SELECT MAX(termID) FROM `term`"
                    result = get_from_db(term_query, None, conn, cursor)
                    termID = check_max_id(result) - 1
                    answer_query = "INSERT INTO `answer` (questionID, termID) VALUES (%s, %s)"
                    post_to_db(answer_query, (data['questionID'], termID), conn, cursor)

                    for t in term['tags']:
                        tag_query = f"SELECT * FROM `tag` WHERE termID = {termID} AND tagName = {str(t).lower()}"
                        tag_result = get_from_db(tag_query, None, conn, cursor)
                        if not tag_result:
                            query = f"INSERT INTO `tag` (termID, tagName) VALUES ({termID}, {str(t).lower()})"
                            post_to_db(query, None, conn, cursor)

            raise ReturnSuccess({"Message" : "Successfully modified the question", "questionID" : int(data['questionID'])}, 201)
        except CustomException as error:
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
        data = {}
        data['type'] = getParameter("type", str, False, "")
        data['language'] = getParameter("language", str, True, "Please provide a language to which to search through")
    
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return errorMessage("Invalid user"), 401

        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            if data['type']:
                query = f"SELECT DISTINCT `question`.* FROM `question` INNER JOIN answer on `answer`.`questionID` = `question`.`questionID` \
                        INNER JOIN `term` on `term`.`termID` = `answer`.`termID` and `term`.`language` = '{data['language']}' WHERE `question`.`type` = '{data['type']}'"
                result = get_from_db(query, None, conn, cursor)
            else:
                query = f"SELECT DISTINCT question.* FROM `question` INNER JOIN answer on answer.questionID = question.questionID \
                        INNER JOIN term on term.termID = answer.termID and term.language = '{data['language']}'"
                result = get_from_db(query, None, conn, cursor)

            final_question_object = []
            for row in result:
                new_question_object = {}
                new_question_object['questionID'] = row[0]
                new_question_object['audioID'] = row[1]
                new_question_object['imageID'] = row[2]
                new_question_object['type'] = row[3]
                new_question_object['questionText'] = row[4]

                if new_question_object['imageID']:
                    query = f"SELECT * FROM image WHERE imageID = {new_question_object['imageID']}"
                    result = get_from_db(query, None, conn, cursor)
                    for row in result:
                        new_question_object['imageLocation'] = IMG_RETRIEVE_FOLDER + row[1] if row and row[1] else None

                if new_question_object['audioID']:
                    query = f"SELECT * FROM audio WHERE audioID = {new_question_object['audioID']}"
                    result = get_from_db(query, None, conn, cursor)
                    for row in result:
                        new_question_object['audioLocation'] = AUD_RETRIEVE_FOLDER + row[1] if row and row[1] else None

                query = f"SELECT * FROM answer WHERE questionID = {new_question_object['questionID']}"
                result = get_from_db(query, None, conn, cursor)
                new_question_object['answers'] = []
                for row in result:
                    new_question_object['answers'].append(row[1])
                final_question_object.append(new_question_object)
            raise ReturnSuccess(final_question_object, 200)
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


class SearchText(Resource):
    @jwt_required
    def get(self):
        data = {}
        data['questionText'] = getParameter("questionText", str, True, "")
        data['language'] = getParameter("language", str, True, "Please provide a language to which to search thorugh")

        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return errorMessage("Invalid user"), 401

        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            query = f"SELECT DISTINCT `question`.* FROM `question` INNER JOIN `answer` on `answer`.`questionID` = `question`.`questionID` \
                INNER JOIN `term` on `term`.`termID` = `answer`.`termID` and `term`.`language` = '{data['language']}' WHERE `question`.`questionText` = '{data['questionText']}'"
            result = get_from_db(query, None, conn, cursor)
            final_question_object = []
            for row in result:
                new_question_object = {}
                new_question_object['questionID'] = row[0]
                new_question_object['audioID'] = row[1]
                new_question_object['imageID'] = row[2]
                new_question_object['type'] = row[3]
                new_question_object['questionText'] = row[4]

                if new_question_object['imageID']:
                    query = f"SELECT * FROM image WHERE imageID = {new_question_object['imageID']}"
                    result = get_from_db(query, None, conn, cursor)
                    for row in result:
                        new_question_object['imageLocation'] = IMG_RETRIEVE_FOLDER + row[1] if row and row[1] else None

                if new_question_object['audioID']:
                    query = f"SELECT * FROM audio WHERE audioID = {new_question_object['audioID']}"
                    result = get_from_db(query, None, conn, cursor)
                    for row in result:
                        new_question_object['audioLocation'] = AUD_RETRIEVE_FOLDER + row[1] if row and row[1] else None

                query = f"SELECT * FROM answer WHERE questionID = {new_question_object['questionID']}"
                result = get_from_db(query, None, conn, cursor)
                new_question_object['answers'] = []
                for row in result:
                    new_question_object['answers'].append(row[1])
                final_question_object.append(new_question_object)
            raise ReturnSuccess(final_question_object, 200)
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


class DeleteQuestion(Resource):
    #deletes a question
    @jwt_required
    def delete(self):
        data = {}
        data['questionID'] = getParameter("questionID", str, True, "")
        data['groupID'] = getParameter("groupID", str, False, "groupID is required if student is a TA")

        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return errorMessage("Invalid user"), 401

        if permission == 'st' and not is_ta(user_id, data['groupID']):
            return errorMessage("User not authorized to delete questions."), 400

        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            if (find_question(int(data['questionID']))):
                question_query = f"SELECT * FROM question WHERE questionID = {data['questionID']}"
                question_data = get_from_db(question_query, None, conn, cursor)
   
                delete_query = "INSERT INTO deleted_question (questionID, audioID, imageID, type, questionText) VALUES (%s, %s, %s, %s, %s)"
                post_to_db(delete_query, (question_data[0][0], question_data[0][1], question_data[0][2], question_data[0][3], question_data[0][4]))

                la_query = f"SELECT logID FROM logged_answer WHERE questionID = {question_data[0][0]}"
                la_results = get_from_db(la_query, None, conn, cursor)

                for log in la_results:
                    log_query = "UPDATE logged_answer SET questionID = %s, deleted_questionID = %s WHERE logID = %s"
                    post_to_db(log_query, (None, question_data[0][0], log[0]), None, conn, cursor)

                query = f"DELETE FROM `question` WHERE `questionID = {data['questionID']}"
                delete_from_db(query, None, con, cursor)
                raise ReturnSuccess("Successfully deleted question and answer set!", 201)
            else:
                raise CustomException("No question with that ID exist!", 201)
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


class Question(Resource):
    #adds a question to the database table
    @jwt_required
    def post(self):
        data = {}
        data['type'] = getParameter("type", str, True, "")
        data['questionText'] = getParameter("questionText", str, True, "")
        data['moduleID'] = getParameter("moduleID", str, True, "Pass in the ID of the module to which the question should be linked")
        data['groupID'] = getParameter("groupID", str, False, "groupID is required if student is a TA")
        data['imageID'] = None
        data['audioID'] = None

        maxID = -1

        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return errorMessage("Invalid user"), 401

        if permission == 'st' and not is_ta(user_id, data['groupID']):
            return errorMessage("User not authorized to add questions."), 400

        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            #If an image was provided to upload
            if 'image' in request.files:
                #if data['imageID'] already has a value, then we have already uploaded an image
                if data['imageID'] is not None:
                    raise CustomException("Uploading two images, can only upload one per question", 403)

                dateTime = time.strftime("%d%m%y%H%M%S")

                file = request.files['image']
                if not file:
                    raise CustomException("Image file not recieved properly", 500)

                filename, extension = os.path.splitext(file.filename)
                filename = secure_filename(filename) + str(dateTime)
                full_file_name = str(filename) + str(extension)

                #making sure the passed in image has an acceptable extension before moving forward
                if extension[1:] in IMAGE_EXTENSIONS:
                    #saving the image to a temporary folder
                    file.save(cross_plat_path(TEMP_UPLOAD_FOLDER + full_file_name))

                    query = f"INSERT INTO image (imageLocation) VALUES ({full_file_name})"
                    post_to_db(query, None, conn, cursor)

                    #moving the image to the Images folder upon successfully creating a record
                    os.rename(cross_plat_path(TEMP_UPLOAD_FOLDER + full_file_name), cross_plat_path(IMG_UPLOAD_FOLDER + full_file_name))

                    #get the inserted image's imageID
                    query = f"SELECT imageID from image WHERE imageLocation = {full_file_name}"
                    imageID = get_from_db(query, None, conn, cursor)
                    data['imageID'] = imageID[0][0]
                else:
                    raise CustomException("File format of " + filename + extension + " is not supported. \
                            Please upload an image format of jpeg, jpg, or png format.", 415)

            if 'audio' in request.files:
                #if data['audioID'] already has a value, then we have already uploaded an audio            
                if data['audioID'] is not None:
                            raise CustomException("Uploading two audio files, can only upload one per question", 403)

                dateTime = time.strftime("%d%m%y%H%M%S")

                file = request.files['audio']
                if not file:
                    raise CustomException("Audio file not recieved properly", 500)

                filename, extension = os.path.splitext(file.filename)
                filename = secure_filename(filename) + str(dateTime)
                full_file_name = str(filename) + str(extension)

                if extension[1:] in AUDIO_EXTENSIONS:
                    #saving the audio to a temporary folder
                    file.save(cross_plat_path(TEMP_UPLOAD_FOLDER + full_file_name))

                    query = f"INSERT INTO audio (audioLocation) VALUES ({full_file_name})"
                    post_to_db(query, None, conn, cursor)

                    #moving the audio to the Audio folder upon successfully creating a record
                    os.rename(cross_plat_path(TEMP_UPLOAD_FOLDER + full_file_name), cross_plat_path(AUD_UPLOAD_FOLDER + full_file_name))

                    #get the inserted audio's audioID
                    query = f"SELECT audioID from audio WHERE audioLocation = {str(full_file_name)}"
                    audioID = get_from_db(query, None, conn, cursor)
                    data['audioID'] = audioID[0][0]
                else:
                    raise CustomException("File format of " + str(filename) + str(extension) + " is not supported. \
                            Please upload an audio of format of wav, ogg, or mp3", 415)

            # Add new question          
            if permission == 'st' and not is_ta(user_id, data['groupID']):
                raise CustomException("User not authorized to add questions.", 401)

            query = "INSERT INTO question (`audioID`, `imageID`, `type`, `questionText`) VALUES (%s, %s, %s, %s)"
            post_to_db(query, (data['audioID'], data['imageID'], data['type'], data['questionText']), conn, cursor)

            query = "SELECT MAX(questionID) FROM question"
            result = get_from_db(query, None, conn, cursor)
            question_id = check_max_id(result) - 1

            if data['moduleID']:
                fquery = f"INSERT INTO `module_question` (`moduleID`, `questionID`) VALUES ({data['moduleID']}, {question_id})"
                post_to_db(query, None, conn, cursor)

            # Add the existing terms to the question as answers
            ans_list = request.form.getlist('answers')
            ans_list = json.loads(ans_list[0])
            for ans in ans_list:
                query = f"INSERT INTO `answer` (questionID, termID) VALUES ({question_id}, {ans})"
                post_to_db(query, None, conn, cursor)

            # Creating new terms that will be linked to the question based on the objects passed in
            term_obj_list = request.form.getlist('arr_of_terms')
            for term_obj in term_obj_list:
                term_obj = json.loads(term_obj)
                for term in term_obj:
                    query = f"INSERT INTO `term` (front, back, language) VALUES ({term['front']}, {term['back']}, {term['language']})"
                    post_to_db(query, None, conn, cursor)
                    term_query = "SELECT MAX(termID) FROM `term`"
                    result = get_from_db(term_query, None, conn, cursor)
                    termID = check_max_id(result) - 1
                    answer_query = f"INSERT INTO `answer` (questionID, termID) VALUES ({question_id}, {termID})"
                    post_to_db(answer_query, None, conn, cursor)

                    for t in term['tags']:
                        tag_query = f"SELECT * FROM `tag` WHERE termID = {termID} AND tagName = {str(t).lower()}"
                        tag_result = get_from_db(tag_query, None, conn, cursor)
                        if not tag_result:
                            query = f"INSERT INTO `tag` (termID, tagName) VALUES ({termID}, {str(t).lower()})"
                            post_to_db(query, None, conn, cursor)
                            
            raise ReturnSuccess({"Message" : "Successfully created a question", "questionID" : int(question_id)}, 201)
        except CustomException as error:
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
        data = {}
        data['questionID'] = getParameter("questionID", str, False, "")

        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return errorMessage("Invalid user"), 401

        try:
            conn = mysql.connect()
            cursor = conn.cursor()
            
            if (find_question(data['questionID'])):
                query = f"SELECT * FROM question WHERE questionID = {data['questionID']}"
                result = get_from_db(query, None, conn, cursor)
                new_question_object = {}
                for row in result:
                    new_question_object['questionID'] = row[0]
                    new_question_object['audioID'] = row[1]
                    new_question_object['imageID'] = row[2]
                    new_question_object['type'] = row[3]
                    new_question_object['questionText'] = row[4]

                query = f"SELECT * FROM image WHERE imageID = {new_question_object['imageID']}"
                result = get_from_db(query, None, conn, cursor)
                for row in result:
                    new_question_object['imageLocation'] = IMG_RETRIEVE_FOLDER + row[1] if row and row[1] else None

                query = f"SELECT * FROM audio WHERE audioID = {new_question_object['audioID']}"
                result = get_from_db(query, None, conn, cursor)
                for row in result:
                    new_question_object['audioLocation'] = AUD_RETRIEVE_FOLDER + row[1] if row and row[1] else None

                query = f"SELECT * FROM answer WHERE questionID = {new_question_object['questionID']}"
                result = get_from_db(query, None, conn, cursor)
                new_question_object['answers'] = []
                for row in result:
                    new_question_object['answers'].append(row[1])
                raise ReturnSuccess(new_question_object, 200)
            else:
                raise CustomException("Question does not exist!", 404)
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