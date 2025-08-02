import utilities.config as conf
import pandas as pd

source = conf.item_bank_translations
df = pd.read_csv(source)

df = df.rename(columns = {'identifier' : 'item_id', 'labels' : 'task'})
del df['context']

df.to_csv('../translation_text/item_bank_translations.csv', index = False, encoding = "utf-8")
