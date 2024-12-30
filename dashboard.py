import customtkinter as ctk
from tkinter import ttk
import pandas as pd
from utilities import utilities as u
import math
class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Levante Translation Dashboard")
        self.geometry("800x600")

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

        # Create a table in the scrollable frame
        self.create_table(self.scrollable_frame)

    def create_table(self, parent):

        # hard-wire for now:
        lang_code = 'es-CO'

        # Create a treeview widget for the table
        columns = ("Item", "Task", "English", "Translated", "Audio")
        self.tree = ttk.Treeview(parent, columns=columns, show="headings")

        # Define column headings
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=150)

        ## Hack file name!
        ourData = pd.read_csv("c:/levante/audio-generation/item_bank_translations.csv")
        # Insert DataFrame rows into the Treeview
        for index, row in ourData.iterrows():
            base = "audio_files"

            if type(row['labels']) == type('str'):
                audio_file_name = u.audio_file_path(row['labels'], row['item_id'], base, lang_code)
                values = [row['item_id'], row['labels'], row['en'], row[lang_code], audio_file_name]
                self.tree.insert("", "end", values=values)

                self.tree.pack(expand=True, fill="both")

    def button_click(self):
        print("Button clicked!")

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
