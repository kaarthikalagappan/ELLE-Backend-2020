### The Deletes Folder
This folder is where all the media files are moved to before they are permanently deleted from the server. <br />
When the user deletes a media, the media is moved to this directory temporarily and then it is permanently deleted when the API call successfully deletes the media record on the database. If the API call fails, the media is moved back to its original place.