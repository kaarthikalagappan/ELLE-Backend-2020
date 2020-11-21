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
from exceptions_util import *
import os
import time
import requests


class Term(Resource):
    """APIs that deal with adding, retrieving, and deleting a term"""

    @jwt_required
    def get(self):
        """
        Retrieve the list of terms that match the parameters.

        Searches through the term's front, back, type, and gender to get any elements that match the search_term, if provided.
        If search_term not provided, we retrieve all terms in that language.
        """

        data = {}
        data['search_term'] = getParameter("search_term", str, False, "Provided search keyword(s)")
        data['language'] = getParameter("language", str, True, "Specify the language")

        matching_terms = []
        language = data['language'].lower()
        #if there is no search term provided, return all the terms
        if 'search_term' not in data or not data['search_term']:
            query = f"""SELECT `term`.*, `image`.`imageLocation`, `audio`.`audioLocation` FROM `term` 
                    LEFT JOIN `image` ON `image`.`imageID` = `term`.`imageID` 
                    LEFT JOIN `audio` ON `audio`.`audioID` = `term`.`audioID` 
                    WHERE `language` = '{language}'"""
            results = get_from_db(query)
            if results and results[0]:
                for term in results:
                    matching_terms.append(convertTermToJSON(term))
            return matching_terms

        #search through different fields in term table that [partially] matches the given search term
        search_string = str(data['search_term']).lower()
        query = f"""SELECT `term`.*, `image`.`imageLocation`, `audio`.`audioLocation` FROM `term` 
                LEFT JOIN `image` ON `image`.`imageID` = `term`.`imageID` 
                LEFT JOIN `audio` ON `audio`.`audioID` = `term`.`audioID` 
                WHERE `language` = '{language}' and (`front` LIKE '{search_string+"%"}' OR 
                `back` LIKE '{search_string+"%"}' OR `type` LIKE '{search_string[:2]}' OR `gender` LIKE '{search_string[:1]}')"""
        results = get_from_db(query)
        if results and results[0]:
            for term in results:
                matching_terms.append(convertTermToJSON(term))

        #searching through tags that [partially] matches the given search term
        query = f"""SELECT `term`.*, `image`.`imageLocation`, `audio`.`audioLocation` FROM `term` 
                LEFT JOIN `image` ON `image`.`imageID` = `term`.`imageID` 
                LEFT JOIN `audio` ON `audio`.`audioID` = `term`.`audioID` 
                INNER JOIN `tag` AS `ta` ON `term`.`termID` = `ta`.`termID` 
                WHERE `language` = '{language}' and `ta`.`tagName` LIKE '{search_string+"%"}'"""
        results = get_from_db(query)
        if results and results[0]:
            for term in results:
                jsonObject = convertTermToJSON(term)
                if jsonObject not in matching_terms:
                    matching_terms.append(jsonObject)

        return matching_terms, 200


    @jwt_required
    def post(self):
        """
        Add a new term or update a new term.

        If termID is passed in, it is assumed that that term is being updated. 
        If termID is not passed in, it is assumed we are adding a new term.
        """

        parser = reqparse.RequestParser()
        parser.add_argument('tag',
                            required = False,
                            action = 'append',
                            help = "Unable to parse list of tags",
                            type = str)
        data = parser.parse_args()

        data['front'] = getParameter("front", str, True, "Front side of term required")
        data['back'] = getParameter("back", str, True, "Back side/Translation of term required")
        data['type'] = getParameter("type", str, False, "Error with type parameter")
        data['gender'] = getParameter("gender", str, False, "Error with gender parameter")
        data['language'] = getParameter("language", str, True, "Please pass in the language of the term")
        data['termID'] = getParameter("termID", int, False, "Pass in termID as an integer if updating a term")
        data['moduleID'] = getParameter("moduleID", int, False, "Pass the moduleID as integer to which this term should be added to")
        data['groupID'] = getParameter("groupID", int, False, "Pass the groupID as integer if the user is a TA")

        # Validate the user
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return errorMessage("Invalid user"), 401

        if permission == 'st' and not is_ta(user_id, data['groupID']):
            return errorMessage("User not authorized to create terms"), 400

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

        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            # If an image was provided to upload
            if 'image' in request.files:
                dateTime = time.strftime("%d%m%y%H%M%S")

                file = request.files['image']
                if not file:
                    raise CustomException("Image file not recieved properly", 500)

                filename, extension = os.path.splitext(file.filename)
                filename = secure_filename(filename) + str(dateTime)
                fullFileName = str(filename) + str(extension)

                #making sure the passed in image has an acceptable extension before moving forward
                if extension[1:] in IMAGE_EXTENSIONS:
                    #saving the image to a temporary folder
                    file.save(cross_plat_path(TEMP_UPLOAD_FOLDER + fullFileName))

                    query = f"""INSERT INTO `image` (`imageLocation`) VALUES ('{fullFileName}')"""
                    post_to_db(query, None, conn, cursor)

                    #moving the image to the Images folder upon successfully creating a record
                    os.rename(cross_plat_path(TEMP_UPLOAD_FOLDER + fullFileName), cross_plat_path(IMG_UPLOAD_FOLDER + fullFileName))

                    #get the inserted image's imageID
                    query = f"""SELECT `imageID` FROM `image` WHERE `imageLocation` = '{fullFileName}'"""
                    imageID = get_from_db(query, None, conn, cursor)
                    data['imageID'] = imageID[0][0]
                else:
                    raise CustomException("File format of " + filename + extension + " is not supported. \
                            Please upload an image format of jpeg, jpg, or png format.", 415)

            if 'audio' in request.files:
                dateTime = time.strftime("%d%m%y%H%M%S")

                file = request.files['audio']
                if not file:
                    raise CustomException("Audio file not recieved properly", 500)

                filename, extension = os.path.splitext(file.filename)
                filename = secure_filename(filename) + str(dateTime)
                fullFileName = str(filename) + str(extension)

                if extension[1:] in AUDIO_EXTENSIONS:
                    #saving the audio to a temporary folder
                    file.save(cross_plat_path(TEMP_UPLOAD_FOLDER + fullFileName))

                    query = f"""INSERT INTO `audio` (`audioLocation`) VALUES ('{fullFileName}')"""
                    post_to_db(query, None, conn, cursor)

                    #moving the audio to the Audio folder upon successfully creating a record
                    os.rename(cross_plat_path(TEMP_UPLOAD_FOLDER + fullFileName), cross_plat_path(AUD_UPLOAD_FOLDER + fullFileName))

                    #get the inserted audio's audioID
                    query = f"""SELECT `audioID` FROM `audio` WHERE `audioLocation` = '{fullFileName}'"""
                    audioID = get_from_db(query, None, conn, cursor)
                    data['audioID'] = audioID[0][0]
                else:
                    raise CustomException("File format of " + str(filename) + str(extension) + " is not supported. \
                            Please upload an audio of format of wav, ogg, or mp3", 415)

            # Updating an exsting term
            if data['termID'] is not None:
                query = f"""SELECT `front` FROM `term` WHERE `termID` = {str(data['termID'])}"""
                result = get_from_db(query, None, conn, cursor)
                if not result:
                    raise CustomException("Not an existing term to edit,\
                                        DEVELOPER: please don't pass in id if creating new term", 404)

                query = f"""UPDATE term SET front = '{data['front']}', 
                        back = '{data['back']}', type = '{data['type']}', 
                        gender = '{data['gender']}', language = '{data['language']}' 
                        WHERE termID = {str(data['termID'])}"""
                post_to_db(query, None, conn, cursor)

                #if they pass in an image or audio, we will replace the existing image or audio (if present) with the new ones
                query = f"SELECT `imageID` FROM `term` WHERE `termID` = {str(data['termID'])}"
                result = get_from_db(query, None, conn, cursor)
                if data['imageID'] is not None:
                    if result and result[0][0]:
                        #If the term already has an image, delete the image and copy on server and replace it
                        query = f"SELECT `imageLocation` FROM `image` WHERE `imageID` = {str(result[0][0])}"
                        imageLocation = get_from_db(query, None, conn, cursor)
                        if not imageLocation or not imageLocation[0][0]:
                            raise CustomException("something went wrong when trying to retrieve image location", 500)

                        imageFileName = imageLocation[0][0]
  
                        query = f"DELETE FROM `image` WHERE `imageID` = {str(result[0][0])}"
                        delete_from_db(query, None, conn, cursor)

                        #removing the existing image
                        os.remove(str(cross_plat_path(IMG_UPLOAD_FOLDER + str(imageFileName))))

                    query = f"""UPDATE `term` SET `imageID` = {data['imageID']} 
                            WHERE `termID` = {str(data['termID'])}"""
                    post_to_db(query, None, conn, cursor)

                query = f"SELECT `audioID` FROM `term` WHERE `termID` = {str(data['termID'])}"
                result = get_from_db(query, None, conn, cursor)
                if data['audioID'] is not None:
                    if result and result[0][0]:
                        #If the term already has an audio, delete the audio and copy on server and replace it
                        query = f"SELECT `audioLocation` FROM `audio` WHERE `audioID` = {str(result[0][0])}"
                        audioLocation = get_from_db(query, None, conn, cursor)
                        if not audioLocation or not audioLocation[0][0]:
                            raise CustomException("something went wrong when trying to retrieve audio location", 500)
                        audioFileName = audioLocation[0][0]

                        query = f"DELETE FROM `audio` WHERE `audioID` = {str(result[0][0])}"
                        delete_from_db(query, None, conn, cursor)

                        #removing existing audio
                        os.remove(cross_plat_path(AUD_UPLOAD_FOLDER + str(audioFileName)))

                    query = f"UPDATE `term` SET `audioID` = '{data['audioID']}' WHERE `termID` = {str(data['termID'])}"
                    post_to_db(query, None, conn, cursor)

                #add new tags or remove tags if they were removed
                query = f"SELECT `tagName` FROM `tag` WHERE `termID` = {str(data['termID'])}"
                attached_tags = get_from_db(query, None, conn, cursor)

                #There are no tags already attached with the term, so we add all the given ones
                if not attached_tags and data['tag'] is not None and data['tag']:  #'is not None' redundant?
                    addNewTags(data['tag'], str(data['termID']), conn, cursor)

                #The user has removed existing tags without any replacements, so we delete them all
                elif not data['tag'] and attached_tags is not None and attached_tags:
                    query = f"DELETE FROM `tag` WHERE `termID` = {str(data['termID'])}"
                    delete_from_db(query, None, conn, cursor)

                #The user is updating the existing tags, so we delete what was removed and add new tags
                elif data['tag'] is not None and attached_tags is not None:
                    existing_tags = []
                    for indiv_tag in attached_tags:
                        existing_tags.append(str(indiv_tag[0]))
                    different_tags = [i for i in existing_tags + data['tag'] if i not in existing_tags or i not in data['tag']]
                    if different_tags:
                        for indiv_tag in different_tags:
                            if indiv_tag in existing_tags and indiv_tag not in data['tag']:
                                #if the tag is not in the given list of tags, the user removed it so delete it
                                query = f"""DELETE FROM `tag` WHERE `termID` = {str(data['termID'])} 
                                        AND `tagName` = {str(indiv_tag)}"""
                                delete_from_db(query, None, conn, cursor)
                            elif indiv_tag in data['tag'] and indiv_tag not in existing_tags:
                                #if the tag is only in the given list, then the user added it, so we add it
                                addNewTags([indiv_tag], str(data['termID']), conn, cursor)
                
                raise ReturnSuccess("Term Modified: " + str(data['termID']), 201)
            else:
                query = "SELECT MAX(`termID`) FROM `term`"
                result = get_from_db(query, None, conn, cursor)
                print("here")
                query = f"""INSERT INTO `term` (`imageID`, `audioID`, `front`, `back`, `type`, `gender`, `language`)
                        VALUES ({"NULL" if not data['imageID'] else data['imageID']}, {"NULL" if not data['audioID'] else data['audioID']}, '{data['front']}', 
                        '{data['back']}', '{data['type']}', '{data['gender']}', '{data['language']}')"""
                post_to_db(query, None, conn, cursor)
                print("here2")
                
                maxID = cursor.lastrowid
                
                #Add the given list of tags
                if 'tag' in data and data['tag']:
                    addNewTags(data['tag'], maxID, conn, cursor)

                #create a default question
                typeQuestion = 'PHRASE' if data['type'] and (data['type'] == 'PH' or data['type'] == 'PHRASE') else 'MATCH'
                questionText = "Match: " + data['front'] + "?"
                questionQuery = f"""INSERT INTO `question` (`type`, `questionText`) 
                                VALUES ('{typeQuestion}', '{questionText}')"""
                post_to_db(questionQuery, None, conn, cursor)

                #get the added question's ID
                maxQuestionQuery = "SELECT MAX(`questionID`) FROM `question`"
                result = get_from_db(maxQuestionQuery, None, conn, cursor)
                questionMaxID = result[0][0] if result and result[0] else 1

                #link the term to the default question
                insertAnswerQuery = f"""INSERT INTO `answer` (`questionID`, `termID`) 
                                    VALUES ({int(questionMaxID)}, {int(maxID)})"""
                post_to_db(insertAnswerQuery, None, conn, cursor)

                #link the question to the module
                insertModuleQuery = f"""INSERT INTO `module_question` (`moduleID`, `questionID`) 
                                    VALUES ({data['moduleID']}, {str(questionMaxID)})"""
                post_to_db(insertModuleQuery, None, conn, cursor)

                raise ReturnSuccess({"Message" : "Successfully created a term", "termID" : int(maxID)}, 201)
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

    @jwt_required
    def delete(self):
        """
        Delete a term.

        Delete the term associated with the given termID.
        Note: Deleting a term will add it to the deleted table for record keeping purposes.
        """

        data = {}
        data['termID'] = getParameter("termID", str, True, "Term ID in integet is required for deletion")
        data['groupID'] = getParameter("groupID", str, False, "groupID (int) is required if student is TA")

        # Validate the user
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return errorMessage("Invalid user"), 401

        if permission == 'st' and not is_ta(user_id, data['groupID']):
            return errorMessage("User not authorized to delete terms"), 400

        if not data['termID'] or data['termID'] == '':
            return errorMessage("Please pass in a valid term id"), 400

        try:
            conn = mysql.connect()
            cursor = conn.cursor()
            exists = check_if_term_exists(data['termID'])

            if not exists:
                raise CustomException("cannot delete non-existing term", 403)

            #get the imageID and audioID, if they exist, in order to delete them as well
            query = f"SELECT `imageID`, `audioID` FROM `term` WHERE `termID` = {str(data['termID'])}"
            results = get_from_db(query, None, conn, cursor)
            imageLocation = [[]]
            audioLocation = [[]]
            if results and results[0]:
                imageID = results[0][0]
                audioID = results[0][1]
                if imageID:
                    query = f"SELECT `imageLocation` FROM `image` WHERE `imageID` = {str(imageID)}"
                    imageLocation = get_from_db(query, None, conn, cursor)
                    os.rename(cross_plat_path(IMG_UPLOAD_FOLDER + str(imageLocation[0][0])), cross_plat_path(TEMP_DELETE_FOLDER + str(imageLocation[0][0])))
                    query = f"DELETE FROM `image` WHERE `imageID` = {str(imageID)}"
                    delete_from_db(query, None, conn, cursor)
                if audioID:
                    query = f"SELECT `audioLocation` FROM `audio` WHERE `audioID` = {str(audioID)}"
                    audioLocation = get_from_db(query, None, conn, cursor)
                    os.rename(cross_plat_path(AUD_UPLOAD_FOLDER + str(audioLocation[0][0])), cross_plat_path(TEMP_DELETE_FOLDER + str(audioLocation[0][0])))
                    query = f"DELETE FROM `audio` WHERE `audioID` = {str(audioID)}"
                    delete_from_db(query, None, conn, cursor)

            deleteAnswersSuccess = Delete_Term_Associations(term_id=data['termID'], given_conn=conn, given_cursor=cursor)
            if deleteAnswersSuccess == 0:
                raise CustomException("Error when trying to delete associated answers", 500)

            # Get term's data
            term_query = f"SELECT * FROM `term` WHERE `termID` = {data['termID']}"
            term_data = get_from_db(term_query, None, conn, cursor)

            # Move to the deleted_term table
            delete_query = f"""INSERT INTO `deleted_term` (`termID`, `imageID`, `audioID`, `front`, `back`, `type`, `gender`, `LANGUAGE`) 
                            VALUES ({term_data[0][0]}, {"NULL" if not term_data[0][1] else term_data[0][1]}, 
                            {"NULL" if not term_data[0][2] else term_data[0][2]}, '{term_data[0][3]}', 
                            '{term_data[0][4]}', '{term_data[0][5]}', '{term_data[0][6]}', '{term_data[0][7]}')"""
            post_to_db(delete_query, None, conn, cursor)

            # Get all logged answers that were associated to the term
            la_query = f"SELECT `logID` FROM `logged_answer` WHERE `termID` = {term_data[0][0]}"
            la_results = get_from_db(la_query, None, conn, cursor)

            # Update logged answers
            for log in la_results:
                log_query = f"""UPDATE `logged_answer` SET `termID` = {None}, 
                            `deleted_termID` = {term_data[0][0]} WHERE `logID` = {log[0]}"""
                post_to_db(log_query, None, conn, cursor)

            query = f"DELETE FROM `term` WHERE `termID` = {str(data['termID'])}"
            delete_from_db(query, None, conn, cursor)

            raise ReturnSuccess("Term " + str(data['termID']) + " successfully deleted", 202)
        except ReturnSuccess as success:
            #If database changes are successfully, permanently delete the media files
            if imageLocation and imageLocation[0]:
                os.remove(str(cross_plat_path(TEMP_DELETE_FOLDER + str(imageLocation[0][0]))))
            if audioLocation and audioLocation[0]:
                os.remove(str(cross_plat_path(TEMP_DELETE_FOLDER + str(audioLocation[0][0]))))
            conn.commit()
            return success.msg, success.returnCode
        except CustomException as error:
            conn.rollback()
            return error.msg, error.returnCode
        except Exception as error:
            #If an error occured while delete database records, move the media back to original location
            if imageLocation and imageLocation[0]:
                os.rename(cross_plat_path(TEMP_DELETE_FOLDER + str(imageLocation[0][0])), cross_plat_path(IMG_UPLOAD_FOLDER + str(imageLocation[0][0])))
            if audioLocation and audioLocation[0]:
                os.rename(cross_plat_path(TEMP_DELETE_FOLDER + str(audioLocation[0][0])), cross_plat_path(AUD_UPLOAD_FOLDER + str(audioLocation[0][0])))
            conn.rollback()
            return errorMessage(str(error)), 500
        finally:
            if(conn.open):
                cursor.close()
                conn.close()


class Tags(Resource):
    """API for dealing with tags"""

    @jwt_required
    def get(self):
        """
        Get all the tags in the database.
        """

        # Validate the user
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return errorMessage("Invalid user"), 401
        
        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            query = "SELECT `tagName` FROM `tag`"
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
            return errorMessage(str(error)), 500
        finally:
            if(conn.open):
                cursor.close()
                conn.close()


class Tag_Term(Resource):
    """API used to get terms associated with a tag"""

    @jwt_required
    def get(self):
        """Get terms associated with a specific tag"""

        tag_name = getParameter("tag_name", str, True, "Name of tag required to retrieve associated terms")
        
        # Validate the user
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return errorMessage("Invalid user"), 401
        
        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            if not tag_name or tag_name == '':
                raise CustomException("Please provide a tag name", 406)

            query = f"""SELECT `term`.*, `image`.`imageLocation`, `audio`.`audioLocation` FROM `term` 
                    LEFT JOIN `image` ON `image`.`imageID` = `term`.`imageID` 
                    LEFT JOIN `audio` ON `audio`.`audioID` = `term`.`audioID` 
                    INNER JOIN `tag` ON `tag`.`termID` = `term`.`termID` 
                    WHERE `tag`.`tagName`='{tag_name.lower()}'"""
            terms_from_db = get_from_db(query, None, conn, cursor)
            matching_terms = []
            for term in terms_from_db:
                jsonObject = convertTermToJSON(term)
                if jsonObject not in matching_terms:
                    matching_terms.append(jsonObject)
            
            raise ReturnSuccess(matching_terms, 200)
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


class Specific_Term(Resource):
    """API to get a specific term given an ID"""

    @jwt_required
    def get(self):
        """Get a specific term given it's termID."""

        termID = getParameter("termID", int, True, "ID of the term whose tags need to be retrieved is required")

        # Validate the user
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return errorMessage("Invalid user"), 401

        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            if not termID or termID == '':
                raise CustomException("Please provide a termID", 406)

            query = f"""SELECT `term`.*, `image`.`imageLocation`, `audio`.`audioLocation` FROM `term` 
                    LEFT JOIN `image` ON `image`.`imageID` = `term`.`imageID` 
                    LEFT JOIN `audio` ON `audio`.`audioID` = `term`.`audioID` 
                    WHERE `term`.`termID` = {str(termID)}"""
            term_from_db = get_from_db(query, None, conn, cursor)

            term = []
            if term_from_db and term_from_db[0]:        
                raise ReturnSuccess(convertTermToJSON(term_from_db[0]), 200)
            else:
                raise CustomException("Term not found", 404)

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


class Tags_In_Term(Resource):
    """API to get all terms associated with a tag"""

    @jwt_required
    def get(self):
        """Get terms associated with a specific tag."""

        termID = getParameter("termID", int, True, "ID of the term whose tags need to be retrieved is required")

        # Validate the user
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return errorMessage("Invalid user"), 401
        
        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            if not termID or termID == '':
                raise CustomException("Please provide a termID", 406)

            query = f"SELECT `tagName` FROM `tag` WHERE `termID` = {str(termID)}"
            tags_from_db = get_from_db(query, None, conn, cursor)
            tags_list = []
            for tag in tags_from_db:
                if tag not in tags_list and tag[0]:
                    tags_list.append(tag[0])
            
            raise ReturnSuccess(tags_list, 200)
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


class TagCount(Resource):
    """API to get a count of how many terms are associated with a tag."""

    @jwt_required
    def get(self):
        """Get a list of all tags in the database and how many terms are associated with it"""

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

