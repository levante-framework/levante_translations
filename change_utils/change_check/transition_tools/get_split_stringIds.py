from crowdin_api import CrowdinClient
from crowdin_api.sorting import Sorting, SortingOrder, SortingRule
from crowdin_api.api_resources.string_translations.enums import ListStringTranslationsOrderBy
from pyairtable import Api, formulas
from change_check import config
import json



def main():
	levanteMain=CrowdinClient(token=config.LEV_CI, project_id=config.LEV_CI_PID)
	api = Api(config.LEV_AT_PAT)
	stringtable=api.table(config.LEV_AT_BASE,config.LEV_AT_SSTABLE)
	translationTracker=Api(config.AT_TRACKER)
	stringIds=[]
	records=stringtable.all(fields=["audio_file","split_itembank_fileId"], formula="{split_itembank_fileId} != BLANK()")
	fileIds=[]
	for record in records:
		fileIds.append(record['fields']["split_itembank_fileId"])
	fileIds=list(set(fileIds))
	taskDict={}
	for f in fileIds:
		source_strings=levanteMain.source_strings.list_strings(
			fileId=f,
			limit=220)
		taskDict[f]=[]
		for s in source_strings["data"]:
			taskDict[f].append(s["data"])
	print("writing string info to file....")
	with open("newStringIds.json", "w",encoding="utf8") as outfile:
		json.dump(taskDict, outfile, indent=4, default=str)
	##start here if successfuly wrote to file
	for record in records:
		myfile=record["fields"]["split_itembank_fileId"]
		rowid=record["id"]
		for item in taskDict[myfile]:
			if record["fields"]["audio_file"]==item["identifier"]:
				stringtable.update(rowid,{"split_stringId":item["id"]})	
				break
if __name__ == "__main__":
	main()
