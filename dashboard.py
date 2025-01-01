import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
import pandas as pd
from utilities import utilities as u
from playsound import playsound

class App(ctk.CTk):

    def __init__(self):
        super().__init__()

        ## default file name!
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

        # Top frame with labels
        self.top_frame = ctk.CTkFrame(self.fullFrame)
        self.top_frame.grid(row=0, column=0, columnspan=3, sticky="nsew", padx=10, pady=10)

        # Configure the grid layout for top_frame
        self.top_frame.grid_columnconfigure((0, 1, 2), weight=1)

        number_of_rows = 3 # for now
        for i in range(number_of_rows):
            self.top_frame.grid_rowconfigure(i, minsize=50, weight=1)

        # Show statistics per language in top frame
        self.display_stats()

### -- Now the lower frame -- Tabbed frame for each language

        self.language_frame = ctk.CTkFrame(self)
        self.language_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.language_frame.grid_columnconfigure(0, weight=1)
        self.language_frame.grid_rowconfigure(0, weight=1)

        self.create_search_frame(self.language_frame)
        
        tabview = ctk.CTkTabview(self.language_frame)
        tabview.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

        # Create tabs -- should be enumeration of languages
        tabEnglish = tabview.add("English")
        tabSpanish = tabview.add("Spanish")
        tabGerman = tabview.add("German")

        # Add scrollable frames
        self.englishFrame = ctk.CTkFrame(tabEnglish)
        self.englishFrame.pack(side="top", expand=True, fill="both", padx=10, pady=10)

        self.spanishFrame = ctk.CTkFrame(tabSpanish)
        self.spanishFrame.pack(side="top", expand=True, fill="both", padx=10, pady=10)
      
        self.germanFrame = ctk.CTkFrame(tabGerman)
        self.germanFrame.pack(side="top", expand=True, fill="both", padx=10, pady=10)

        self.englishTree = self.create_table(self.englishFrame, 'en')     
        self.spanishTree = self.create_table(self.spanishFrame, 'es-CO')
        self.germanTree = self.create_table(self.germanFrame, 'de')

    def display_stats(self):
        # Need to refactor into a language-specific function

        # get error and 'no task' stats
        statsData = u.get_stats()

        englishStats = statsData.loc[statsData['Language'] == 'English']
        englishErrors = englishStats['Errors'][0]
        englishNoTask = englishStats['No Task'][0]

        spanishStats = statsData.loc[statsData['Language'] == 'Spanish']
        spanishErrors = spanishStats['Errors'][1]
        spanishNoTask = spanishStats['No Task'][1]

        germanStats = statsData.loc[statsData['Language'] == 'German']
        germanErrors = germanStats['Errors'][2]
        germanNoTask = germanStats['No Task'][2]

        ## Might be good to add a voice row here

        # First row
        generated_english = u.count_audio_files('en')
        self.generatedEnglish = ctk.CTkLabel(self.top_frame, text=f'English Audio: {generated_english}')
        self.generatedEnglish.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        generated_spanish = u.count_audio_files('es-CO')
        self.generatedSpanish = ctk.CTkLabel(self.top_frame, text=f'Spanish Audio: {generated_spanish}')
        self.generatedSpanish.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        generated_german = u.count_audio_files('de')
        self.generatedGerman = ctk.CTkLabel(self.top_frame, text=f'German Audio: {generated_german}')
        self.generatedGerman.grid(row=0, column=2, padx=5, pady=5, sticky="w")

        # Second row
        self.errorsEnglish = ctk.CTkLabel(self.top_frame, text=f'English Errors: {englishErrors}')
        self.errorsEnglish.grid(row=1, column=0, padx=5, pady=5, sticky="w")

        self.errorsSpanish = ctk.CTkLabel(self.top_frame, text=f'Spanish Errors: {spanishErrors}')
        self.errorsSpanish.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        self.errorsGerman = ctk.CTkLabel(self.top_frame, text=f'German Errors: {germanErrors}')
        self.errorsGerman.grid(row=1, column=2, padx=5, pady=5, sticky="w")

        # Third row
        self.notaskEnglish = ctk.CTkLabel(self.top_frame, text=f'English No Task: {englishNoTask}')
        self.notaskEnglish.grid(row=2, column=0, padx=5, pady=5, sticky="w")

        self.notaskSpanish = ctk.CTkLabel(self.top_frame, text=f'Spanish No Task: {spanishNoTask}')
        self.notaskSpanish.grid(row=2, column=1, padx=5, pady=5, sticky="w")

        self.notaskGerman = ctk.CTkLabel(self.top_frame, text=f'German No Task: {germanNoTask}')
        self.notaskGerman.grid(row=2, column=2, padx=5, pady=5, sticky="w")           

    def create_search_frame(self, parent):
        search_frame = ctk.CTkFrame(parent)
        search_frame.grid(row=1, column=0, padx=5, pady=5, sticky="ew")

        # Configure the grid layout for search_frame
        search_frame.grid_columnconfigure(1, weight=1)  # Make the entry expandable

        # Add label to the search_frame
        label = ctk.CTkLabel(search_frame, text="Search for task: ")
        label.grid(row=0, column=0, padx=(5,2), pady=5, sticky="w")

        # Create the search box and add it to search_frame
        parent.search_var = tk.StringVar()
        parent.search_entry = ctk.CTkEntry(search_frame, textvariable=parent.search_var)
        parent.search_entry.grid(row=0, column=1, padx=(2,5), pady=5, sticky="ew")

        # Optionally, you can add the event bindings here
        # parent.search_var.trace("w", self.search_treeview)
        # parent.search_entry.bind("<Return>", lambda event: self.search_treeview(parent, "en"))

        return search_frame  # Return the frame in case you need to reference it later

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

    def search_treeview(self, parentFrame, lang_code, *args):

        query = parentFrame.search_var.get()

        ## This shouldn't be needed if we can sort out the ParentFrame
        if lang_code == 'en':
            tree = self.englishTree
        elif lang_code == 'es-CO':
            tree = self.spanishTree
        elif lang_code == 'de':
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

    

if __name__ == "__main__":
    app = App()
    app.mainloop()

