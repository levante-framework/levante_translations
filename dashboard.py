import customtkinter as ctk
from tkinter import ttk
import pandas as pd
from utilities import utilities as u
from playsound import playsound
import textwrap

import math
class App(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("Levante Translation Dashboard")
        self.geometry("1000x600")

        # Top frame with buttons
        self.top_frame = ctk.CTkFrame(self)
        self.top_frame.pack(side="top", fill="x", padx=10, pady=10)

        # Tabbed frame
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(expand=True, fill="both", padx=10, pady=10)

        # Create tabs
        self.tab1 = self.tabview.add("Spanish")
        self.tab2 = self.tabview.add("German")

        # Add scrollable frame to Tab 1
        self.scrollable_frame = ctk.CTkScrollableFrame(self.tab1)
        self.scrollable_frame.pack(expand=True, fill="both", padx=10, pady=10)

        self.create_table(self.scrollable_frame)



    def create_table(self, parent):

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
        
#                print(f"Selected item: {item}")
#                print(f"Selected column: {column}")
#                print(f"Item text: {item_text}")
#                print(f"Item values: {item_values}")

                # play audio
                # should go by column name...
                playsound(item_values[4])

        # hard-wire for now:
        lang_code = 'es-CO'

        # Create a treeview widget for the table
        columns = ("Item", "Task", "English", "Translated", "Audio")
        style = ttk.Style()
        style.configure("Treeview", rowheight=80, \
                        font=('TkDefaultFont', 16))

        self.tree = ttk.Treeview(parent, columns=columns, show="headings", style='Treeview')
        self.tree.bind("<<TreeviewSelect>>", on_tree_select)

        # Define column headings
        for col in columns:
            self.tree.heading(col, text=col)
            if col == 'Item' or col == 'Task' or col == 'Audio':
                self.tree.column(col, width=15)
            else:
                self.tree.column(col, width=200)

        ## Hack file name!
        ourData = pd.read_csv("c:/levante/audio-generation/item_bank_translations.csv")
        # Insert DataFrame rows into the Treeview
        for index, row in ourData.iterrows():
            base = "audio_files"

            if type(row['labels']) == type('str'):
                audio_file_name = u.audio_file_path(row['labels'], row['item_id'], base, lang_code)
                values = [row['item_id'], row['labels'], row['en'], row[lang_code], audio_file_name]

                # Hack for column numbers
                values[2] = u.wrap_text(values[2])
                values[3] = u.wrap_text(values[3])

                self.tree.insert("", "end", values=values)

                self.tree.pack(expand=True, fill="both")





    


if __name__ == "__main__":
    app = App()
    app.mainloop()

# Spare stuff
"""
        self.button1 = ctk.CTkButton(self.top_frame, text="Button 1", command=self.button_click)
        self.button1.pack(side="left", padx=5)

        self.button2 = ctk.CTkButton(self.top_frame, text="Button 2", command=self.button_click)
        self.button2.pack(side="left", padx=5)

        self.button3 = ctk.CTkButton(self.top_frame, text="Button 3", command=self.button_click)
        self.button3.pack(side="left", padx=5)
"""
