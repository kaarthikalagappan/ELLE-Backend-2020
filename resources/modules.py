# -*- encoding: utf-8 -*-

from flask import send_file, request, json
from flask_restful import Resource, reqparse
from flask_jwt_extended import jwt_required
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
def attach_question(module_id, question_id, conn, cursor):
    query = f"SELECT * FROM module_question WHERE moduleID = {module_id} AND questionID = {question_id}"
    result = get_from_db(query, None, conn, cursor)
    # If an empty list is returned, post new link
    if not result or not result[0]:
        query = f'''INSERT INTO module_question (moduleID, questionID)
                VALUES ({module_id}, {question_id})'''
        post_to_db(query, None, conn, cursor)
        return True
    else:
        # Delete link if it exists
        query = f'''DELETE FROM module_question
                WHERE moduleID = {module_id} AND questionID = {question_id}'''
        post_to_db(query, None, conn, cursor)
        return False


class Modules(Resource):
    # For acquiring all modules available for the current user
    # based on the user's registered groups
    @jwt_required
    def get(self):
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401

        query = f"""
                SELECT `module`.*, `group_module`.`groupID` FROM `module` 
                INNER JOIN `group_module` ON `module`.`moduleID` = `group_module`.`moduleID` 
                INNER JOIN `group_user` ON `group_module`.`groupID` = `group_user`.`groupID` 
                WHERE `group_user`.`userID`={user_id}
                """
        result = get_from_db(query)

        modules = []
        for row in result:
            modules.append(convertToJSON(row))

        # Return module information
        return modules


class RetrieveGroupModules(Resource):
    # Get all modules associated with the given groupID
    @jwt_required
    def get(self):
        # Get the user's ID and check permissions
        permission, user_id = validate_permissions()
        if not permission or not user_id:
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
            modules.append(convertToJSON(row)) 
        
        # Return module information
        return modules


class SearchModules(Resource):
    #Retrieve modules that matches the given language parameter
    @jwt_required
    def get(self):
        # Get the user's ID and check permissions
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401

        parser = reqparse.RequestParser()
        parser.add_argument('language', type=str, required=True)
        data = parser.parse_args()

        query = f"""
                SELECT module.*, group_module.groupID FROM module 
                INNER JOIN group_module ON group_module.moduleID=module.moduleID 
                WHERE module.language='{data['language']}'
                """
        records = get_from_db(query)
        modules = []
        for row in records:
            modules.append(convertToJSON(row)) 
        
        # Return module information
        return modules, 200
        

class RetrieveUserModules(Resource):
    #Get all the modules associated with the user's groups,p the modules they created,
    #and whether they have permission to delete that module or not
    #Design choice: TAs can only delete modules they created, Professors can delete modules
    #they created or their TAs created, and superadmins can delete any module
    @jwt_required
    def get(self):
        # Get the user's ID and check permissions
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401
        
        group_id = get_group_id()

        #if a regular student user, return modules associated with their groups (similar to /modules)
        if permission == 'st' and not is_ta(user_id, group_id):
            query = f"""
                SELECT `module`.*, `group_module`.`groupID` FROM `module` 
                INNER JOIN `group_module` ON `module`.`moduleID` = `group_module`.`moduleID` 
                INNER JOIN `group_user` ON `group_module`.`groupID` = `group_user`.`groupID` 
                WHERE `group_user`.`userID`={user_id}
                """
            result = get_from_db(query)

            modules = []
            for row in result:
                modules.append(convertToJSON(row))

            # Return module information
            return modules

        if permission == 'su':
            query = f"""
                    SELECT DISTINCT `module`.*, `group_module`.`groupID` FROM `module` 
                    LEFT JOIN `group_module` ON `module`.`moduleID` = `group_module`.`moduleID` 
                    LEFT JOIN `group_user` ON `group_module`.`groupID` = `group_user`.`groupID`
                    """
        else:
            query = f"""
                    SELECT DISTINCT `module`.*, `group_module`.`groupID` FROM `module` 
                    LEFT JOIN `group_module` ON `module`.`moduleID` = `group_module`.`moduleID` 
                    LEFT JOIN `group_user` ON `group_module`.`groupID` = `group_user`.`groupID` 
                    WHERE `group_user`.`userID`={user_id} OR `module`.`userID`={user_id}
                    """
        result = get_from_db(query)

        modules = []
        for row in result:
            modules.append(convertToJSON(row))

        TA_list = []
        if permission == 'pf':
            TA_list = GetCurrentTAList(user_id)

        if is_ta(user_id, group_id):
            for module in modules:
                module['owned'] = True if module['userID'] == user_id else False
        else:
            for module in modules:
                module['owned'] = True if module['userID'] == user_id or module['userID'] in TA_list or permission == 'su' else False

        return modules, 200


class RetrieveAllModules(Resource):
    # Get all modules in the database
    @jwt_required
    def get(self):
        # Get the user's ID and check permissions
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401
        
        group_id = get_group_id()

        if permission == 'st' and not is_ta(user_id, group_id):
            return "Invalid permission level", 401

        # Query to retrieve all modules
        query = f"SELECT `module`.*, `user`.userName FROM `module` INNER JOIN `user` ON `user`.userID = `module`.userID"
        result = get_from_db(query)
        
        # Attaching variable names to rows
        modules = []
        for row in result:
            modules.append(convertModuleToJSON(row)) 
        # Return module information
        return modules
        

# For acquiring the associated questions and answers with a module
class ModuleQuestions(Resource):
    # Get a list of question objects, which each contain a list of terms functioning as their answers
    # Requires moduleID
    @jwt_required
    def post(self):
        permission, user_id = validate_permissions()
        if not permission or not user_id:
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
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401
        
        module_id = get_module_id()
        if not module_id:
            return {'message':'Please provide the id of a module'}, 400
        
        # Get all decks associated with the group
        query = f'''
                SELECT module.*, group_module.groupID FROM module 
                INNER JOIN group_module ON group_module.moduleID=module.moduleID 
                INNER JOIN group_user ON group_module.groupID = group_user.groupID 
                WHERE group_user.userID={user_id} AND module.moduleID={module_id}
                '''
        result = get_from_db(query)

        module = None

        if result and result[0]:
            # Attaching variable names to rows\
            module = convertToJSON(result[0])
        
        # Return module information
        return module

    @jwt_required
    # Creating a new module
    def post(self):
        # groupID doesn't need to be passed is superadmin is creating a new module
        # and doesn't want to attach it to any groups
        group_id = get_group_id()
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401

        if not group_id and permission != 'su':
            return {'message':'Please provide the id of a group'}, 400

        if permission == 'st' and not is_ta(user_id, group_id):
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

        try:
            conn = mysql.connect()
            cursor = conn.cursor()
            # Posting to database
            query = f"""
                    INSERT INTO module (name, language, complexity, userID)
                    VALUES ('{name}', '{language}', {complexity}, {user_id});
                    """
            post_to_db(query)

            query = "SELECT MAX(moduleID) from module"
            moduleID = get_from_db(query) #ADD A CHECK TO SEE IF IT RETURNED SUCCESSFULLY

            if not moduleID or not moduleID[0]:
                raise CustomException("Error in creating a module", 500)

            if group_id:
                # Linking the newly created module to the group associated with the groupID            
                query = f"""INSERT INTO `group_module` (`moduleID`, `groupID`) 
                        VALUES ('{moduleID[0][0]}', '{group_id}')"""
                post_to_db(query)

            raise ReturnSuccess({"moduleID" : moduleID[0][0]}, 200)
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
    def put(self):
        # Parsing JSON
        # groupID doesn't need to be passed if professor or superadmin is updating a module
        parser = reqparse.RequestParser()
        parser.add_argument('moduleID', type=int, required=True)
        parser.add_argument('name', type=str, required=True)
        parser.add_argument('language', type=str, required=True)
        parser.add_argument('complexity', type=int, required=True)
        parser.add_argument('groupID', type=int, required=False)
        data = parser.parse_args()

        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            permission, user_id = validate_permissions()
            if not permission or not user_id:
                return "Invalid user", 401
            
            if permission == 'st' and not is_ta(user_id, group_id):
                return "User not authorized to do this", 401

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

            query = "SELECT `*` FROM `module` WHERE `moduleID`=%s"
            results = get_from_db(query, data['moduleID'])
            if not results or not results[0]:
                raise CustomException("Non existant module", 400)

            print(results)
            moduleObj = convertToJSON(results[0])

            raise ReturnSuccess(moduleObj, 200)
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
    # Deleting an existing module, requires moduleID
    def delete(self):
        # groupID only needs to be passed if the user is a TA for the group
        group_id = get_group_id()
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401

        TA_list = []
        if permission == 'pf':
            TA_list = GetCurrentTAList(user_id)

        if permission == 'st' and not is_ta(user_id, group_id):
            return {'Error' : 'User not authorized to do this'}, 401
        
        module_id = get_module_id()
        if not module_id:
            return {'Error' : 'Please provide the id of a module.'}, 400
        
        query = f"SELECT module.userID FROM module WHERE module.moduleID = {module_id}"
        module_user_id = get_from_db(query)
        if not module_user_id or not module_user_id[0]:
            return {'Error' : 'Invalid module ID'}, 400
        
        module_user_id = module_user_id[0][0]

        if (permission == 'pf' and module_user_id not in TA_list and module_user_id != user_id) or \
           (permission == 'ta' and module_user_id != user_id):
           return {'Error' : 'User not authorized to do this'}, 401

        try:
            conn = mysql.connect()
            cursor = conn.cursor()

            # Deleting module
            query = f"DELETE FROM module WHERE moduleID = {module_id};"
            post_to_db(query)

            raise ReturnSuccess('Successfully deleted module!', 200)
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


#  For attaching and detaching questions from modules
class AttachQuestion(Resource):
    @jwt_required
    def post(self):
        # groupID only needs to be passed if the user is a TA for the group
        group_id = get_group_id()
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401

        if permission == 'st' and not is_ta(user_id, group_id):
            return "User not authorized to do this", 401
        
        # Parsing JSON
        parser = reqparse.RequestParser()
        parser.add_argument('moduleID', type=int, required=True)
        parser.add_argument('questionID', type=int, required=False)
        data = parser.parse_args()
        module_id = data['moduleID']
        question_id = data['questionID']

        try:
            conn = mysql.connect()
            cursor = conn.cursor()
            # Attaching or detaching if already attached
            attached = attach_question(module_id, question_id, conn, cursor)
            # Response
            if attached:
                raise ReturnSuccess('Question has been linked to module.', 201)
            else:
                raise ReturnSuccess('Question has been unlinked from module.', 200)
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


#  For attaching and detaching terms from modules
class AttachTerm(Resource):
    @jwt_required
    def post(self):
        # groupID only needs to be passed if the user is a TA for the group
        group_id = get_group_id()
        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401

        if permission == 'st' and not is_ta(user_id, group_id):
            return "User not authorized to do this", 401

        # Parsing JSON
        parser = reqparse.RequestParser()
        parser.add_argument('moduleID', type=int, required=True)
        parser.add_argument('termID', type=int, required=True)
        data = parser.parse_args()
        module_id = data['moduleID']
        term_id = data['termID']

        try:
            conn = mysql.connect()
            cursor = conn.cursor()
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
                    raise CustomException('Term does not exist or MATCH question has been deleted internally.', 400)
            # Getting question id if question already existed
            if question_id == -1:
                question_id = result[0][0]

            # Attaching or detaching if already attached
            attached = attach_question(module_id, question_id, conn, cursor)
            # Response
            if attached:
                 raise ReturnSuccess('Term has been linked to module.', 201)
            else:
                raise ReturnSuccess('Term has been unlinked from module.', 200)
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


#  For attaching and detaching modules from group(s)
class AddModuleGroup(Resource):
    @jwt_required
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('moduleID', type=int, required=True)
        parser.add_argument('groupID', type=int, required=True)
        data = parser.parse_args()

        permission, user_id = validate_permissions()
        if not permission or not user_id:
            return "Invalid user", 401

        group_id = data['groupID']
        if permission == 'st' and not is_ta(user_id, group_id):
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


def convertModuleToJSON(module):
    if len(module) < 4:
        return errorMessage("Wrong amount of values in the object. Module record has 4 fields, or 5 with groupID")
    
    moduleObj = {}
    moduleObj['moduleID'] = module[0]
    moduleObj['name'] = module[1]
    moduleObj['language'] = module[2]
    moduleObj['complexity'] = module[3]
    moduleObj['userID'] = module[4]

    if len(module) > 5:
        moduleObj['username'] = module[5]
    
    return moduleObj


def GetCurrentTAList(professorID):
    TA_list = []
    get_ta_query = f"""
                    SELECT user.userID FROM user 
                    INNER JOIN group_user on group_user.userID = user.userID 
                    AND group_user.groupID IN 
                    (SELECT group_user.groupID from group_user WHERE group_user.userID = {professorID}) 
                    WHERE group_user.accessLevel = 'ta'
                    """
    ta_results = get_from_db(get_ta_query)
    if ta_results and ta_results[0]:
        for ta in ta_results:
            TA_list.append(ta[0])
    return TA_list


def convertToJSON(moduleRecord):
    if len(moduleRecord) < 4:
        return errorMessage("Wrong amount of values in the object. Module record has 4 fields, or 5 with groupID")
    
    moduleObj = {}
    moduleObj['moduleID'] = moduleRecord[0]
    moduleObj['name'] = moduleRecord[1]
    moduleObj['language'] = moduleRecord[2]
    moduleObj['complexity'] = moduleRecord[3]
    moduleObj['userID'] = moduleRecord[4]

    if len(moduleRecord) > 5:
        moduleObj['groupID'] = moduleRecord[5]
    
    return moduleObj
