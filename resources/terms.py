# -*- encoding: utf-8 -*-

from flask import request
from config import (
    IMAGE_EXTENSIONS, AUDIO_EXTENSIONS, TEMP_DELETE_FOLDER,
    TEMP_UPLOAD_FOLDER, IMG_UPLOAD_FOLDER, AUD_UPLOAD_FOLDER,
    IMG_RETRIEVE_FOLDER, AUD_RETRIEVE_FOLDER
    )
from flask_restful import Resource, reqparse
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from flaskext.mysql import MySQL
from db import mysql
from db_utils import *
from utils import *
from datetime import date
import os
import time
import requests


#Set it to True to see some extra information printed to the console for debugging purposes
DEBUG = True


class CustomException(Exception):
    pass


class TermsException(Exception):
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


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in IMAGE_EXTENSIONS or \
        filename.rsplit('.', 1)[1].lower() in AUDIO_EXTENSIONS


class Term(Resource):
    @jwt_required
    #Searching through the terms
    #ADD language parameter
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('search_term',
                            required = False,
                            type = str,
                            help = "The keyword that you want to look up")
        parser.add_argument('language',
                            required = True,
                            type = str,
                            help = "Please specify the language")

        data = parser.parse_args()
        matching_terms = []
        language = data['language'].lower()
        #if there is no search term provided, return all the terms
        if 'search_term' not in data or not data['search_term']:
            query = "SELECT term.*, image.imageLocation, audio.audioLocation FROM `term` \
                    LEFT JOIN image ON image.imageID = term.imageID \
                    LEFT JOIN audio ON audio.audioID = term.audioID \
                    WHERE language = %s"
            results = get_from_db(query, language)
            if results and results[0]:
                for term in results:
                    matching_terms.append(convertToJSON(term))
            return matching_terms

        #search through different fields in term table that [partially] matches the given search term
        search_string = str(data['search_term']).lower()
        query = "SELECT term.*, image.imageLocation, audio.audioLocation FROM `term` \
                LEFT JOIN image ON image.imageID = term.imageID \
                LEFT JOIN audio ON audio.audioID = term.audioID \
                WHERE language = %s and (front LIKE %s OR back \
                LIKE %s or type LIKE %s or gender LIKE %s)"
        results = get_from_db(query, (language, search_string+"%", search_string+"%", search_string[:2], search_string[:1]))
        if results and results[0]:
            for term in results:
                matching_terms.append(convertToJSON(term))

        #searching through tags that [partially] matches the given search term
        query = "SELECT term.*, image.imageLocation, audio.audioLocation from term \
                LEFT JOIN image ON image.imageID=term.imageID \
                LEFT JOIN audio ON audio.audioID = term.audioID \
                INNER JOIN tag as ta ON term.termID = ta.termID \
                WHERE language = %s and ta.tagName LIKE  %s"
        results = get_from_db(query, (language, search_string+"%"))
        if results and results[0]:
            for term in results:
                jsonObject = convertToJSON(term)
                if jsonObject not in matching_terms:
                    matching_terms.append(jsonObject)

        return matching_terms, 200
        #search through term's back, front, type, tag fields

    @jwt_required
    #Adding or updating a term
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('front',
                            required = True,
                            type = str,
                            help = "Front side of term required")
        parser.add_argument('back',
                            required = True,
                            type = str,
                            help = "Back side/Translation of term required")
        parser.add_argument('type',
                            required = False,
                            type = str)
        parser.add_argument('tag',
                            required = False,
                            action = 'append',
                            help = "Unable to parse list of tags",
                            type = str)
        parser.add_argument('gender',
                            required = False,
                            type = str)
        parser.add_argument('language',
                            required = True,
                            help = "Please pass in the language of the term",
                            type = str)
        parser.add_argument('termID',  #If termID is passed, we are updating the term
                            required = False,
                            help = "Pass in term id if updating a term",
                            type = str)
        parser.add_argument('moduleID',
                            required=False,
                            help="Pass the moduleID to which this term should be added to",
                            type=str)
        parser.add_argument('groupID',
                            required=False,
                            help="Pass the groupID if the user is a TA",
                            type=str)
        data = parser.parse_args()

        # Validate the user
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401

        if permission == 'st' and not is_ta(user_id, data['groupID']):
            return "User not authorized to create terms", 400

        # Create imageID and audioID fields to keep track of uploads
        data['imageID'] = None
        data['audioID'] = None
        if data['type']:
            data['type'] = data['type'][:2]

        if not data['termID']:
            data['termID'] = None

        if not data['gender']:
            data['gender'] = 'N'
        else:
            data['gender'] = data['gender'][:1]
 
        if not data['language']:
            data['language'] = None
        else:
            data['language'] = data['language'][:2].lower()
 
        if not data['tag']:
            data['tag'] = []

        if DEBUG:
            print("Given information (cleaned):")
            print(data)

        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            # If an image was provided to upload
            if 'image' in request.files:
                if DEBUG:
                    print("Found image to upload, uploading them")
                    print(request.files['image'])

                dateTime = time.strftime("%d%m%y%H%M%S")

                file = request.files['image']
                if not file:
                    raise TermsException("Image file not recieved properly", 500)

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
                    raise TermsException("File format of " + filename + extension + " is not supported. \
                            Please upload an image format of jpeg, jpg, or png format.", 415)

            if 'audio' in request.files:
                if DEBUG:
                    print("Found audio to upload, uploading them")
                    print(request.files['audio'])

                dateTime = time.strftime("%d%m%y%H%M%S")

                file = request.files['audio']
                if not file:
                    raise TermsException("Audio file not recieved properly", 500)

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
                    raise TermsException("File format of " + str(filename) + str(extension) + " is not supported. \
                            Please upload an audio of format of wav, ogg, or mp3", 415)

            if DEBUG:
                print("Given tag list:")
                print(data['tag'])

            # Updating an exsting term
            if data['termID'] is not None:
                if DEBUG:
                    print("updaing an existing term of termID: " + str(data['termID']))

                query = "SELECT front from term WHERE termID = %s"
                result = get_from_db(query, str(data['termID']), conn, cursor)
                if not result:
                    raise TermsException("Not an existing term to edit,\
                                        DEVELOPER: please don't pass in id if creating new term", 404)

                query = "UPDATE term SET front = %s, back = %s, type = %s, gender = %s, language = %s WHERE termID = %s"
                post_to_db(query, (data['front'], data['back'], data['type'], data['gender'], data['language'], str(data['termID'])),
                        conn, cursor)

                #if they pass in an image or audio, we will replace the existing image or audio (if present) with the new ones
                query = "SELECT imageID from term WHERE termID = %s"
                result = get_from_db(query, str(data['termID']), conn, cursor)
                if data['imageID'] is not None:
                    if result and result[0][0]:
                        #If the term already has an image, delete the image and copy on server and replace it
                        query = "SELECT imageLocation from image WHERE imageID = %s"
                        imageLocation = get_from_db(query, str(result[0][0]), conn, cursor)
                        if not imageLocation or not imageLocation[0][0]:
                            raise TermsException("something went wrong when trying to retrieve image location", 500)

                        imageFileName = imageLocation[0][0]

                        if DEBUG:
                            print("data: " + str(data['imageID']))
                            print("result: " + str(result))
  
                        query = "DELETE FROM image WHERE imageID = %s"
                        delete_from_db(query, str(result[0][0]), conn, cursor)

                        #removing the existing image
                        os.remove(str(cross_plat_path(IMG_UPLOAD_FOLDER + str(imageFileName))))

                    query = "UPDATE term SET imageID = %s WHERE termID = %s"
                    post_to_db(query, (data['imageID'], str(data['termID'])), conn, cursor)

                    if DEBUG:
                        print("Replaced image")

                query = "SELECT audioID from term WHERE termID = %s"
                result = get_from_db(query, str(data['termID']), conn, cursor)
                if data['audioID'] is not None:
                    if result and result[0][0]:
                        #If the term already has an audio, delete the audio and copy on server and replace it
                        query = "SELECT audioLocation from audio WHERE audioID = %s"
                        audioLocation = get_from_db(query, str(result[0][0]), conn, cursor)
                        if not audioLocation or not audioLocation[0][0]:
                            raise TermsException("something went wrong when trying to retrieve audio location", 500)
                        audioFileName = audioLocation[0][0]

                        query = "DELETE FROM audio WHERE audioID = %s"
                        delete_from_db(query, str(result[0][0]), conn, cursor)

                        #removing existing audio
                        os.remove(cross_plat_path(AUD_UPLOAD_FOLDER + str(audioFileName)))

                    query = "UPDATE term SET audioID = %s WHERE termID = %s"
                    post_to_db(query, (data['audioID'], str(data['termID'])), conn, cursor)

                    if DEBUG:
                        print("Replaced audio")

                #add new tags or remove tags if they were removed
                query = "SELECT tagName from tag WHERE termID = %s"
                attached_tags = get_from_db(query, str(data['termID']), conn, cursor)
                if DEBUG:
                    print("updating term: attached tag result:")
                    print(attached_tags)

                #There are no tags already attached with the term, so we add all the given ones
                if not attached_tags and data['tag'] is not None and data['tag']:  #'is not None' redundant?
                    addNewTags(data['tag'], str(data['termID']), conn, cursor)
                    if DEBUG:
                        print("Adding the given list of tags since existing tags are none")

                #The user has removed existing tags without any replacements, so we delete them all
                elif not data['tag'] and attached_tags is not None and attached_tags:
                    query = "DELETE from tag WHERE termID = %s"
                    delete_from_db(query, str(data['termID']).lower())
                    if DEBUG:
                        print("Deleting all the existing tags since given tag list was none")

                #The user has updating the existing tags, so we delete what was removed and add new tags
                elif data['tag'] is not None and attached_tags is not None:
                    existing_tags = []
                    for indiv_tag in attached_tags:
                        existing_tags.append(str(indiv_tag[0]))
                    different_tags = [i for i in existing_tags + data['tag'] if i not in existing_tags or i not in data['tag']]
                    if different_tags:
                        if DEBUG:
                            print("Removing and adding specific tags")
                        for indiv_tag in different_tags:
                            if indiv_tag in existing_tags and indiv_tag not in data['tag']:
                                #if the tag is not in the given list of tags, the user removed it so delete it
                                query = "DELETE from tag WHERE termID = %s AND tagName = %s"
                                delete_from_db(query, (str(data['termID']), str(indiv_tag)))
                            elif indiv_tag in data['tag'] and indiv_tag not in existing_tags:
                                #if the tag is only in the given list, then the user added it, so we add it
                                addNewTags([indiv_tag], str(data['termID']), conn, cursor)
                
                raise ReturnSuccess("Term Modified: " + str(data['termID']), 201)
            else:
                # Add new term   
                if DEBUG:
                    print("Adding a new term")

                query = "SELECT MAX(termID) FROM term"
                result = get_from_db(query, None, conn, cursor)

                query = "INSERT INTO term (`imageID`, `audioID`, `front`, `back`, `type`, `gender`, `language`) \
                        VALUES (%s, %s, %s, %s, %s, %s, %s)"
                post_to_db(query, (data['imageID'], data['audioID'], data['front'],
                            data['back'], data['type'], data['gender'],data['language']), conn, cursor)
                
                maxID = cursor.lastrowid
                
                #Add the given list of tags
                if 'tag' in data and data['tag']:
                    addNewTags(data['tag'], maxID, conn, cursor)

                #create a default question
                typeQuestion = 'PHRASE' if data['type'] and (data['type'] == 'PH' or data['type'] == 'PHRASE') else 'MATCH'
                questionText = "Match: " + data['front'] + "?"
                questionQuery = "INSERT INTO question (`type`, `questionText`) VALUES (%s, %s)"
                post_to_db(questionQuery, (typeQuestion, questionText), conn, cursor)

                #get the added question's ID
                maxQuestionQuery = "SELECT MAX(questionID) FROM question"
                result = get_from_db(maxQuestionQuery, None, conn, cursor)
                questionMaxID = result[0][0] if result and result[0] else 1

                #link the term to the default question
                insertAnswerQuery = "INSERT INTO answer (`questionID`, `termID`) VALUES (%s, %s)"
                post_to_db(insertAnswerQuery, (int(questionMaxID), int(maxID)), conn, cursor)

                #link the question to the module
                insertModuleQuery = "INSERT INTO `module_question` (`moduleID`, `questionID`) VALUES (%s, %s)"
                post_to_db(insertModuleQuery, (data['moduleID'], str(questionMaxID)), conn, cursor)

                raise ReturnSuccess({"Message" : "Successfully created a term", "termID" : int(maxID)}, 201)
        except TermsException as error:
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

    @jwt_required
    def delete(self):
        parser = reqparse.RequestParser()
        parser.add_argument('termID',
                            required = True,
                            type = str,
                            help = "Term id required for deletion")
        parser.add_argument('groupID',
                            required = False,
                            type = str,
                            help = "groupID is required if student is TA")
        data = parser.parse_args()

        # Validate the user
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401

        if permission == 'st' and not is_ta(user_id, data['groupID']):
            return "User not authorized to delete terms", 400

        if not data['termID'] or data['termID'] == '':
            return errorMessage("Please pass in a valid term id"), 400

        try:
            conn = mysql.connect()
            cursor = conn.cursor()
            
            exists = check_if_term_exists(data['termID'])

            if not exists:
                raise TermsException("cannot delete non-existing term", 403)

            #get the imageID and audioID, if they exist, in order to delete them as well
            query = "SELECT imageID, audioID FROM term WHERE termID = %s"
            results = get_from_db(query, str(data['termID']), conn, cursor)
            imageLocation = [[]]
            audioLocation = [[]]
            if results and results[0]:
                imageID = results[0][0]
                audioID = results[0][1]
                if imageID:
                    query = "SELECT imageLocation FROM image WHERE imageID = %s"
                    imageLocation = get_from_db(query, str(imageID), conn, cursor)
                    os.rename(cross_plat_path(IMG_UPLOAD_FOLDER + str(imageLocation[0][0])), cross_plat_path(TEMP_DELETE_FOLDER + str(imageLocation[0][0])))
                    query = "DELETE FROM image WHERE imageID = %s"
                    delete_from_db(query, str(imageID), conn, cursor)
                if audioID:
                    query = "SELECT audioLocation FROM audio WHERE audioID = %s"
                    audioLocation = get_from_db(query, str(audioID), conn, cursor)
                    os.rename(cross_plat_path(AUD_UPLOAD_FOLDER + str(audioLocation[0][0])), cross_plat_path(TEMP_DELETE_FOLDER + str(audioLocation[0][0])))
                    query = "DELETE FROM audio WHERE audioID = %s"
                    delete_from_db(query, str(audioID), conn, cursor)

            deleteAnswersSuccess = Delete_Term_Associations(termID=data['termID'], givenConn=conn, givenCursor=cursor)
            if deleteAnswersSuccess == 0:
                raise TermsException("Error when trying to delete associated answers", 500)

            # Get term's data
            term_query = "SELECT * FROM term WHERE termID = %s"
            term_data = get_from_db(term_query, data['termID'], conn, cursor)

            # Move to the deleted_term table
            delete_query = "INSERT INTO deleted_term (termID, imageID, audioID, front, back, type, gender, LANGUAGE) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
            post_to_db(delete_query, (term_data[0][0], term_data[0][1], term_data[0][2], term_data[0][3], term_data[0][4], term_data[0][5], term_data[0][6], term_data[0][7]), conn, cursor)

            # Get all logged answers that were associated to the term
            la_query = "SELECT logID FROM logged_answer WHERE termID = %s"
            la_results = get_from_db(la_query, term_data[0][0], conn, cursor)

            # Update logged answers
            for log in la_results:
                log_query = "UPDATE logged_answer SET termID = %s, deleted_termID = %s WHERE logID = %s"
                post_to_db(log_query, (None, term_data[0][0], log[0]))

            query = "DELETE FROM term WHERE termID = %s"
            delete_from_db(query, str(data['termID']), conn, cursor)
            raise ReturnSuccess("Term " + str(data['termID']) + " successfully deleted", 202)
        except ReturnSuccess as success:
            #If database changes are successfully, permanently delete the media files
            if imageLocation and imageLocation[0]:
                os.remove(str(cross_plat_path(TEMP_DELETE_FOLDER + str(imageLocation[0][0]))))
            if audioLocation and audioLocation[0]:
                os.remove(str(cross_plat_path(TEMP_DELETE_FOLDER + str(audioLocation[0][0]))))
            conn.commit()
            return success.msg, success.returnCode
        except TermsException as error:
            conn.rollback()
            return error.msg, error.returnCode
        except Exception as error:
            #If an error occured while delete database records, move the media back to original location
            if imageLocation and imageLocation[0]:
                os.rename(cross_plat_path(TEMP_DELETE_FOLDER + str(imageLocation[0][0])), cross_plat_path(IMG_UPLOAD_FOLDER + str(imageLocation[0][0])))
            if audioLocation and audioLocation[0]:
                os.rename(cross_plat_path(TEMP_DELETE_FOLDER + str(audioLocation[0][0])), cross_plat_path(AUD_UPLOAD_FOLDER + str(audioLocation[0][0])))
            conn.rollback()
            return errorMessage(str(error), DEBUG), 500
        finally:
            if(conn.open):
                cursor.close()
                conn.close()


class Tags(Resource):
    @jwt_required
    #Get all the tags in the database
    def get(self):
        # Validate the user
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401
        
        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            query = "SELECT tagName from tag"
            tags_from_db = get_from_db(query, None, conn, cursor)
            tags = {"tags" : []}
            if tags_from_db and tags_from_db[0]:
                for tag in tags_from_db:
                    if tag[0].lower() not in tags['tags']:
                        tags['tags'].append(tag[0].lower())

            raise ReturnSuccess(tags, 200)
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


class Tag_Term(Resource):
    @jwt_required
    #Get terms associated with a specific tagName
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('tag_name',
                            required = True,
                            type = str,
                            help = "Name of tag required to retrieve associated terms")
        data = parser.parse_args()
        
        # Validate the user
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401
        
        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            if not data['tag_name']:
                raise TermsException("Please provide a tag name", 406)

            query = "SELECT term.*, image.imageLocation, audio.audioLocation FROM term \
                    LEFT JOIN image ON image.imageID = term.imageID \
                    LEFT JOIN audio ON audio.audioID = term.audioID \
                    INNER JOIN tag on tag.termID=term.termID WHERE tag.tagName=%s"
            terms_from_db = get_from_db(query, data['tag_name'].lower(), conn, cursor)
            matching_terms = []
            for term in terms_from_db:
                jsonObject = convertToJSON(term)
                if jsonObject not in matching_terms:
                    matching_terms.append(jsonObject)
            
            raise ReturnSuccess(matching_terms, 200)
        except TermsException as error:
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

class Specific_Term(Resource):
    @jwt_required
    #Get a specific term given it's termID
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('termID',
                            required = True,
                            type = str,
                            help = "ID of the term whose tags need to be retrieved is required")
        data = parser.parse_args()

        # Validate the user
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401

        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            if not data['termID'] or data['termID'] == '':
                raise TermsException("Please provide a termID", 406)

            query = "SELECT term.*, image.imageLocation, audio.audioLocation FROM `term` \
                    LEFT JOIN image ON image.imageID = term.imageID \
                    LEFT JOIN audio ON audio.audioID = term.audioID \
                    WHERE term.termID = %s"
            term_from_db = get_from_db(query, str(data['termID']), conn, cursor)
            print(term_from_db)
            term = []
            if term_from_db and term_from_db[0]:        
                raise ReturnSuccess(convertToJSON(term_from_db[0]), 200)
            else:
                raise TermsException("Term not found", 404)

        except TermsException as error:
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


class Tags_In_Term(Resource):
    @jwt_required
    #Get terms associated with a specific tagName
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('termID',
                            required = True,
                            type = str,
                            help = "ID of the term whose tags need to be retrieved is required")
        data = parser.parse_args()

        # Validate the user
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401
        
        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            if not data['termID'] or data['termID'] == '':
                raise TermsException("Please provide a termID", 406)

            query = "SELECT tagName FROM `tag` WHERE termID = %s"
            tags_from_db = get_from_db(query, str(data['termID']), conn, cursor)
            tags_list = []
            for tag in tags_from_db:
                if tag not in tags_list and tag[0]:
                    tags_list.append(tag[0])
            
            raise ReturnSuccess(tags_list, 200)
        except TermsException as error:
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


class TagCount(Resource):
    #Get a count of how many terms are associated with each tag
    @jwt_required
    def get(self):
        get_all_tags_query = "SELECT * FROM `tag`"
        tags_list = get_from_db(get_all_tags_query)
        tag_count = {}

        for tag_record in tags_list:
            tag_name = tag_record[1].lower()
            if tag_name not in tag_count:
                tag_count[tag_name] = 1
            else:
                tag_count[tag_name] = tag_count[tag_name] + 1
            
        return tag_count


def addNewTags(tagList, termID, conn=None, cursor=None):
    for tag in tagList:
        #check if a record of these two combinations exist, if not insert
        query = "SELECT * from tag WHERE termID = %s AND tagName = %s"
        result = get_from_db(query, (termID, str(tag).lower()), conn, cursor)
        if result:
            if DEBUG:
                print(result)
                print("Trying to insert a duplicate tag")
        else:
            query = "INSERT into tag (termID, tagName) VALUES (%s, %s)"
            post_to_db(query, (termID, str(tag).lower()), conn, cursor)

def Delete_Term_Associations(termID, questionID=None, givenConn=None, givenCursor=None):
    #Note: This function is called from delete method of Term.
    #Checks how many Answer records are associated with this term and deletes those answer records
    #But before deleting, it checks if the answer record's questionID is associated with only the term being deleted
        #If so, deletes the question as well
    try:
        conn = mysql.connect() if givenConn == None else givenConn
        cursor = conn.cursor() if givenCursor == None else givenCursor

        deleteAnswerQuery = "DELETE from `answer` WHERE `questionID` = %s AND `termID` = %s"
        deleteQuestionQuery = "DELETE from `question` WHERE `questionID` = %s"
        getAssociatedQuestions = "SELECT * FROM `answer` WHERE questionID = %s"
        query = "SELECT * FROM `answer` WHERE termID = %s"
        answerRecords = get_from_db(query, str(termID), conn, cursor)

        for answer in answerRecords:
            if answer:
                questionInAnswers = get_from_db(getAssociatedQuestions, str(answer[0]), conn, cursor)
                if questionInAnswers and questionInAnswers[0] and len(questionInAnswers) <= 1:
                    if questionInAnswers[0][1] != answer[1]:
                        raise TermsException("Something went wrong in the logic of deleting a term", 500)
                    delete_from_db(deleteQuestionQuery, str(answer[0]))
                    if DEBUG:
                        print("QuestionID " + str(answer[0]) + " was deleted from database because it was only linked to the deleting term with termID: " + str(termID))
                delete_from_db(deleteAnswerQuery, (str(answer[0]), str(answer[1])), conn, cursor)
                print(answer)
        
        raise ReturnSuccess("Successfully deleted associated answer records", 200)
    except TermsException as error:
        if givenConn == None:
            conn.rollback()
        print(error.msg)
        return 0
    except ReturnSuccess as success:
        if givenConn == None:
            conn.commit()
        print(success.msg)
        return 1
    except Exception as error:
        if givenConn == None:
            conn.rollback()
        print(error)
        return 0
    finally:
        if(givenConn == None and conn.open):
            cursor.close()
            conn.close()

def convertToJSON(data):
    if len(data) < 10:
        if DEBUG:
            print("passed wrong amount of values to convertToJSON, it needs all elements in terms table")
        return errorMessage("passed wrong amount of values to convertToJSON, it needs all elements in terms table")
    result = {
        "termID" : data[0],
        "imageID" : data[1],
        "audioID" : data[2],
        "front" : data[3],
        "back" : data[4],
        "type" : data[5],
        "gender" : data[6],
        "language" : data[7],
        "imageLocation" : IMG_RETRIEVE_FOLDER + data[8] if data[8] else None,
        "audioLocation" : AUD_RETRIEVE_FOLDER + data[9] if data[9] else None
    }
    return result
