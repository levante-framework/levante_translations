# Utility to list voices
import requests
import os
from playsound import playsound 
from pyht import Client
import time

# Constants for API, in this case for Play.Ht, maybe
API_URL = "https://api.play.ht/api/v1/convert"
STATUS_URL = "https://api.play.ht/api/v1/articleStatus"

headers = {
    "Authorization": os.environ["PLAY_DOT_HT_API_KEY"],
    "X-User-ID": os.environ["PLAY_DOT_HT_USER_ID"],
    'Accept': 'application/json',
    "Content-Type": "application/json"
}

def list_voices(lang_code):
    # Set up the API request
    url = "https://play.ht/api/v1/getVoices"

    # Make the API request
    response = requests.get(url, headers=headers)

    # Check if the request was successful
    if response.status_code == 200:
        response_data = response.json()
        voices = response_data.get("voices", [])
    
         # Specify the language you want to filter by
        if lang_code == 'en':
            target_language = "English (US)"  # Change this to your desired language
        elif lang_code == 'de':
            target_language = "German"  # Change this to your desired language
        elif lang_code == 'es-CO':
            target_language = "Spanish (Colombia)"  # Change this to your desired language
        else:
            return("Error")

        # Filter voices by the specified language
        filtered_voices = [voice for voice in voices if voice.get('language') == target_language]

        # debug language
        #filtered_voices = [voice for voice in voices]

        # Do we want to return the entire dictionary? 
        return(filtered_voices)

# Print voice details for debugging
#        for voice in filtered_voices:

#            print(f"Name: {voice.get('name', 'N/A')}")
#        print(f"ID: {voice.get('value', 'N/A')}")
#            print(f"Language: {voice.get('language', 'N/A')}")
#        print(f"Gender: {voice.get('gender', 'N/A')}")
#        print(f"Age: {voice.get('age', 'N/A')}")
#        print(f"Sample: {voice.get('sample', 'N/A')}")
#        print("---")

    else:
        print(f"Error: {response.status_code} - {response.text}")

# Borrowed from playHt_tts!!
# could return file name or error, etc.
def get_audio(text, voice):

    client = Client(
        api_key = os.environ["PLAY_DOT_HT_API_KEY"],
        user_id = os.environ["PLAY_DOT_HT_USER_ID"],
    )

    retrySeconds = .5
    errorCount = 0

    data = {
        # content needs to be an array, even if we only do one at a time
        "content" : text,
        "voice": voice,
        "title": "Comparison Audio", # not sure where this matters?
        "trimSilence": True
    }

    ## Use a While loop so we can retry odd failure cases
    while True and errorCount < 5:
        response = requests.post(API_URL, headers=headers, json=data) 

        # In some cases we get an odd error that appears to suggest the
        # transcription is still in progress, but it never finishes
        # to handle that case, we abandon that transaction & start a new one
        restartRequest = False
        # 201 means that we got a response of some kind
        if response.status_code == 201:
            # results are packed into a json object
            result = response.json()
        else:
            # sometimes a retry works after no response
            errorCount += 1
            continue

        # status is a little awkward to parse. Some errors aren't exactly errors
        json_status = response.json()

        if "transcriptionId" in json_status:
            # This means that we've successfully started the transcription
            transcription_id = json_status["transcriptionId"]
        
            # Poll the status until completion or we get 5 error returns
            while True and errorCount < 5 and restartRequest == False:
                downloadURL = None # clear each time
                status_params = {"transcriptionId": transcription_id}
                status_response = requests.get(STATUS_URL, params=status_params, headers=headers)
                status_data = status_response.json()

                # Some errors are "fatal", some just mean a retry is needed
                if 'error' in status_data:
                    if status_data['error'] == True: # and \
                        #status_data['message'] != 'Transcription still in progress':
                        restartRequest = True
                        errorCount += 1
                        continue # we want to start the loop over

                # Our transcription is successful                        
                if status_data["converted"] == True:
                    #print(f"Audio URL: {status_data['audioUrl']}")
                    # set the download URL for retrieval or get it right here?
                    downloadURL = status_data['audioUrl']

                    # At this point we should have an "audioURL" that we can retrieve
                    # and then write out to the appropriate directory
                    audioData = requests.get(downloadURL)

                    # open file for writing
                    # Download the MP3 file
                    if audioData.status_code == 200:
                        restartRequest = False
                        errorCount = 0

                        output_file = 'voice_comparison.mp3'
                        with open(output_file, "wb") as file:
                            file.write(audioData.content)
                            file.close
                            return 'Success'    
                else:
                    # print(f"Conversion in progress. Status: {status_data['converted']}")
                    # currently most tasks complet in about 1 second, so .5 seconds
                    # seems like a good tradeoff between "over-polling" and "over-waiting"
                    time.sleep(retrySeconds)  # Wait before checking again
            else:
                continue
    else:
        # we've tried several times
        return 'Error'
