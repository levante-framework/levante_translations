import os
from elevenlabs import play, voices
from elevenlabs.client import ElevenLabs 
from elevenlabs import Voice, VoiceSettings
import utilities.config as conf
import pprint 

# create "global" voice_dict
global voice_dict

try:
    api_key=os.getenv('elevenlabs_test')  # enter your API key here 
    client = ElevenLabs(api_key=api_key)
except:
    print("No Eleven Labs API Key")

def list_voices(lang_code, gender_filter=None):

    # ElevenLabs doesn't have es-CO
    if lang_code == 'es-CO':
        modified_language_code = 'es'
    else:
        modified_language_code = lang_code

    response = client.voices.get_all() # get our voices
#    response = client.voices.get_shared(
#        page_size=100,  # Adjust as needed, max 100
#        category='professional',  # Optional filter
#        gender='Female',    # Optional filter
#        age=None,       # Optional filter
#        accent=None,    # Optional filter
#        language=modified_language_code, 
#        search=None,    # Optional search term
#        use_cases='conversational',  # Optional filter
#        featured=None,  # Optional filter
#        sort=None,       # Optional sorting criteria
#        #model="eleven_multilingual_v2",
#    )
    voice_list = response.voices


    # Filter for voices we've added ourselves or shared voices available to us
    library_voices = [voice for voice in voice_list \
                      if (voice.category == "professional" or voice.category == "shared" or voice.category == "premade" or voice.category == "generated" or voice.category == "personal") and \
                        voice.labels.get('language') == modified_language_code]
    
    # Apply gender filter if specified
    if gender_filter:
        library_voices = [voice for voice in library_voices \
                         if voice.labels.get('gender', '').lower() == gender_filter.lower()]
    
    # Create a dictionary with voice names as keys and voice IDs as values
    voice_dict = {voice.name: voice.voice_id for voice in library_voices}
    return voice_dict

def play_audio(text, desired_voice):
    # Generate audio from text
    # The tricky part is that we need the voice_id, not the voice name!
    # we could build a dictionary?
    
    # Clean the text first
    text = text.strip()
    
    # Debug output
    print(f"ElevenLabs Debug - Text: '{text}' (length: {len(text)})")
    print(f"ElevenLabs Debug - Voice: {desired_voice}")
    
    """
    voice = Voice(
        voice_id=desired_voice,
        settings=VoiceSettings(
            stability=0.71,
            similarity_boost=0.5,
            style=0.0,
            use_speaker_boost=True
        )
    )
"""

    audio_iterator = client.generate(text=text, voice=desired_voice, \
        model="eleven_multilingual_v2")

    # Collect all audio chunks into a single bytes object
    audio_data = b"".join(audio_iterator)
    
    print(f"ElevenLabs Debug - Generated audio: {len(audio_data)} bytes")

    # Play the generated audio using our fixed play_data_object function
    from utilities.utilities import play_data_object
    play_data_object(audio_data)

    # Save the audio to a file
    #with open("output.mp3", "wb") as f:
    #    f.write(audio_data)

#voice_dict = list_voices(conf.LANGUAGE_CODES['German'])

#with open("voices.txt", "w", encoding="utf-8") as file: 
#    file.write(formatted_voices) 
#print("Voice information has been written to voices.txt") 
#print(f"Number of voices: {len(response.voices)}") 