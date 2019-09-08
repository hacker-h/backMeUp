#!/usr/bin/env python
"""
This is the upload component of backMeUp.
It zips, encrypts and uploads your backup into your Google Drive.
"""

from __future__ import print_function, unicode_literals

import io
import logging
import ntpath
import os
import os.path
import pickle
import subprocess
import sys
from datetime import datetime
from time import sleep

import yaml
from google.auth.transport.requests import Request
from googleapiclient import errors
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

# use fork with fixed redirect url
from myflow import InstalledAppFlow
# from google_auth_oauthlib.flow import InstalledAppFlow

# TODO add doc strings for all functions
# TODO flake8 conformity
# TODO pylint conformity

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/drive']

GOOGLE_DRIVE_BACKUP_DIRECTORY_NAME = "backMeUp"
GOOGLE_DRIVE_FOLDER_MIME_TYPE = 'application/vnd.google-apps.folder'

MANDATORY_VOLUME_PATH = "/mandatoryVolume"

GPG_PUBLIC_KEY_PATH = "%s/key.pub.asc" % MANDATORY_VOLUME_PATH
GPG_PRIVATE_KEY_PATH = "%s/key.sec.asc" % MANDATORY_VOLUME_PATH
TEMP_DIR_FOR_BACKUPS = "/tmp/backups"

# suppress known library error
google_logger = logging.getLogger("googleapiclient.discovery_cache")
google_logger.setLevel(logging.CRITICAL)

# configure logging
logger = logging.getLogger("back_me_up")
logging.basicConfig()
logger.setLevel(logging.INFO)

def check_whether_mandatory_volume_was_passed():
    """
    Check whether mandatoryVolume was properly passed
    """
    if not os.path.exists(MANDATORY_VOLUME_PATH):
        logger.error("mandatoryVolume was not passed to '%s' missing!", MANDATORY_VOLUME_PATH)
        exit(1)
    if not os.path.isdir(MANDATORY_VOLUME_PATH):
        logger.error("mandatoryVolume '%s' should be a directory, not a file!", MANDATORY_VOLUME_PATH)
        exit(1)

def backup_path_is_empty(backup_path):
    if not os.path.exists(backup_path):
        logger.debug("backup path '%s' does not exist.", backup_path)
        return True
    if not os.path.isdir(backup_path):
        logger.debug("backup path '%s' is a single file")
        return False
    files_in_backup_path = os.listdir(backup_path)
    logger.debug("Found %d files in backup path '%s':", len(files_in_backup_path), backup_path)
    return len(files_in_backup_path) == 0

def import_public_gpg_key():
    if not "GPG_KEY_ID" in os.environ:
        logger.error("GPG_KEY_ID is not set")
        exit(1)
    logger.debug("Importing GPG key..")
    bash_command = "gpg --import %s" % GPG_PUBLIC_KEY_PATH
    process = subprocess.Popen(bash_command.split(), stdout=subprocess.PIPE)
    output, error = process.communicate()
    logger.debug(output)
    if error:
        logger.error("Failed to import GPG Key.")
        exit(1)

def import_private_gpg_key():
    if not "GPG_KEY_ID" in os.environ:
        logger.error("GPG_KEY_ID is not set")
        exit(1)
    logger.debug("Importing GPG key..")
    bash_command = "gpg --import %s" % GPG_PRIVATE_KEY_PATH
    process = subprocess.Popen(bash_command.split(), stdout=subprocess.PIPE)
    output, error = process.communicate()
    logger.debug(output)
    if error:
        logger.error("Failed to import GPG Key.")
        exit(1)

def prepare_temp_dir_for_backup():
    try:
        os.mkdir(TEMP_DIR_FOR_BACKUPS)
        logger.debug("%s was successfully created " % TEMP_DIR_FOR_BACKUPS) 
    except FileExistsError:
        logger.debug("%s already exists" % TEMP_DIR_FOR_BACKUPS)

def zip_file_or_directory(file_or_directory_path, zip_file_path):
    bash_command = "zip -q -r %s %s" % (zip_file_path, file_or_directory_path)
    process = subprocess.Popen(bash_command.split(), stdout=subprocess.PIPE)
    output, error = process.communicate()
    logger.debug(output)
    if error:
        logger.error("Failed to zip path '%s', aborting..", file_or_directory_path)
        exit(1)

def encrypt_zip_file(zip_file_path, gpg_file_path):
    logger.debug("encrypting zipfile '%s'..", zip_file_path)
    bash_command = "gpg --output %s --encrypt --always-trust --recipient %s %s" % (
        gpg_file_path, os.environ["GPG_KEY_ID"], zip_file_path)

    process = subprocess.Popen(bash_command.split(), stdout=subprocess.PIPE)
    output, error = process.communicate()
    logger.debug(output)
    if error:
        logger.error("Failed to encrypt backup files, aborting..")
        exit(1)

def delete_zip_file(zip_file_path):
    logger.debug("Deleting zipfile '%s'..", zip_file_path)
    os.remove(zip_file_path)
    logger.debug("%s deleted", zip_file_path)

def delete_gpg_file(gpg_file_path):
    logger.debug("Deleting local gpg file '%s'...", gpg_file_path)
    os.remove(gpg_file_path)
    logger.debug("'%s' successfully deleted", gpg_file_path)

def folder_name_matches(google_drive_file_dict):
    return google_drive_file_dict['name'] == GOOGLE_DRIVE_BACKUP_DIRECTORY_NAME

def is_not_deleted(google_drive_file_dict):
    return not google_drive_file_dict['trashed']

def is_folder(google_drive_file_dict):
    return google_drive_file_dict['mimeType'] == GOOGLE_DRIVE_FOLDER_MIME_TYPE

def create_or_fetch_credentials():
    credentials = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            credentials = pickle.load(token)

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            credentials = flow.run_local_server(host='', redirect_host='localhost',
                                                open_browser=False, port=80)
    # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(credentials, token)
    return credentials

def get_drive_backup_folder(service, non_deleted_items):
    potential_folders = [item for item in non_deleted_items if is_folder(item) and folder_name_matches(item)]
    if len(potential_folders) > 1:
        logger.error("Found %d duplicates of folder '%s' in your Google Drive, make sure it is unique!", len(potential_folders), GOOGLE_DRIVE_BACKUP_DIRECTORY_NAME)
        exit(1)
    if len(potential_folders) == 0:
        logger.info("Creating drive folder '%s'..", GOOGLE_DRIVE_BACKUP_DIRECTORY_NAME)
        parent_folder = service.files().create(body={'name':GOOGLE_DRIVE_BACKUP_DIRECTORY_NAME, 'mimeType':GOOGLE_DRIVE_FOLDER_MIME_TYPE}).execute()
    if len(potential_folders) == 1:
        logger.debug("folder '%s' already exists, reusing it..", GOOGLE_DRIVE_BACKUP_DIRECTORY_NAME)
        parent_folder = potential_folders[0]
    logger.debug("parentfolder: %s", parent_folder)
    return parent_folder

def upload_file(service, file_name, file_path):
    # Check if the file already exists
    non_deleted_drive_items = get_non_deleted_items(service)
    parent_folder_id = get_drive_backup_folder(service, non_deleted_drive_items)['id']
    matching_drive_files = get_matching_drive_files(non_deleted_drive_items, parent_folder_id, file_name)
    # Create a new file
    if len(matching_drive_files) == 0:
        logger.info("Uploading file '%s'..", file_name)
        file_metadata = {'name': file_name, 'parents': [parent_folder_id]}
        media = MediaFileUpload(file_path, mimetype='text/plain')
        drive_file = service.files().create(body=file_metadata, media_body=media).execute()
        logger.debug("File '%s' created successfully.", file_name)
    # Create a new revision of the existing file
    if len(matching_drive_files) == 1:
        logger.info("Uploading a new revision of '%s'..", file_name)
        drive_file = matching_drive_files[0]
        media = MediaFileUpload(file_path, mimetype='text/plain')
        updated_file = service.files().update(fileId=drive_file['id'], media_body=media).execute()
        logger.debug("Updated file '%s': %s", file_name, updated_file)
        revisions = service.revisions().list(fileId=drive_file['id']).execute()
        logger.debug("Revisions of file '%s': %s", file_name, revisions)

def get_non_deleted_items(service):
    all_items = service.files().list(fields="nextPageToken, files(id, name, mimeType, parents, size, trashed)").execute()["files"]
    non_deleted_items = [item for item in all_items if is_not_deleted(item)]
    return non_deleted_items

def get_matching_drive_files(non_deleted_items, parent_folder_id, file_name):
    potential_files = [item for item in non_deleted_items if not is_folder(item) and item['name'] == file_name and item['parents'] == [parent_folder_id]]
    if len(potential_files) > 1:
        logger.error("Found %d duplicates of file '%s' in your Google Drive, make sure it is unique!", len(potential_files), file_name)
        exit(1)
    return potential_files

def download_latest_revision(service, drive_file_name, destination_path):
    # Check if the file exists
    non_deleted_drive_items = get_non_deleted_items(service)
    parent_folder_id = get_drive_backup_folder(service, non_deleted_drive_items)['id']
    matching_drive_files = get_matching_drive_files(non_deleted_drive_items, parent_folder_id, drive_file_name)
    if len(matching_drive_files) > 1:
        logger.error("Drive Filename '%s' is not unique!", drive_file_name)
        exit(1)
    if len(matching_drive_files) == 0:
        logger.error("Drive Filename '%s' does not exist!", drive_file_name)
        exit(1)
    drive_file = matching_drive_files[0]
    logger.info("Downloading file '%s' to '%s'", drive_file_name, destination_path)
    with open(destination_path, "wb") as file_handle:
        request = service.files().get_media(fileId=drive_file['id'])
        downloader = MediaIoBaseDownload(file_handle, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            logger.debug("Download %d%%.", int(status.progress() * 100))

def usage():
    logger.error("Usage: back_me_up download <file_name> <target_path>")
    logger.error("       back_me_up upload <source_path>")

def upload(service, backup_path):
    if backup_path_is_empty(backup_path):
        logger.error("Backup path '%s' is empty. Exiting.", backup_path)
        exit(1)
    prepare_temp_dir_for_backup()

    if os.path.isdir(backup_path):
        files_in_backup_path = os.listdir(backup_path)
    else:
        backup_path, _file_name = os.path.split(backup_path)
        files_in_backup_path = [_file_name]
    total_files_to_backup = len(files_in_backup_path)
    file_counter = 0
    logger.info("Found '%d' directories/files to backup", total_files_to_backup)
    logger.debug("files_in_backup_path='%s'", files_in_backup_path)
    logger.debug("backup_path='%s'", backup_path)
    # fetch, zip, encrypt and backup all directories/files in the backup path
    for file_name in files_in_backup_path:
        file_counter += 1
        # build required paths
        file_path = "%s/%s" % (backup_path, file_name)
        if file_path.startswith("//"):
            logger.debug("Detected two leading slashes, removing one")
            _new_file_path = file_path[1:]
            logger.debug("'%s' -> '%s'", file_path, _new_file_path)
            file_path = _new_file_path
        logger.debug("file_path='%s'", file_path)
        zip_file_path = "%s/%s.zip" % (TEMP_DIR_FOR_BACKUPS, file_name)
        logger.debug("zip_file_path='%s'", zip_file_path)
        gpg_file_path = "%s.gpg" % zip_file_path
        logger.debug("gpg_file_path='%s'", gpg_file_path)

        # do a backup
        zip_file_or_directory(file_path, zip_file_path)
        encrypt_zip_file(zip_file_path, gpg_file_path)
        logger.info("%d/%d files", file_counter, total_files_to_backup)
        upload_file(service, "%s.zip.gpg" % file_name, gpg_file_path)

        # clean up
        delete_zip_file(zip_file_path)
        delete_gpg_file(gpg_file_path)
    logger.info("backup finished!")

def arguments_match_upload_mode(arguments):
    if arguments and len(arguments) == 2 and arguments[0] == "upload":
        return True
    return False

def arguments_match_download_mode(arguments):
    if arguments and len(arguments) == 3 and arguments[0] == "download":
        return True
    return False

def decrypt_gpg_file(gpg_file_path, target_path):
    logger.debug("decrypting gpg file '%s'..", gpg_file_path)
    bash_command = "gpg --output %s --decrypt --always-trust --recipient %s %s" % (
        target_path, os.environ["GPG_KEY_ID"], gpg_file_path)

    process = subprocess.Popen(bash_command.split(), stdout=subprocess.PIPE)
    output, error = process.communicate()
    logger.debug(output)
    if error:
        logger.error("Failed to encrypt backup files, aborting..")
        exit(1)

def unzip_file(zip_file_path, destination_path):
    bash_command = "unzip %s -d %s" % (zip_file_path, destination_path)
    process = subprocess.Popen(bash_command.split(), stdout=subprocess.PIPE)
    output, error = process.communicate()
    logger.debug(output)
    if error:
        logger.error("Failed to unzip backup file '%s', aborting..", zip_file_path)
        exit(1)

def download(service, file_name, destination_path):
    # download desired file to destination path
    prepare_temp_dir_for_backup()
    gpg_file_path = "%s/%s" % (TEMP_DIR_FOR_BACKUPS, file_name)
    # remove .gpg ending
    zip_file_target_path = gpg_file_path[:-4]
    download_latest_revision(service, file_name, gpg_file_path)
    # decrypt .gpg file to zipfile
    decrypt_gpg_file(gpg_file_path, zip_file_target_path)
    # unzip zipfile to destination path
    unzip_file(zip_file_target_path, destination_path)
    # delete .gpg file and zipfile
    delete_gpg_file(gpg_file_path)
    delete_zip_file(zip_file_target_path)

def main():
    """
    Main function
    """
    arguments = sys.argv[1:]
    check_whether_mandatory_volume_was_passed()

    service = build('drive', 'v3', credentials=create_or_fetch_credentials())
    if arguments_match_upload_mode(arguments):
        # backup_path = "/backMeUp"
        backup_path = arguments[1]
        import_public_gpg_key()
        upload(service, backup_path)
    elif arguments_match_download_mode(arguments):
        file_name = arguments[1]
        if not file_name.endswith(".gpg"):
            logger.error("The file to download '%s' is no '.gpg' file. Aborting..")
            exit(1)
        file_path = arguments[2]
        import_private_gpg_key()
        download(service, file_name, file_path)
    else:
        logger.error("Invalid arguments")
        usage()
        exit(1)

try:
    if __name__ == '__main__':
        main()
except KeyboardInterrupt:
    quit("script stopped by user")
