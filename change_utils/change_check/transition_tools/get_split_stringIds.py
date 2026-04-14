from crowdin_api import CrowdinClient
from pyairtable import Api
from change_check import config, utils
import json



def main():
	levanteMain=CrowdinClient(token=config.LEV_CI, project_id=config.LEV_CI_PID)
	api = Api(config.LEV_AT_PAT)
	stringtable=api.table(config.LEV_AT_BASE,config.LEV_AT_SSTABLE)
	fileIds=sorted(set(utils.ITEMBANK_TASK_FILE_MAP.values()))
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
	records=stringtable.all(
		fields=["audio_file", "taskManual"],
		formula="AND({audio_file} != BLANK(), {taskManual} != BLANK())",
	)
	for record in records:
		fields = record.get("fields", {})
		task_key = utils.normalize_task_manual_key(fields.get("taskManual"))
		myfile = utils.ITEMBANK_TASK_FILE_MAP.get(task_key) if task_key else None
		if myfile is None:
			continue
		rowid=record["id"]
		for item in taskDict[myfile]:
			if fields.get("audio_file")==item["identifier"]:
				stringtable.update(rowid,{"split_stringId":item["id"]})	
				break
if __name__ == "__main__":
	main()
