import os
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from CTkToolTip import *
import pandas as pd
from utilities import utilities as u
from playsound import playsound
import tempfile
from typing import Final

# Service specific code
from PlayHt import playHt_utilities
from ElevenLabs import elevenlabs_utilities

class App(ctk.CTk):

    def __init__(self):
        super().__init__()

### --- Here is where the actual code start --- ###

        ## Uses our default file name
        self.ourData = pd.read_csv("item_bank_translations.csv")

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
        self.top_frame.grid(row=0, column=0, rowspan=4, columnspan=3, sticky="nsew")

        number_of_rows = 4 # for now
        for i in range(number_of_rows):
            self.top_frame.grid_rowconfigure(i, weight=1)

        # Configure the grid layout for top_frame
        self.top_frame.grid_columnconfigure((0, 1, 2), weight=1)

        # Show statistics per language in top frame
        self.display_stats()

        ### -- Now the lower frame -- Tabbed frame for each language
        # Row assignments
        SEARCH_ROW: Final[int] = 0
        VOICE_ROW: Final[int] = 1
        self.TABLE_ROW: Final[int] = 2

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

        self.tabview = self.create_tabview()

        # when tab is selected, change values for voices
        # should probably cache them at some point
    def on_tab_change(self):
        self.after(100, self.update_comboboxes)

    def create_tabview(self):
        tabview = ctk.CTkTabview(self.language_frame, 
                                      command=self.on_tab_change)
        tabview.grid(row=self.TABLE_ROW, column=0, padx=2, pady=2, sticky="nsew")

        # Create tabs -- should be enumeration of languages
        tabEnglish = tabview.add("English")
        tabSpanish = tabview.add("Spanish")
        tabGerman = tabview.add("German")

        # Add scrollable frames
        self.englishFrame = ctk.CTkFrame(tabEnglish)
        self.englishFrame.pack(side="top", expand=True, fill="both", padx=2, pady=2)

        self.spanishFrame = ctk.CTkFrame(tabSpanish)
        self.spanishFrame.pack(side="top", expand=True, fill="both", padx=2, pady=2)
      
        self.germanFrame = ctk.CTkFrame(tabGerman)
        self.germanFrame.pack(side="top", expand=True, fill="both", padx=2, pady=2)

        self.englishTree = self.create_table(self.englishFrame, 'en')     
        self.spanishTree = self.create_table(self.spanishFrame, 'es-CO')
        self.germanTree = self.create_table(self.germanFrame, 'de')

        return tabview

    def display_stats(self):
        # Need to refactor into a language-specific function

        # get error and 'no task' stats
        statsData = u.get_stats()

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

        # First row
        generated_english = u.count_audio_files('en')
        self.generatedEnglish = ctk.CTkLabel(self.top_frame, text=f'English Audio: {generated_english}')
        self.generatedEnglish.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

        generated_spanish = u.count_audio_files('es-CO')
        self.generatedSpanish = ctk.CTkLabel(self.top_frame, text=f'Spanish Audio: {generated_spanish}')
        self.generatedSpanish.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")

        generated_german = u.count_audio_files('de')
        self.generatedGerman = ctk.CTkLabel(self.top_frame, text=f'German Audio: {generated_german}')
        self.generatedGerman.grid(row=0, column=2, padx=5, pady=5, sticky="nsew")

        # Second row
        self.errorsEnglish = ctk.CTkLabel(self.top_frame, text=f'English Errors: {englishErrors}')
        self.errorsEnglish.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")

        self.errorsSpanish = ctk.CTkLabel(self.top_frame, text=f'Spanish Errors: {spanishErrors}')
        self.errorsSpanish.grid(row=1, column=1, padx=5, pady=5, sticky="nsew")

        self.errorsGerman = ctk.CTkLabel(self.top_frame, text=f'German Errors: {germanErrors}')
        self.errorsGerman.grid(row=1, column=2, padx=5, pady=5, sticky="nsew")

        # Third row
        self.notaskEnglish = ctk.CTkLabel(self.top_frame, text=f'English No Task: {englishNoTask}')
        self.notaskEnglish.grid(row=2, column=0, padx=5, pady=5, sticky="nsew")

        self.notaskSpanish = ctk.CTkLabel(self.top_frame, text=f'Spanish No Task: {spanishNoTask}')
        self.notaskSpanish.grid(row=2, column=1, padx=5, pady=5, sticky="nsew")

        self.notaskGerman = ctk.CTkLabel(self.top_frame, text=f'German No Task: {germanNoTask}')
        self.notaskGerman.grid(row=2, column=2, padx=5, pady=5, sticky="nsew")           

        ## Voice row here
        self.voiceEnglish = ctk.CTkLabel(self.top_frame, text=f'Voice: {self.englishVoice}')
        self.voiceEnglish.grid(row=3, column=0, padx=5, pady=5, sticky="nsew")

        self.voiceSpanish = ctk.CTkLabel(self.top_frame, text=f'Voice: {self.spanishVoice}')
        self.voiceSpanish.grid(row=3, column=1, padx=5, pady=5, sticky="nsew")

        self.voiceGerman = ctk.CTkLabel(self.top_frame, text=f'Voice: {self.germanVoice}')
        self.voiceGerman.grid(row=3, column=2, padx=5, pady=5, sticky="nsew")

    def create_search_frame(self, parent, row):
        search_frame = ctk.CTkFrame(parent)
        search_frame.grid(row=row, column=0, padx=2, pady=2, sticky="ew")

        # Configure the grid layout for search_frame
        search_frame.grid_columnconfigure(1, weight=1)  # Make the entry expandable

        # Add label to the search_frame
        label = ctk.CTkLabel(search_frame, text="Search for task: ")
        label.grid(row=0, column=0, padx=(5,5), pady=2, sticky="w")

        # Create the search box and add it to search_frame
        parent.search_var = tk.StringVar()
        parent.search_entry = ctk.CTkEntry(search_frame, textvariable=parent.search_var)
        parent.search_entry.grid(row=0, column=1, padx=(5,5), pady=2, sticky="ew")

        # bind to current language / code for displaying results
        parent.search_entry.bind("<Return>", lambda event: self.search_treeview(parent))
        CTkToolTip(parent.search_entry, message="Type a task id and then <Return> to navigate to the item and play the text.")
        return search_frame  # Return the frame in case you need to reference it later

    def create_voice_frame(self, parent, row):
        voice_frame = ctk.CTkFrame(parent)
        voice_frame.grid(row=row, column=0, padx=5, pady=2, sticky="ew")

        # Configure the grid layout for the voice frame
        voice_frame.grid_columnconfigure(1, weight=1)  # Make the entry expandable

        # Add PlayHt elements
        label = ctk.CTkLabel(voice_frame, text="Compare PlayHt Voice: ")
        label.grid(row=0, column=0, padx=(5,5), pady=2, sticky="w")

        service = 'PlayHt'
        voice_values = self.get_voice_list(service)

        self.ht_voice_combobox = ctk.CTkComboBox(voice_frame, values=voice_values, \
            command=lambda choice: self.voice_compare_callback(choice, service))
        self.ht_voice_combobox.grid(row=0, column=1, padx=(5,5), pady=2, sticky="w")
        self.ht_voice_combobox.set("Select a PlayHt Voice")

        label = ctk.CTkLabel(voice_frame, text="Compare ElevenLabs Voice: ")
        label.grid(row=0, column=2, padx=(5,5), pady=2, sticky="w")

        service = 'ElevenLabs'
        voice_values = self.get_voice_list(service)

        self.eleven_voice_combobox = ctk.CTkComboBox(voice_frame, values=voice_values, \
            command=lambda choice: self.voice_compare_callback(choice, service))
        self.eleven_voice_combobox.grid(row=0, column=3, padx=(5,5), pady=2, sticky="w")
        self.eleven_voice_combobox.set("Select an ElevenLabs Voice")

        return voice_frame  # Return the frame in case you need to reference it later

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
        
                # play audio
                # should go by column name...
                playsound(item_values[4])

        # Create a treeview widget for the table
        columns = ("Item", "Task", "English", "Translated", "Audio")
        style = ttk.Style()
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
        for index, row in self.ourData.iterrows():
            base = "audio_files"

            if type(row['labels']) == type('str'):
                audio_file_name = u.audio_file_path(row['labels'], row['item_id'], base, lang_code)
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

        if active_tab == "English":
            tree = self.englishTree
        elif active_tab == "Spanish":
            tree = self.spanishTree
        elif active_tab == "German":
            tree = self.germanTree
        else:
            print ("NO LANGUAGE")
            exit()

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

    def update_comboboxes(self):
        # get_language_list used current tab to derive lang_code
        ht_voice_list = self.get_voice_list('PlayHt')
        eleven_voice_list = self.get_voice_list('ElevenLabs')

        # update combo boxes for both services
        self.ht_voice_combobox.configure(values=ht_voice_list)
        self.ht_voice_combobox.set(ht_voice_list[0] if ht_voice_list else "")

        self.eleven_voice_combobox.configure(values=eleven_voice_list)
        self.eleven_voice_combobox.set(eleven_voice_list[0] if eleven_voice_list else "")

    def get_voice_list(self, service):

        global ht_english_voice_list
        global ht_spanish_voice_list
        global ht_german_voice_list

        global eleven_english_voice_list
        global eleven_spanish_voice_list
        global eleven_german_voice_list

        global eleven_english_voice_dict
        global eleven_spanish_voice_dict
        global eleven_german_voice_dict

        # we get called before there is a tab view
        # so in that case we default to English
        # (a little lame:))
        try:
            if self.tabview.winfo_exists():
                active_tab = self.tabview.get()

            # Needs refactoring:)!
            if active_tab == "English":
                lang_code = 'en'
                if service == 'PlayHt':
                    if 'ht_english_voice_list' in globals():
                        return ht_english_voice_list
                elif service == 'ElevenLabs':
                    if 'eleven_english_voice_list' in globals():
                        return eleven_english_voice_list
            elif active_tab == "Spanish":
                lang_code = 'es-CO'
                if service == 'PlayHt':
                    if 'ht_spanish_voice_list' in globals():
                        return ht_spanish_voice_list
                elif service == 'ElevenLabs':
                    if 'eleven_spanish_voice_list' in globals():
                        return eleven_spanish_voice_list
            elif active_tab == "German":
                lang_code = 'de'
                if service == 'PlayHt':
                    if 'ht_german_voice_list' in globals():
                        return ht_german_voice_list
                elif service == 'ElevenLabs':
                    if 'eleven_german_voice_list' in globals():
                        return eleven_german_voice_list
            else:
                print ("NO LANGUAGE")
                exit()
        except:
            # assume we will show english when created
            lang_code = 'en'

        # voice list not found
        if service == 'PlayHt':
            voice_list = playHt_utilities.list_voices(lang_code)
            voices = []
            for voice in voice_list:
                voices.append(voice.get('value'))
            if lang_code == 'en':
                ht_english_voice_list = voices
            elif lang_code == 'es-CO':
                ht_spanish_voice_list = voices
            elif lang_code == 'de':
                ht_german_voice_list = voices
            return voices    

        elif service == 'ElevenLabs':
            voice_dict = elevenlabs_utilities.list_voices(lang_code)
            voices = list(voice_dict.keys())

            # We need to find a way to retrieve voice_ids later
            # And we have 3 (for now) voice dictionaries
            voice_ids = list(voice_dict.values())
            if lang_code == 'en':
                eleven_english_voice_dict = voice_dict
                eleven_english_voice_list = voices
            elif lang_code == 'es-CO':
                eleven_spanish_voice_dict = voice_dict
                eleven_spanish_voice_list = voices
            elif lang_code == 'de':
                eleven_german_voice_dict = voice_dict
                eleven_german_voice_list = voices
            return voices    
            
### Needs to support both services

    def voice_compare_callback(self, chosen_voice, service):   

        # trees don't seem to have named columns?
        TRANSLATION_COLUMN = 3

        # We want to find the selected item (if any) and render
        # it with the selected voice, and the current language
        if self.tabview.get() == "English":
            useTree = self.englishTree
            #use_voicedict = eleven_english_voice_dict
        elif self.tabview.get() == "Spanish":
            useTree = self.spanishTree
            #use_voicedict = eleven_spanish_voice_dict
        elif self.tabview.get() == "German":
            useTree = self.germanTree
            #use_voicedict = eleven_german_voice_dict
        else:
            print("Nothing Selected")
            return

        voice = chosen_voice        

        selected_item = useTree.selection()[0]
        selected_row = useTree.item(selected_item)
        
        column_values = selected_row['values']
        translated_text = column_values[TRANSLATION_COLUMN]

        if service == 'PlayHt':
            translated_audio = playHt_utilities.get_audio(translated_text, voice)
            if len(translated_audio) == 0:
                return
            self.play_data_object(translated_audio)
        elif service == 'ElevenLabs':
            # we need to look up the voice id (or not!)
            #voice_id = use_voicedict[voice]
            elevenlabs_utilities.play_audio(translated_text, voice)

    def play_data_object(self, audio_data):
        # Create a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        temp_filename = temp_file.name
    
        try:
        # Write the audio data to the temporary file
            temp_file.write(audio_data)
            temp_file.close()
        
            # Play the temporary file
            playsound(temp_filename)
        finally:
            # Clean up the temporary file
            os.unlink(temp_filename)



if __name__ == "__main__":
    app = App()
    app.mainloop()

