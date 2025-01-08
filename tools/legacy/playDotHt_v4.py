# Based on v3
#
# Adds support for repo-friendly & bucket-friendly paths
# Makes paths "Windows friendly"

from abc import abstractmethod
import sys
import os
import threading
import time
from typing import List
import pandas as pd
import requests
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace

#experiment
import pyht

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Constants for API
API_URL = "https://api.play.ht/api/v1/convert"
STATUS_URL = "https://api.play.ht/api/v1/articleStatus"

# Trying to get save files co-erced into our desired path
audio_base_dir = "audio_files"

def create_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)
    return path


################################################
# API helper methods
################################################

@dataclass(frozen=True)
class TranscriptionTx:
    """
    This immutable dataclass represents a transaction to convert text to speech
    It carries two types of data:
        the data necessary to make the API calls on Play.ht, see https://docs.play.ht/reference/api-convert-tts-standard-premium-voices
        the data we use internally to track the status of the transaction
    """
    voice: str
    lang_code: str
    item_id: str
    #don't know if we need this in the transaction
    #labels: str #Currently used for the task name
    text: str
    transcription_id: str = None
    # below are the data we use internally to track the status of the transaction
    status: str = 'pending'  # pending, in_progress, error, <audio_file_url> - pending means not yet submitted for conversion
    resp_body: str = None # dump of the response body

def convert_tts(transaction: TranscriptionTx, user_id, auth_token) -> TranscriptionTx:
    """
    Convert text to speech using the Play.ht API.

    Args:
        transaction (TranscriptionTx): The transaction object containing the text, voice, and status.
        user_id (str): The user ID for authentication.
        auth_token (str): The authentication token.

    Returns:
        TranscriptionTx: The updated transaction object with the transcription ID and status.
    """
    headers = {
        'Authorization': auth_token,
        'X-USER-ID': user_id,
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    data = {
        "content": [transaction.text],
        "voice": transaction.voice,
        "title": "Individual Audio",
        "trimSilence": True
    }
    # logging.debug(f"convert_tts: submitting item={transaction.item_id}")
    response = requests.post(API_URL, headers=headers, json=data) # see https://docs.play.ht/reference/api-convert-tts-standard-premium-voices
    if response.status_code == 201:
        result = response.json()
        logging.info(f"convert_tts: response for item={transaction.item_id}: transcriptionId={result['transcriptionId']}")
        return replace(transaction, transcription_id=result['transcriptionId'], status='in_progress', resp_body=result)
    else:
        logging.error(f"convert_tts: no response for item={transaction.item_id}: status code={response.status_code}")
        return replace(transaction, status='error', resp_body=f'NO RESPONSE (convert), status code={response.status_code}')

def check_status(transaction: TranscriptionTx, user_id, auth_token) -> TranscriptionTx:
    """
    Check the status of a transcription transaction.

    Args:
        transaction (TranscriptionTx): The transaction object containing the transcription ID and status.
        user_id (str): The user ID for authentication.
        auth_token (str): The authentication token.

    Returns:
        TranscriptionTx: The updated transaction object with the status and audio URL if the transcription is completed.
    """
    if transaction.transcription_id is None:
        logging.error("check_status: No transcription ID, aborting")
        raise Exception("No transcription ID, aborting")

    headers = {
        'Authorization': auth_token,
        'X-USER-ID': user_id,
        'Accept': 'application/json'
    }
    # logging.debug(f"check_status: checking item={transaction.item_id}")
    response = requests.get(f"{STATUS_URL}?transcriptionId={transaction.transcription_id}", headers=headers)
    if response.status_code == 200:
        result = response.json()
        if result.get('error', False): # some error may not mean that the transaction failed !!! #TODO figure out how to distinguish unrecoverable errors
            logging.error(f"check_status: item={transaction.item_id}: errorMessage={result['errorMessage']}")
            return replace(transaction, status='error', resp_body=result)
        if result.get('converted', False):
            logging.info(f"check_status: item={transaction.item_id} is completed")
            return replace(transaction, status=result['audioUrl'], resp_body=result)
        else:
            logging.info(f"check_status: item={transaction.item_id} is still in progress")
            return transaction
    else:
        logging.error(f"check_status: status_code={response.status_code}")
        return replace(transaction, resp_body=f'NO RESPONSE (status), status code={response.status_code}') # we should not assume that the transaction failed!


################################################
# Transactions Status Persistence
################################################

class StatusDataStore:
    @abstractmethod
    def __init__(self, input_file: str):
        if input_file is None:
            raise ValueError("input file cannot be None")
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"input file '{input_file}' not found")
        self.input_file = input_file
        pass
    @abstractmethod
    def extract_transactions(self) -> List[TranscriptionTx]:
        pass
    @abstractmethod
    def persist_tx_status(self, transaction: TranscriptionTx) -> None:
        pass

class CsvManager(StatusDataStore):
    """
    A class to manage the output CSV files.
    The expected columns related to tts transactions follow the following pattern:
    'tts_{self.lang_code}_{self.voice}_{column_name}'
    """

    @dataclass(frozen=True)
    class LockedOutputFile:
        lock: threading.Lock
        filepath: str

    def __init__(self, input_file, item_id_column):
        super().__init__(input_file)
        self.item_id_column = item_id_column
        self.lock = threading.Lock()
        self.locked_output_file = None
        self.overwrite_input_file = False
        self.labels = 'labels' # should probably load this from somewhere 

    def set_csv_output_file(self, output_file_name: str):
        """
        Instructs the store to write transaction statuses to a new specific csv file
        """
        if self.overwrite_input_file is True:
            raise ValueError("set_csv_output_file: input file overwriting is enabled, aborting")
        if output_file_name is None:
            raise ValueError("set_csv_output_file: output file cannot be None, aborting")
        elif os.path.exists(output_file_name):
            errorMessage = f"set_csv_output_file: '{output_file_name}' already exists, aborting."
            logging.error(errorMessage)
            raise FileExistsError(errorMessage)
        
        self.locked_output_file = CsvManager.LockedOutputFile(self.lock, output_file_name)

    def set_overwrites_csv_input_file(self):
        """
        Instructs the store to write transaction statuses back into the input csv file
        """
        if self.locked_output_file is not None:
            raise ValueError("set_overwrites_csv_input_file: output file was set, aborting")

        self.overwrite_input_file = True
        self.locked_output_file = CsvManager.LockedOutputFile(self.lock, self.input_file)

    def set_target_locale_and_voice(self, lang_code, voice):
        """
        Instructs the store to prepare for writing transaction statuses for a specific locale and voice.

        To avoid duplicating the header row when writing a transaction status, we
        here ensure the columns exist in the output csv ahead of processing the transactions
        """
        if self.locked_output_file is None:
            raise ValueError("set_target_locale_and_voice: output not set, aborting")
        
        # assign the locale and voice to our instance
        self.lang_code = lang_code
        self.voice = voice
        #  Ensure the columns exist in the output CSV file
        tx_columns = CsvManager.get_tx_columns(lang_code=lang_code, voice=voice)
        with self.locked_output_file.lock:
            if self.overwrite_input_file is True:
                CsvManager.__ensure_columns_exist(csv_file=self.locked_output_file.filepath, columns=tx_columns)
            else:
                CsvManager.__ensure_copy_csv_and_columns_exist(input_file=self.input_file, output_file=self.locked_output_file.filepath, columns=tx_columns)

    def __ensure_columns_exist(csv_file: str, columns: List[str]):
        """
        !!! ATTENTION !!! Make sure to call this function within a lock to avoid concurrent writes to the csv file.
        """
        if os.path.isfile(csv_file):
            logging.info(f"__ensure_columns_exist: reading csv file={csv_file}")
            df = pd.read_csv(csv_file)
        else:
            errorMessage = f"__ensure_columns_exist: no existing file={csv_file}, aborting"
            logging.error(errorMessage)
            raise FileNotFoundError(errorMessage)
            
        # Ensure the columns exist in the DataFrame
        for column in columns:
            if column not in df.columns:
                df[column] = None

        # Write the DataFrame to the CSV file
        df.to_csv(csv_file, index=False)

    def __ensure_copy_csv_and_columns_exist(input_file: str, output_file: str, columns: List[str]):
        """
        !!! ATTENTION !!! Make sure to call this function within a lock to avoid concurrent writes to the csv file.
        """
        # If the file exists, read it
        if os.path.isfile(output_file):
            errorMessage = f"__ensure_copy_csv_and_columns_exist: output file already exists={output_file}, aborting"
            logging.error(errorMessage)
            raise FileExistsError(errorMessage)
        
        # read DataFrame from input file
        df = pd.read_csv(input_file)

        # Ensure the columns exist in the DataFrame
        for column in columns:
            if column not in df.columns:
                df[column] = None

        logging.info(f"__ensure_copy_csv_and_columns_exist: creating output csv file={output_file}")
        # Write the DataFrame to the CSV file
        df.to_csv(output_file, index=False)
        
    def __parse_input_file(input_file_path: str, required_columns: List[str], tx_columns: List[str]) -> pd.DataFrame:
        """
        Parse the transactions info from input file into a DataFrame.

        Args:
            input_file_path (str): The path of the input file.
            required_columns (List[str]): A list of column names that are required in the input file.
            tx_columns (List[str]): A list of column names for the transaction status.
        Returns:
            pd.DataFrame: The parsed DataFrame.

        Raises:
            Exception: If any of the required columns are missing in the input file.
        """
        logging.info(f"parse_input_file: requiring columns={required_columns}")
        data_frame = pd.read_csv(input_file_path)
        # validate required columns
        for col in required_columns:
            if col not in data_frame.columns:
                errorMessage = f"parse_input_file: Missing column '{col}', aborting."
                logging.error(errorMessage)
                raise Exception(errorMessage)
        # add tx columns if they do not exist
        for col in tx_columns:
            if col not in data_frame.columns:
                data_frame[col] = 'pending'
        return data_frame
    
    def extract_transactions(self) -> List[TranscriptionTx]:
        if self.lang_code is None or self.voice is None:
            raise ValueError("extract_transactions: locale and voice not set, aborting")
        
        tx_columns = CsvManager.get_tx_columns(lang_code=self.lang_code, voice=self.voice)
        required_columns = [self.item_id_column, self.lang_code, self.labels]
        data_frame = CsvManager.__parse_input_file(self.input_file, required_columns, tx_columns)

        if data_frame is None:
            errorMessage = f"extract_transactions: could not parse input file, aborting"
            logging.error(errorMessage)
            raise Exception(errorMessage)

        transactions_from_input = CsvManager.extract_transactions_from_df(
            df=data_frame,
            item_id_column=self.item_id_column,
            lang_code=self.lang_code,
            voice=self.voice,
            labels=self.labels
            )
        #TODO perhaps log this snapshot to a text file
        return transactions_from_input

    def persist_tx_status(self, transaction: TranscriptionTx):
        """
        Persists the status of a transcription transaction to the output csv file.
        It does so behind a lock to avoid concurrent writes from multiple threads and corrupting the file.
        """
        if self.locked_output_file is None:
            errorMsg = f"persist_tx_status: no output file set, aborting"
            logging.error(errorMsg)
            raise Exception(errorMsg)
        
        output_csv_file = self.locked_output_file.filepath
        output_csv_lock = self.locked_output_file.lock
        with output_csv_lock:
            # we need to use the lock to prevent concurrent write to the output csv file
            # but also to prevent getting out-of-date data frames as we read from the csv file

            # TODO: avoid reading and writing the entire file and update only the corresponding row

            df = pd.read_csv(output_csv_file)
            df = CsvManager.dump_tx_status_to_df(transaction, df, self.item_id_column)
            CsvManager.__persist_df_to_csv(df, output_csv_file)

    def __persist_df_to_csv(df: pd.DataFrame, output_csv_file):
        """
        DO NOT USE THIS FUNCTION DIRECTLY. USE persist_tx_status(transaction: TranscriptionTx) INSTEAD.
        Writing to the CSV file is not inherently thread-safe and concurrent writes from multiple threads will corrupt the file.
        """
        # write to file
        df.to_csv(
            output_csv_file,
            mode='w',
            index=False,
            header=True,
            encoding='utf-8', #TODO check if this is necessary. Google docs export to csv likely uses utf-8
            )

    ## HELPER FUNCTIONS
    def extract_transactions_from_df(df: pd.DataFrame, item_id_column: str, lang_code: str, voice: str, labels: str) -> List[TranscriptionTx]:
        transactions = []
        for _, row in df.iterrows():
            transaction = CsvManager.df_row_to_transcription_tx(row=row, item_id_column=item_id_column, lang_code=lang_code, voice=voice, labels=labels)
            transactions.append(transaction)
        return transactions
        
    def df_row_to_transcription_tx(row: pd.Series, item_id_column, lang_code: str, voice: str) -> TranscriptionTx:
        """
        Parse a TranscriptionTx object from a given data frame row.
        
        !!! Important: Note that `lang_code` and `voice` parameters are also used to derive the expected transaction status column names.
        """
        tx_status = row[CsvManager.get_tx_status_column(lang_code=lang_code, voice=voice)]
        if pd.isna(tx_status):
            logging.warning(f"df_row_to_transcription_tx: missing status for item={row[item_id_column]}")
            tx_status = 'pending'
        return TranscriptionTx(
            voice=voice,
            lang_code=lang_code,
            item_id=            row[item_id_column],
            text=               row[lang_code],
            #TODO make these below more dynamic in case tx_columns are changed
            transcription_id=   row[CsvManager.get_tx_id_column(lang_code=lang_code, voice=voice)],
            status=             tx_status,
            resp_body=          row[CsvManager.get_tx_details_columns(lang_code=lang_code, voice=voice)],
            )

    def dump_tx_status_to_df(transaction: TranscriptionTx, df: pd.DataFrame, item_id_column: str) -> pd.DataFrame:
        """
        Updates the given DataFrame with the status of a transcription transaction.

        Args:
            transaction (TranscriptionTx): The transcription transaction object.
            df (pd.DataFrame): The DataFrame to update.
            item_id_column (str): The name of the column in the DataFrame that contains the item IDs.

        Returns:
            pd.DataFrame: The updated DataFrame.
        """
        df.loc[
            df[item_id_column] == transaction.item_id,
            CsvManager.get_tx_columns(lang_code=transaction.lang_code, voice=transaction.voice)
        ] = transaction.transcription_id, transaction.status, transaction.resp_body #TODO make this dynamic in case tx_columns are changed
        return df

    def format_tx_column(lang_code, voice, column_name):
        return f'tts_{lang_code}_{voice}_{column_name}'

    def get_tx_id_column(lang_code, voice):
        return CsvManager.format_tx_column(lang_code, voice, 'tx_id')

    def get_tx_status_column(lang_code, voice):
        return CsvManager.format_tx_column(lang_code, voice, 'status')

    def get_tx_details_columns(lang_code, voice):
        return CsvManager.format_tx_column(lang_code, voice, 'details')

    def get_tx_columns(lang_code, voice) -> List[str]:
        return [
            CsvManager.get_tx_id_column(lang_code, voice),
            CsvManager.get_tx_status_column(lang_code, voice),
            CsvManager.get_tx_details_columns(lang_code, voice),
            ]

################################################
# DRIVER CODE
################################################

"""
def download_audio_files(df, destination_folder=None, overwrite=False, save_task_audio=None):
    for _, row in df.iterrows():
        task = row['tasks']  # Column used to specify the task

        # Skip tasks that do not match the specified task
        if save_task_audio is not None and task != save_task_audio:
            continue

        uri = row['status']
        item_id = row['item_id']
        lang_code = row['lang_code']
        voice = row['voice']

        # Create a subdirectory based on the 'tasks' column
        if destination_folder is None:
            destination_folder = os.path.join(f"{lang_code}_{voice}", task)
        else:
            destination_folder = os.path.join(destination_folder, task)

        filename = os.path.basename(uri)
        local_file_path = os.path.join(destination_folder, filename)

        if not overwrite and os.path.exists(local_file_path):
            continue

        response = requests.get(uri, stream=True)
        if response.status_code == 200:
            os.makedirs(destination_folder, exist_ok=True)
            with open(local_file_path, 'wb') as f:
                f.write(response.content)
"""

def process_transactions(transactions: List[TranscriptionTx], status_data_store: StatusDataStore, user_id, auth_token, rate_limit_per_minute, audio_dir, save_task_audio=None):
    def process(transaction):
        if transaction.status not in ['pending', 'error']:
            logging.debug(f"process: transaction={transaction.item_id}: skip convert, status={transaction.status}")
        else:
            transaction = convert_tts(transaction, user_id, auth_token)
            status_data_store.persist_tx_status(transaction)

        if transaction.status != 'in_progress':
            logging.debug(f"process: transaction={transaction.item_id}: skip check_status, status={transaction.status}")
        else:
            backoff = 1  # this is arbitrary
            time.sleep(backoff)
            while transaction.status == 'in_progress':
                transaction = check_status(transaction, user_id, auth_token)
                status_data_store.persist_tx_status(transaction)
                if backoff < 30:  # this is arbitrary
                    backoff *= 2
                time.sleep(backoff)

        # TODO make detecting need for download more robust
        if not transaction.status.startswith('https://'):
            logging.debug(f"process: transaction={transaction.item_id}: skip download, status={transaction.status}")
        else:
            # We've gotten a URL so our translation is ready to download
            # Repo path: core-task-assets\math\de\shared>
            ##? Calc task_dir from label or from item_id??
            audio_file_path = \
                os.path.join(audio_base_dir, transaction.labels,
                              transaction.lang_code, "shared")
            # Assuming 'task' is derived from item_id for directory structure
            # task_subdir = transaction.item_id.split('_')[0]
            transaction = download_audio_files(transaction, audio_file_path)
            status_data_store.persist_tx_status(transaction)
        time.sleep(rate_limit_interval)  # TODO: implement real rate limiting

    # Once we have the URL for the translation, download it to a file system    
    
    def download_audio_files(transaction, audio_dir, save_task_dir = None):
        if not os.path.exists(audio_dir):
            os.mkdir(audio_dir)
            #errorMsg = f"download_audio_files: audio_dir does not exist={audio_dir}"
            #logging.error(errorMsg)
            #raise FileNotFoundError(errorMsg)

        response = requests.get(transaction.status, stream=True)
        if response.status_code == 200:
            # this is kind of bogus given desired path
            audio_file_full_dir = os.path.join(audio_dir,transaction)
            if not os.path.exists(audio_file_full_dir):
                os.mkdir(audio_file_full_dir)
            audio_file_path = os.path.join(audio_dir,transaction.item_id+".mp3")

            if os.path.exists(audio_file_path):
                logging.warning(f"download_audio_files: file already exists={audio_file_path}")
            else:
                with open(audio_file_path, 'wb') as f:
                    f.write(response.content)
            return replace(transaction, status=audio_file_path)

    rate_limit_interval = 60 / rate_limit_per_minute
    with ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(process, transactions)
    
def setup_csvmanager_status_store(
        input_file_path,
        output_file_path,
        user_id,
        overwrite_input_file: bool,
        item_id_column,
        lang_code,
        voice,
        ) -> StatusDataStore:

    # create our CsvManager instance
    csv_status_store = CsvManager(input_file_path, item_id_column)

    # setup the destination for persisting the status of our tts transactions 
    if overwrite_input_file is True:
        if output_file_path is not None:
            if output_file_path is not input_file_path:
                errorMsg = f"Conflicting parameters: output file cannot be used when overwriting input file"
                logging.error(errorMsg)
                raise Exception(errorMsg)
            else:
                logging.warning(f"no need to specify output file path when opting to overwrite input file")
        logging.info(f"!!! ATTENTION !!! input csv file will be overwritten")
        # we do not call set_output_file() but opt to overwrite the csv input file instead
        csv_status_store.set_overwrites_csv_input_file()
    else:
        if output_file_path is None: # we need to create an output csv file since none was provided
            timestamp = datetime.now().strftime('%Y%m%d.%H.%M.%S')
            dir_path = f'./snapshots_{user_id}'
            os.makedirs(dir_path, exist_ok=True)
            output_filepath = os.path.join(dir_path,"tts_" + timestamp + "_" +user_id + ".csv")
            logging.info(f"no output file path specified: will create output file as {output_filepath}")
        csv_status_store.set_csv_output_file(output_filepath)

    # select a particular target locale and voice for the transactions and ensure the columns exist in the output csv
    csv_status_store.set_target_locale_and_voice(lang_code, voice)

    return csv_status_store

def main(
        input_file_path: str,
        lang_code: str,
        voice: str,
        user_id: str = None,
        api_key: str = None,
        overwrite_input_file_str: str = 'False',
        output_file_path: str = None,
        item_id_column: str = 'item_id',
        rate_limit_per_minute_str: str = '40',
        audio_dir: str = None,
        save_task_audio: str = None,  # saving audio only for specified task (e.g. 'theory-of-mind')
    ):
    """
    The main function to process the transcription jobs.

    Args:
        input_file_path (str): The path of the input CSV file where details of text and of past tts transactions are extracted.
        lang_code (str): A locale code, e.g.: 'es-CO' and the name for the column to select for tts transcription
        voice (str): The name of the play.ht voice to use, e.g.: 'es-CO-SalomeNeural'
        user_id (str, optional): The user ID for authentication. If not provided, it will be read from the environment variable 'PLAY_DOT_HT_USER_ID'.
        api_key (str, optional): The api key authenticating our API calls. If not provided, it will be read from the environment variable 'PLAY_DOT_HT_API_KEY'.
        overwrite_input_file_str (str, optional): A boolean string to indicate whether to overwrite the input file. Defaults to 'False'.
        output_file_path (str, optional): The path for the output CSV files to create and where to store the state of our transactions. Defaults to './snapshots_{user_id}/tts_{timestamp}_{user_id}.csv'
        item_id_column (str, optional): column name in the input file for stable and unique item ID. Defaults to 'item_id'.
        rate_limit_per_minute (str, optional): The rate limit expected for the endpoint. Defaults to 50.
        audio_dir (str, optional): The directory to store the audio files. Defaults to "audio_files/{lang_code}/".
    """

    if user_id is None:
        user_id = os.environ['PLAY_DOT_HT_USER_ID']
        if user_id is None:
            raise ValueError("user_id cannot be None")
    if api_key is None:
        api_key = os.environ['PLAY_DOT_HT_API_KEY']
        if api_key is None:
            raise ValueError("auth_token cannot be None")
    overwrite_input_file = overwrite_input_file_str.lower() == 'true'
    rate_limit_per_minute = int(rate_limit_per_minute_str)

    # init status data store
    status_data_store = setup_csvmanager_status_store(
        input_file_path=input_file_path,
        output_file_path=output_file_path,
        user_id=user_id,
        item_id_column=item_id_column,
        overwrite_input_file=overwrite_input_file,
        lang_code=lang_code,
        voice=voice,
    )

    # parse transaction objects
    transactions = status_data_store.extract_transactions()
    logging.info(f"main: extracted {len(transactions)} transactions, sample={transactions[:3]}")

    # create destination folder for audio files
    # Audio Directory needs to be task/lang_code/shared
    # So we can't fix it in place now
    # might need to change on each item!
    if audio_dir is None:
        # need to add task name
        audio_dir = os.path.join("audio_files","lang_code","shared")
    create_directory(audio_dir)

    process_transactions(
        transactions=transactions,
        status_data_store=status_data_store,
        user_id=user_id,
        auth_token=api_key,
        rate_limit_per_minute=rate_limit_per_minute,
        audio_dir=audio_dir,
        save_task_audio=save_task_audio,  # Pass the new argument
    )

if __name__ == "__main__":
    main(*sys.argv[1:])

# save audio for theory-of-mind:
# python playDotHt_v3.py item-bank-translations.csv 'en' 'en-US-AriaNeural' --save_task_audio='theory-of-mind'
# save audio for all tasks (in task-specific subdirectories):
# python playDotHt_v3.py item-bank-translations.csv 'en' 'en-US-AriaNeural'