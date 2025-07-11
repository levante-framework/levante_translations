from math import isnan
import os
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import customtkinter as ctk
from CTkToolTip import *
import pandas as pd
from utilities import utilities as u
from utilities import config as conf

from playsound import playsound
from typing import Final

# Service specific code
# Moving PlayHt from v1 to v2
from PlayHt import playHt_utilities
from PlayHt import voice_mapping
from ELabs import elevenlabs_utilities

class App(ctk.CTk):

    def __init__(self):
        super().__init__()

        # Get list of languages and voices
        self.language_dict = conf.get_languages()

        ## Uses our default file name
        self.ourData = pd.read_csv(conf.item_bank_translations)
        self.ourData = self.ourData.rename(columns={'identifier': 'item_id'})

        # Updated for simplified language codes
        self.ourData = self.ourData.rename(columns={'text': 'en'})
        # Keep the original column names as they are now (en, de, es, fr, nl)


        self.title("Levante Translation and Audio Generation Dashboard")
        self.geometry("1000x600")

        # Create and place the full frame
        self.fullFrame = ctk.CTkFrame(self)
        self.fullFrame.grid(row=0, column=0, sticky="nsew")

        # Configure the grid layout for the main window
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Configure the grid layout for fullFrame
        self.fullFrame.grid_columnconfigure((0, 1, 2), weight=1)
        self.fullFrame.grid_rowconfigure(0, weight=1)
        self.fullFrame.rowconfigure(0, weight=1)

        # Top frame with labels
        self.top_frame = ctk.CTkFrame(self.fullFrame, height=400)
        self.top_frame.grid(row=0, column=0, rowspan=4, columnspan=4, sticky="nsew")

        number_of_rows = 4 # for now
        for i in range(number_of_rows):
            self.top_frame.grid_rowconfigure(i, weight=1)

        # Configure the grid layout for top_frame
        self.top_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Show statistics per language in top frame
        self.display_stats()

        ### -- Now the lower frame -- Tabbed frame for each language
        # Row assignments
        SEARCH_ROW: Final[int] = 2
        VOICE_ROW: Final[int] = 1
        SSML_ROW: Final[int] = 0
        self.TABLE_ROW: Final[int] = 3
        self.STATUS_ROW: Final[int] = 4

        self.language_frame = ctk.CTkFrame(self)
        self.language_frame.grid(row=1, column=0, padx=2, pady=2, sticky="nsew")

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.language_frame.grid_columnconfigure(0, weight=1)
        self.language_frame.grid_rowconfigure(self.TABLE_ROW, weight=1)

        # search field for item names
        self.create_search_frame(self.language_frame, SEARCH_ROW)

        # fields for comparing voices
        self.create_voice_frame(self.language_frame, VOICE_ROW)

        self.create_ssml_frame(self.language_frame, SSML_ROW)

        self.tabview = self.create_tabview()

        self.create_statusbar()

        #Add basic instructions:
        u.show_intro_messagebox(self)
    
    # when tab is selected, change values for voices
    # should probably cache them at some point
    def on_tab_change(self):
        # Always clear cache when switching tabs
        self.clear_voice_cache()
        self.after(100, self.update_comboboxes)

    def on_ssml_play(self):
        # We want to play the current text in ssml_input through
        # the current (language specific) voice
        play_text_html = self.ssml_input.get("0.0", "end")
        play_text_ssml = u.html_to_ssml(play_text_html)

        # get the correct voice
        voice = ''
        try:
            if self.tabview.winfo_exists():
                active_tab = self.tabview.get()
            else:
                return
            
            voice = conf.get_default_voice(active_tab)
            service = conf.get_service(active_tab)
        except Exception as e:
            print(f"Error getting service/voice configuration: {e}")
            # assume we will show english when created
            service = 'ElevenLabs'  # Changed from PlayHt to ElevenLabs for English default
            voice = 'Alexandra - Conversational and Real'
            active_tab = 'English'

        # Now transcribe text & play using selected voice
        try:
            u.play_audio_from_text(service, active_tab, voice, play_text_ssml)
        except Exception as e:
            print(f"Error playing audio: {e}")
            self.set_status(f"Unable to Play: {str(e)}")

    def create_tabview(self):
        tabview = ctk.CTkTabview(self.language_frame, 
                                      command=self.on_tab_change)
        tabview.grid(row=self.TABLE_ROW, column=0, padx=2, pady=2, sticky="nsew")

        language_dict = conf.get_languages()
        self.tabArray = {}
        self.frameArray = {}
        self.treeArray = {}

        for language_name in language_dict.keys():

            newTab = tabview.add(language_name)
            self.tabArray[language_name] = newTab

            newFrame = ctk.CTkFrame(newTab)
            newFrame.pack(side="top", expand=True, fill="both", padx=2, pady=2)
            self.frameArray[language_name] = newFrame

            # Need to set lang code
            specific_language = language_dict.get(language_name)
            language_code = specific_language.get('lang_code')
            newTree = self.create_table(newFrame, language_code)
            self.treeArray[language_name] = newTree

        return tabview

    def display_stats(self):
        # Need to refactor into a language-specific function

        # get error and 'no task' stats
        statsData = u.get_stats()

        # Each language gets a column, so this probably won't
        # scale well with languages. Might become legacy
        englishStats = statsData.loc[statsData['Language'] == 'English']
        englishErrors = englishStats['Errors'][0]
        englishNoTask = englishStats['No Task'][0]
        self.englishVoice = englishStats['Voice'][0]

        spanishStats = statsData.loc[statsData['Language'] == 'Spanish']
        spanishErrors = spanishStats['Errors'][1]
        spanishNoTask = spanishStats['No Task'][1]
        self.spanishVoice = spanishStats['Voice'][1]

        germanStats = statsData.loc[statsData['Language'] == 'German']
        germanErrors = germanStats['Errors'][2]
        germanNoTask = germanStats['No Task'][2]
        self.germanVoice = germanStats['Voice'][2]

        # Left column for Label
        headerOne = ctk.CTkLabel(self.top_frame, text = "Current")
        headerOne.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        headerTwo = ctk.CTkLabel(self.top_frame, text = "Audio Stats:")
        headerTwo.grid(row=2, column=0, padx=5, pady=5, sticky="nsew")

        # First row
        generated_english = u.count_audio_files('en')
        self.generatedEnglish = ctk.CTkLabel(self.top_frame, text=f'English Audio: {generated_english}')
        self.generatedEnglish.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")

        generated_spanish = u.count_audio_files('es')
        self.generatedSpanish = ctk.CTkLabel(self.top_frame, text=f'Spanish Audio: {generated_spanish}')
        self.generatedSpanish.grid(row=0, column=2, padx=5, pady=5, sticky="nsew")

        generated_german = u.count_audio_files('de')
        self.generatedGerman = ctk.CTkLabel(self.top_frame, text=f'German Audio: {generated_german}')
        self.generatedGerman.grid(row=0, column=3, padx=5, pady=5, sticky="nsew")

        # Second row
        self.errorsEnglish = ctk.CTkLabel(self.top_frame, text=f'English Errors: {englishErrors}')
        self.errorsEnglish.grid(row=1, column=1, padx=5, pady=5, sticky="nsew")

        self.errorsSpanish = ctk.CTkLabel(self.top_frame, text=f'Spanish Errors: {spanishErrors}')
        self.errorsSpanish.grid(row=1, column=2, padx=5, pady=5, sticky="nsew")

        self.errorsGerman = ctk.CTkLabel(self.top_frame, text=f'German Errors: {germanErrors}')
        self.errorsGerman.grid(row=1, column=3, padx=5, pady=5, sticky="nsew")

        # Third row
        self.notaskEnglish = ctk.CTkLabel(self.top_frame, text=f'English No Task: {englishNoTask}')
        self.notaskEnglish.grid(row=2, column=1, padx=5, pady=5, sticky="nsew")

        self.notaskSpanish = ctk.CTkLabel(self.top_frame, text=f'Spanish No Task: {spanishNoTask}')
        self.notaskSpanish.grid(row=2, column=2, padx=5, pady=5, sticky="nsew")

        self.notaskGerman = ctk.CTkLabel(self.top_frame, text=f'German No Task: {germanNoTask}')
        self.notaskGerman.grid(row=2, column=3, padx=5, pady=5, sticky="nsew")           

        ## Voice row here
        self.voiceEnglish = ctk.CTkLabel(self.top_frame, text=f'Voice: {self.englishVoice}')
        self.voiceEnglish.grid(row=3, column=1, padx=5, pady=5, sticky="nsew")

        self.voiceSpanish = ctk.CTkLabel(self.top_frame, text=f'Voice: {self.spanishVoice}')
        self.voiceSpanish.grid(row=3, column=2, padx=5, pady=5, sticky="nsew")

        self.voiceGerman = ctk.CTkLabel(self.top_frame, text=f'Voice: {self.germanVoice}')
        self.voiceGerman.grid(row=3, column=3, padx=5, pady=5, sticky="nsew")

    def create_search_frame(self, parent, row):
        search_frame = ctk.CTkFrame(parent)
        search_frame.grid(row=row, column=0, padx=2, pady=2, sticky="ew")

        # Configure the grid layout for search_frame
        search_frame.grid_columnconfigure(1, weight=1)  # Make the entry expandable

        # Add label to the search_frame
        label = ctk.CTkLabel(search_frame, text="Search for specific item to use for testing, or select one from below: ")
        label.grid(row=0, column=0, padx=(5,5), pady=2, sticky="w")

        # Create the search box and add it to search_frame
        parent.search_var = tk.StringVar()
        parent.search_entry = ctk.CTkEntry(search_frame, textvariable=parent.search_var)
        parent.search_entry.grid(row=0, column=1, padx=(5,5), pady=2, sticky="ew")

        # bind to current language / code for displaying results
        parent.search_entry.bind("<Return>", lambda event: self.search_treeview(parent))
        CTkToolTip(parent.search_entry, message="Type an item id and then <Return> to navigate to the item and play the text.")
        return search_frame  # Return the frame in case you need to reference it later

    def create_voice_frame(self, parent, row):
        voice_frame = ctk.CTkFrame(parent)
        voice_frame.grid(row=row, column=0, padx=5, pady=2, sticky="ew")

        # Configure the grid layout for the voice frame
        voice_frame.grid_columnconfigure(2, weight=1)  # Make the entry expandable

        # Add refresh button at the left
        self.refresh_voices_button = ctk.CTkButton(voice_frame, 
            text="🔄 Refresh Voices",
            command=lambda: self.update_comboboxes(force_refresh=True),
            width=120)
        self.refresh_voices_button.grid(row=0, column=0, padx=(5,5), pady=2, sticky="w")

        # Add PlayHt elements
        label = ctk.CTkLabel(voice_frame, text="Compare SSML Using PlayHt Voice: ")
        label.grid(row=0, column=1, padx=(5,5), pady=2, sticky="w")

        voice_values = self.get_voice_list('PlayHt')

        self.ht_voice_combobox = ctk.CTkComboBox(voice_frame, values=voice_values, \
            command=lambda choice: self.voice_compare_callback(choice, 'PlayHt'))
        self.ht_voice_combobox.grid(row=0, column=2, padx=(5,5), pady=2, sticky="w")
        self.ht_voice_combobox.set("Select a PlayHt Voice")

        label = ctk.CTkLabel(voice_frame, text="Compare SSML Using ElevenLabs Voice: ")
        label.grid(row=0, column=3, padx=(5,5), pady=2, sticky="w")

        voice_values = self.get_voice_list('ElevenLabs')

        self.eleven_voice_combobox = ctk.CTkComboBox(voice_frame, values=voice_values, \
            command=lambda choice: self.voice_compare_callback(choice, 'ElevenLabs'))
        self.eleven_voice_combobox.grid(row=0, column=4, padx=(5,5), pady=2, sticky="w")
        self.eleven_voice_combobox.set("Select an ElevenLabs Voice")

        return voice_frame  # Return the frame in case you need to reference it later

    def create_ssml_frame(self, parent, row):
        ssml_frame = ctk.CTkFrame(parent)
        ssml_frame.grid(row=row, column=0, padx=5, pady=2, sticky="ew")

        # Configure the grid layout for the ssml frame
        ssml_frame.grid_columnconfigure(1, weight=1)  # Make the entry expandable

        # Add PlayHt elements
        label = ctk.CTkLabel(ssml_frame, text="SSML Editor: ")
        label.grid(row=0, column=0, padx=(5,5), pady=2, sticky="w")

        self.ssml_play = ctk.CTkButton(ssml_frame,  
            text="Play in default voice:",
            command=lambda: self.on_ssml_play())
        self.ssml_play.grid(row=1, column=0, padx=(5,5), pady=2, sticky="w")

        self.ssml_input = ctk.CTkTextbox(ssml_frame, width=400, height=50)
        self.ssml_input.insert("0.0", 'Text goes <break time="2.0s" /> here...')
        self.ssml_input.grid(row=0, column=1, rowspan=2, padx=(5,5), pady=2, sticky="nsew")

        self.show_ssml_button = ctk.CTkButton(ssml_frame,
            text="Show SSML Tips", command=lambda: u.show_ssml_tips(self))
        self.show_ssml_button.grid(row=0, column=2, padx=(5,5), pady=2, sticky="w")

        return ssml_frame

    def create_table(self, parent, lang_code):

        def on_tree_select(event):
            # Get the ID of the selected item
            selected_items = event.widget.selection()
    
            if selected_items:  # Check if any item is selected
                item = selected_items[0]  # Get the first selected item
        
             # Get the column ID (if needed)
                column = event.widget.identify_column(event.widget.winfo_pointerx() - event.widget.winfo_rootx())
        
                # Get the values of the selected item
                item_values = event.widget.item(item, "values")
        
                # Get the text of the selected item
                item_text = event.widget.item(item, "text")
        

                # should go by column name...

                translation_text = item_values[3]

                # clear existing text and insert our new text
                self.ssml_input.delete("0.0", "end")
                self.ssml_input.insert("0.0", translation_text)

                # This is kind of gross. Maybe we should fix tools?
                audio_file = item_values[4]
                try:
                    self.set_status(os.path.abspath(audio_file))
                    playsound(os.path.abspath(audio_file))
                except:
                    messagebox.showinfo("Can't find or play audio file.")

        # Create a treeview widget for the table
        columns = ("Item", "Task", "English", "Translated", "Audio")
        style = ttk.Style()
        style.configure("Treeview.Heading",
                font=("Arial", 14, "bold"),  # Font family, size, and weight
                foreground="blue",           # Optional: change text color
                background="lightgray")      # Optional: 
        style.configure("Treeview", rowheight=80, \
                        font=('TkDefaultFont', 16))

        ourTree = ttk.Treeview(parent, columns=columns, show="headings", style='Treeview')
        ourTree.bind("<<TreeviewSelect>>", on_tree_select)

        vsb = ctk.CTkScrollbar(parent, orientation="vertical", command=ourTree.yview)
        hsb = ctk.CTkScrollbar(parent, orientation="horizontal", command=ourTree.xview)

        ourTree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")

        # Define column headings
        for col in columns:
            ourTree.heading(col, text=col)
            if col == 'Item' or col == 'Task' or col == 'Audio':
                ourTree.column(col, width=15)
            else:
                ourTree.column(col, width=200)

        # Insert DataFrame rows into the Treeview
        # First row: {self.ourData.iloc[0].to_dict()}
        for index, row in self.ourData.iterrows():
            base = "audio_files"

            if isinstance(row['labels'], str) and row['labels'].strip():
                audio_file_name = u.audio_file_path(row['labels'], row['item_id'], base, lang_code)
                if not isinstance(row[lang_code], str) and isnan(row[lang_code]):
                    row[lang_code] = ''; # Don't want a Nan value
                values = [row['item_id'], row['labels'], row['en'], row[lang_code], audio_file_name]

                # Hack for column numbers
                values[2] = u.wrap_text(values[2])
                values[3] = u.wrap_text(values[3])

                ourTree.insert("", "end", values=values)

                ourTree.pack(expand=True, fill="both")
        return ourTree

    def search_treeview(self, parentFrame, *args):

        query = parentFrame.search_var.get()

        ## This shouldn't be needed if we can sort out the ParentFrame
        active_tab = self.tabview.get()
        tree = self.treeArray[active_tab]

        for item_index in tree.get_children():
            # column 0 is the task name
            if query in tree.item(item_index, 'values')[0]:
                tree.focus_set()
                tree.focus(item_index)
                tree.selection_set(item_index)
                tree.see(item_index)
                # add a break to only pick one
                break
            else:
                tree.selection_remove(item_index)

    def clear_voice_cache(self):
        """Clear all cached voice lists to force refresh"""
        # Remove all cached voice list attributes
        attrs_to_remove = []
        for attr_name in dir(self):
            if attr_name.startswith('ht_') and attr_name.endswith('_voice_list'):
                attrs_to_remove.append(attr_name)
            elif attr_name.startswith('eleven_') and (attr_name.endswith('_voice_list') or attr_name.endswith('_voice_dict')):
                attrs_to_remove.append(attr_name)
        
        for attr_name in attrs_to_remove:
            if hasattr(self, attr_name):
                delattr(self, attr_name)
        
        print("Voice cache cleared - voice lists will be regenerated")

    def update_comboboxes(self, force_refresh=False):
        # Clear cache if force_refresh is True or if switching tabs
        if force_refresh:
            self.clear_voice_cache()
        
        # get_language_list used current tab to derive lang_code
        ht_voice_list = self.get_voice_list('PlayHt')
        eleven_voice_list = self.get_voice_list('ElevenLabs')

        # update combo boxes for both services
        self.ht_voice_combobox.configure(values=ht_voice_list)
        self.ht_voice_combobox.set(ht_voice_list[0] if ht_voice_list else "")

        self.eleven_voice_combobox.configure(values=eleven_voice_list)
        self.eleven_voice_combobox.set(eleven_voice_list[0] if eleven_voice_list else "")

    def get_voice_list(self, service):

        # to be language extensible:
        # List of lists or dict of lists

        # we get called before there is a tab view
        # so in that case we default to English
        # (a little lame:))
        try:
            if self.tabview.winfo_exists():
                active_tab = self.tabview.get()

            # Get language code from config based on active tab
            specific_language = self.language_dict.get(active_tab)
            if not specific_language:
                print("NO LANGUAGE")
                exit()
                
            lang_code = specific_language.get('lang_code')
            
            # Check for cached voice lists
            if service == 'PlayHt':
                voice_list_attr = f'ht_{lang_code.replace("-","_")}_voice_list'
                if hasattr(self, voice_list_attr) and getattr(self, voice_list_attr):
                    return getattr(self, voice_list_attr)
            elif service == 'ElevenLabs':
                voice_list_attr = f'eleven_{lang_code.replace("-","_")}_voice_list'
                if hasattr(self, voice_list_attr) and getattr(self, voice_list_attr):
                    return getattr(self, voice_list_attr)
        except:
            # assume we will show english when created
            lang_code = 'en'
            # HACK
            service = "ElevenLabs"
            
        # voice list not found
        if service == 'PlayHt':
            # For comparison evaluation, show curated PlayHT voices for each language
            try:
                # Get all voices from the voice mapping system
                all_voices = voice_mapping.list_voices()
                
                # Get ElevenLabs voices to exclude them from PlayHT list
                try:
                    elevenlabs_voices = set()
                    # Get ElevenLabs voices for all potential language codes
                    for test_lang in ['en', 'es', 'de', 'fr', 'nl']:
                        try:
                            el_voices = elevenlabs_utilities.list_voices(test_lang)
                            elevenlabs_voices.update(el_voices.keys())
                        except:
                            continue
                except Exception as e:
                    print(f"Warning: Could not get ElevenLabs voices for filtering: {e}")
                    elevenlabs_voices = set()
                
                # Define curated voice selections for comparison evaluation (6-10 voices per service)
                curated_voices = {
                    'en': [
                        'English (US)_Susan (Advertising)',
                        'English (US)_Delilah', 
                        'English (CA)_Charlotte (Narrative)',
                        'English (CA)_Olivia (Advertising)',
                        'English (IE)_Madison',
                        'English (IN)_Navya',
                        'English (GB)_Sarah'
                    ],
                    'es-CO': [
                        'Spanish_Violeta Narrative',
                        'Spanish_Xavi Narrative', 
                        'Spanish_Violeta Conversational',
                        'Spanish_Patricia Narrative',
                        'Spanish_Xavi Conversational',
                        'Spanish_Patricia Conversational'
                    ],
                    'de': [
                        'German_Anke Narrative',
                        'German_Bernd Narrative',
                        'German_Anke Conversational',
                        'German_Bernd Conversational'
                    ],
                    'fr-CA': [
                        'French_Ange Narrative',
                        'French_Claude Narrative',
                        'French_Ange Conversational', 
                        'French_Claude Conversational'
                    ],
                    'nl': [
                        'Dutch_Bram Narrative',
                        'Dutch_Lotte Narrative',
                        'Dutch_Bram Conversational',
                        'Dutch_Lotte Conversational'
                    ]
                }
                
                # Get curated voices for this language, or fall back to filtered search
                if lang_code in curated_voices:
                    voices = curated_voices[lang_code]
                    # Verify these voices exist in the actual voice list
                    available_voice_names = [voice['name'] for voice in all_voices]
                    voices = [v for v in voices if v in available_voice_names]
                else:
                    # Fall back to language filtering
                    language_filters = {
                        'en': ['English', 'english'],
                        'es-CO': ['Spanish', 'spanish'],
                        'de': ['German', 'german'],
                        'fr-CA': ['French', 'french'],
                        'nl': ['Dutch', 'dutch', 'Netherlands']
                    }
                    
                    voices = []
                    if lang_code in language_filters:
                        filters = language_filters[lang_code]
                        for voice in all_voices:
                            voice_name = voice['name']
                            # Skip if this is an ElevenLabs voice
                            if voice_name in elevenlabs_voices:
                                continue
                            # Check if any of the language filters match the voice name
                            if any(lang_filter in voice_name for lang_filter in filters):
                                voices.append(voice_name)
                    
                    # Limit to first 10 voices for non-curated languages
                    voices = voices[:10]
                        
            except Exception as e:
                print(f"Error getting PlayHT voices: {e}")
                voices = ["Spanish_Violeta Narrative", "German_Anke Narrative", "French_Ange Narrative"]
                
            # Create attribute name by replacing hyphens with underscores
            voice_list_attr = f'ht_{lang_code.replace("-","_")}_voice_list'
            # Set the attribute dynamically
            setattr(self, voice_list_attr, voices)
            return voices

        elif service == 'ElevenLabs':
            # For comparison evaluation, show curated ElevenLabs voices for each language
            try:
                # Define curated ElevenLabs voices for comparison evaluation (6-10 voices per service)
                curated_elevenlabs_voices = {
                    'en': {
                        'voices': ['Yasmine', 'Alexandra - Conversational and Real', 'Aunt Annie - calm and professional', 'Claudia - Credible, Competent & Authentic', 'Zuri - New Yorker', 'Nia Davis- Black Female', 'Juniper', 'Jessica Anne Bogart - Conversations'],
                        'gender_filter': 'Female'  # Only female voices for English
                    },
                    'es-CO': {
                        'voices': ['Yasmine', 'Alexandra - Conversational and Real', 'Aunt Annie - calm and professional', 'Claudia - Credible, Competent & Authentic', 'Zuri - New Yorker', 'Nia Davis- Black Female'],  # Multi-lingual voices
                        'gender_filter': None
                    },
                    'de': {
                        'voices': ['Yasmine', 'Alexandra - Conversational and Real', 'Aunt Annie - calm and professional', 'Claudia - Credible, Competent & Authentic', 'Zuri - New Yorker', 'Nia Davis- Black Female'],  # Multi-lingual voices
                        'gender_filter': None
                    },
                    'fr-CA': {
                        'voices': ['Yasmine', 'Alexandra - Conversational and Real', 'Aunt Annie - calm and professional', 'Claudia - Credible, Competent & Authentic', 'Zuri - New Yorker', 'Nia Davis- Black Female'],  # Multi-lingual voices
                        'gender_filter': None
                    },
                    'nl': {
                        'voices': ['Yasmine', 'Alexandra - Conversational and Real', 'Aunt Annie - calm and professional', 'Claudia - Credible, Competent & Authentic', 'Zuri - New Yorker', 'Nia Davis- Black Female'],  # Multi-lingual voices
                        'gender_filter': None
                    }
                }
                
                # Get curated voices for this language, or fall back to filtered search
                if lang_code in curated_elevenlabs_voices:
                    config = curated_elevenlabs_voices[lang_code]
                    gender_filter = config['gender_filter']
                    
                    # For non-English languages, try to get voices from English since they're multilingual
                    if lang_code != 'en':
                        # Try to get multilingual voices from English
                        try:
                            voice_dict = elevenlabs_utilities.list_voices('en', gender_filter)
                            all_available_voices = list(voice_dict.keys())
                        except:
                            # Fall back to the original language code
                            voice_dict = elevenlabs_utilities.list_voices(lang_code, gender_filter)
                            all_available_voices = list(voice_dict.keys())
                    else:
                        # For English, use the original approach
                        voice_dict = elevenlabs_utilities.list_voices(lang_code, gender_filter)
                        all_available_voices = list(voice_dict.keys())
                    
                    # Filter to only include curated voices that are actually available
                    voices = [v for v in config['voices'] if v in all_available_voices]
                    
                    # If no curated voices are available, fall back to all available voices
                    if not voices:
                        voices = all_available_voices
                else:
                    # Fall back to all available voices for this language
                    voice_dict = elevenlabs_utilities.list_voices(lang_code)
                    voices = list(voice_dict.keys())
                    
            except Exception as e:
                print(f"Error getting ElevenLabs voices: {e}")
                # Fall back to default behavior
                gender_filter = 'Female' if lang_code == 'en' else None
                voice_dict = elevenlabs_utilities.list_voices(lang_code, gender_filter)
                voices = list(voice_dict.keys())

            # Create attribute names by replacing hyphens with underscores
            voice_dict_attr = f'eleven_{lang_code.replace("-","_")}_voice_dict'
            voice_list_attr = f'eleven_{lang_code.replace("-","_")}_voice_list'

            # Set the attributes dynamically
            setattr(self, voice_dict_attr, voice_dict)
            setattr(self, voice_list_attr, voices)

            return voices
            
    def voice_compare_callback(self, chosen_voice, service):   

        # trees don't seem to have named columns?
        TRANSLATION_COLUMN = 3

        # We want to find the selected item (if any) and render
        # it with the selected voice, and the current language
        language = self.tabview.get()
        useTree = self.treeArray[language]

        voice = chosen_voice        

        if service == 'PlayHt':
            cBox = self.ht_voice_combobox
            # For PlayHT, the voice mapping will be handled automatically
            # in the play_audio_from_text function via playHt_utilities.get_audio
        else:
            cBox = self.eleven_voice_combobox

        cBox.configure(button_color="yellow")
        cBox.update()

        # try getting text from ssml editbox
        play_text_html = self.ssml_input.get("0.0", "end")
        play_text_ssml = u.html_to_ssml(play_text_html)

        u.play_audio_from_text(service, language, voice, play_text_ssml)

        cBox.configure(button_color = "white")
        cBox.update

    def create_statusbar(self):

        # Create a read-only entry widget
        self.statusbar = ctk.CTkEntry(self, 
                                state="normal", 
                                fg_color=("white", "gray20"),
                                text_color=("black", "white"),
                                border_width=2, 
                                placeholder_text="Audio file path will go here"
                                )
        self.statusbar.grid(row=self.STATUS_ROW, column=0, padx=5, pady=2, sticky="ew")

        # Remove focus highlight
        #self.statusbar.configure(takefocus=0)


    def set_status(self, new_status):
        # Set the text
        self.statusbar.delete(0, ctk.END)
        self.statusbar.insert(0, new_status)
        # Remove focus highlight
        #self.statusbar.configure(takefocus=0)


if __name__ == "__main__":
    app = App()
    app.mainloop()

