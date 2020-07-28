DROP TABLE IF EXISTS `user`;
DROP TABLE IF EXISTS 'group';
DROP TABLE IF EXISTS 'group_user';
DROP TABLE IF EXISTS 'tokens';
DROP TABLE IF EXISTS 'module';
DROP TABLE IF EXISTS 'question';
DROP TABLE IF EXISTS 'module_question';
DROP TABLE IF EXISTS 'term';
DROP TABLE IF EXISTS 'answer';
DROP TABLE IF EXISTS 'tag';
DROP TABLE IF EXISTS 'image';
DROP TABLE IF EXISTS 'audio';
DROP TABLE IF EXISTS 'alternate_form';
DROP TABLE IF EXISTS 'game_log';
DROP TABLE IF EXISTS 'session';
DROP TABLE IF EXISTS 'logged_answer';

-- Stores user informationM)
/* permissionGroup:
us: User
ad: Admin
*/
CREATE TABLE 'user' (
    userID INT PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(20) NOT NULL,
    'password' VARCHAR(100) NOT NULL,
    passwordReset VARCHAR(50),
    permissionGroup CHAR(2),
    lastToken VARCHAR(45)
)

-- User groups connect users in a class to their available modules
CREATE TABLE 'group' (
    groupID INT PRIMARY KEY AUTOINCREMENT,
    groupName VARCHAR(50) NOT NULL,
    'password' VARCHAR(100) NOT NULL
)

-- Link table for Groups to Users
CREATE TABLE 'group_user' (
    userID INT NOT NULL,
    groupID INT NOT NULL,
    isAdmin TINYINT DEFAULT 0,
    FOREIGN KEY (userID) REFERENCES user(userID) ON DELETE CASCADE,
    FOREIGN KEY (groupID) REFERENCES group(groupID) ON DELETE CASCADE
)

-- Stores temporary web tokens
CREATE TABLE 'tokens' (
    expired VARCHAR(45)
)

-- Stores modules, a grouped set of questions
/* Languages use two-character codes */
/* Complexity:
0   (Contains only translation questions, fully compatible with all projects)
1   (Does not contain longform questions, but may contain other questions)
2   (May contain all question types)
*/
CREATE TABLE 'module' (
    moduleID INT PRIMARY KEY AUTOINCREMENT,
    groupID INT,
    'name' VARCHAR(250) NOT NULL,
    'language' varchar(2),
    complexity tinyint,
    FOREIGN KEY (groupID) REFERENCES group(groupID) ON DELETE CASCADE
)

-- Questions, which have at least one answer and optional audio/image/text
/* Types:
MATCH       (Base type, uses a term as the question prompt, only one answer)
PHRASE      (Identical to MATCH, but for whole phrases, only one answer)
IMAGE       (Select a word corresponding to an image, may have multiple answers)
AUDIO       (Select a word corresponding to audio, may have multiple answers)
LONGFORM    (Questions with a full text prompt, may have multiple answers)
*/
CREATE TABLE 'question' (
    questionID INT PRIMARY KEY AUTOINCREMENT,
    audioID INT,
    imageID INT,
    'type' varchar(10) NOT NULL,
    questionText varchar(50),
    FOREIGN KEY (audioID) REFERENCES audio(audioID),
    FOREIGN KEY (imageID) REFERENCES image(imageID)
)

-- Link table for Modules to Questions
CREATE TABLE 'module_question' (
    moduleID INT NOT NULL,
    questionID INT NOT NULL,
    FOREIGN KEY (moduleID) REFERENCES module(moduleID) ON DELETE CASCADE,
    FOREIGN KEY (questionID) REFERENCES question(questionID) ON DELETE CASCADE
)

-- Terms, words and their translations along with other information
/* Types:
NN  (Noun)
VR  (Verb)
AJ  (Adjective)+
AV  (Adverb)
PH  (Phrase)
*/
/* Genders:
MA (Male)
FE (Female)
NA (Nongendered)
*/
/* Front/Back clarification
Front is the word in the foreign language (prompt),
Back is the word in the native language (answer)
*/
CREATE TABLE 'term' (
    termID INT PRIMARY KEY AUTOINCREMENT,
    imageID INT,
    audioID INT,
    front varchar(50) NOT NULL,
    back varchar(50) NOT NULL,
    'type' varchar(2),
    gender varchar(1),
    'language' varchar(2),
    FOREIGN KEY (imageID) REFERENCES image(imageID),
    FOREIGN KEY (audioID) REFERENCES audio(audioID)
)

-- Link Table for Terms and Questions
CREATE TABLE 'answer' (
    questionID INT NOT NULL,
    termID INT NOT NULL,
    FOREIGN KEY (questionID) REFERENCES question(questionID),
    FOREIGN KEY (termID) REFERENCES term(termID)
)

-- Text tags associated with terms.  One term may have multiple tags.
CREATE TABLE 'tag' (
    termID INT PRIMARY KEY AUTOINCREMENT,
    tagName varchar(20) NOT NULL,
    FOREIGN KEY (termID) REFERENCES term(termID) ON DELETE CASCADE
)

-- Reusable images associated with terms and questions
CREATE TABLE 'image' (
    imageID INT PRIMARY KEY AUTOINCREMENT,
    imageLocation varchar (225)
)

-- Reusable audio associated with terms and questions
CREATE TABLE 'audio' (
    audioID INT PRIMARY KEY AUTOINCREMENT,
    audioLocation varchar (225)
)

-- Alternate forms of existing words
CREATE TABLE 'alternate_form' (
    formID INT PRIMARY KEY AUTOINCREMENT,
    termID INT,
    'type' varchar(2),
    front varchar(50)
    FOREIGN KEY (termID) REFERENCES term(termID) ON DELETE CASCADE
)

-- Game data logging for older games
/* Platforms:
mo0     (Previous Mobile Game)
vr0     (Previous VR Game)
cp     (2020 PC Game)
mo     (2020 Mobile Game)
vr     (2020 VR Game)
*/
CREATE TABLE 'game_log' (
    logID INT PRIMARY KEY AUTOINCREMENT,
    userID INT,
    deckID INT,
    correct INT,
    incorrect INT,
    platform varchar(3),
    FOREIGN KEY (userID) REFERENCES user(termID),
    FOREIGN KEY (deckID) REFERENCES deck(termID) ON DELETE CASCADE
)

-- Game data logging for modern games
CREATE TABLE 'session' (
    sessionID INT PRIMARY KEY AUTOINCREMENT,
    userID INT NOT NULL,
    moduleID INT NOT NULL,
    sessionDate varchar(15),
    playerScore int,
    startTime varchar(15),
    endTime varchar(15),
    platform varchar(3),
    FOREIGN KEY (userID) REFERENCES user(termID),
    FOREIGN KEY (moduleID) REFERENCES module(moduleID) ON DELETE CASCADE
)

-- Individual answer logging
/* Correct
0   (Wrong)
1   (Right)
*/
CREATE TABLE 'logged_answer' (
    logID INT PRIMARY KEY AUTOINCREMENT,
    questionID INT,
    termID INT,
    sessionID INT,
    correct TINYINT,
    FOREIGN KEY (questionID) REFERENCES question(questionID) ON DELETE CASCADE,
    FOREIGN KEY (termID) REFERENCES term(termID) ON DELETE CASCADE,
    FOREIGN KEY (sessionID) REFERENCES session(sessionID) ON DELETE CASCADE
)