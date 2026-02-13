from crowdin_api import CrowdinClient
from pyairtable import Api, Table
from pyairtable.formulas import match
from dotenv import load_dotenv
from datetime import datetime
from difflib import SequenceMatcher, unified_diff
from collections import OrderedDict
from flatten_json import flatten, unflatten_list
from change_check import utils, config
import requests
import argparse
import os
import json
import csv


# This already works! But it should be recording and tracking the diffs in airtable instead of CSVs...need to build that in, but not a lot of point until we have done the one-time transition
#could be single import?
def main():
	#surveys=["parentsurvey"]
	#checkSurveys(surveys)CLI=argparse.ArgumentParser()
	CLI=argparse.ArgumentParser()
	#a list of surveys to update. options are caregiver-family, caregiver-child, teacher-general, teacher-classroom
	CLI.add_argument(
		"--platform",
		default="none",
		help="Specify a single platform element, either tasks or surveys"
	)


	args=CLI.parse_args()
	updateType=args.platform
	if updateType!="surveys" and updateType!="tasks":
		print("Error: Please provide a valid platform for source string check. Use 'surveys' or 'tasks'.")
		exit()
	if updateType=="tasks":
		print("Checking for task changes...")
		checkItembank()
	if updateType=="surveys":
		print("Checking for survey changes...")
		checkSurveys()

def writetoairtable(adiffbase, atable, rows):
	translationTracker=Api(config.AT_TRACKER)
	insertRows=[]
	inTable=False
	for r in rows:
		inTable=reconcileRow(adiffbase, atable,r)
		if not inTable:
			insertRows.append(r)
	table=translationTracker.table(adiffbase,atable)
	results=table.batch_create(insertRows)
	return results

def reconcileRow(base,table,row):
	translationTracker=Api(config.AT_TRACKER)
	formula=match({"at_audiokey":row["at_audiokey"],"updated":False})
	t=translationTracker.table(base,table)
	record=t.first(formula=formula)
	if record is None:
		return False
	else:
		print(record["id"])
		t.update(record["id"],row)
		return True
			

def checkItembank():
	airtableLevante = Api(config.LEV_AT_PAT)
	ss_table=airtableLevante.table(config.LEV_AT_BASE,config.LEV_AT_SSTABLE)
	changes=[]
	for record in ss_table.all():
		fields = record.get("fields", {})
		task=fields.get("taskManual")
		if task=="DELETE":
			continue
		audiokey = fields.get("audio_file")
		airtableString=fields.get("source_string_of_truth")
		stringId = fields.get("split_stringId")
		if stringId:
			crowdin_source=utils.getSourceString(stringId)
			crowdin_source_string=crowdin_source["text"]
			crowdin_source_key=crowdin_source["identifier"]
		else:
			crowdin_source_key=False
			crowdin_source_string=False
		now=datetime.now()
		dateTimeFound=now.isoformat()
		check=False
		row={
			"at_audiokey":audiokey,
			"at_string":airtableString,
			"crowdin_id":stringId,
			"changeKey":False,
			"changeString":False,
			"newString":False,
			"updated":False,
			"DDMMYYFound":dateTimeFound
		}
		if crowdin_source_string:
			if audiokey!=crowdin_source_key or airtableString!=crowdin_source_string:
				row["changeKey"]=audiokey!=crowdin_source_key
				row["ci_string"]=crowdin_source_string
				row["ci_audiokey"]=crowdin_source_key
				row["changeString"]=airtableString!=crowdin_source_string
				changes.append(row)					
		else:
			row["newString"]=True
			changes.append(row)
	if len(changes)==0:
		print("No changes or additions found in itembank. Crowdin and Airtable are in sync.")
	else:
		writetoairtable(config.AT_TRACKER_BASE,config.AT_IB_DIFFTABLE,changes)
		print("Found",len(changes)," changes/additions to itembank. See itembank diff in airtable for details.")

def checkSurveys():
	changes=[]
	changedFiles=[]
	#should have file, flattened key, old string, new string
	structureFlag=False
	surveyList=["parent_survey_child.json","parent_survey_family.json","teacher_survey_classroom.json","teacher_survey_general.json"]
	folder_path=os.path.join(os.getcwd(), "newsurveys")
	print("Current working directory:", os.getcwd())
	print(folder_path)
	os.makedirs(folder_path,exist_ok=True)
	if not os.listdir(folder_path):
		print(f"newsurveys folder is empty! One or more of these json files: {surveyList} must be present in newsurveys/ folder.")
		exit()
	present_files = [f for f in surveyList if os.path.isfile(os.path.join(folder_path, f))]
	if present_files:
		print(f"Checking the following survey files: {present_files}")
	else:
		print(f"Error: None of the required survey files are present. Please upload one or more of the following files after downloading them from surveyjs:{surveyList}")
	for survey in present_files:
		prodSurvey="https://storage.googleapis.com/levante-assets-prod/surveys/"+survey
		surveyJs=folder_path+"/"+survey
		# There is no way to pull surveyjs json unless we host our own survey creator instance. This is something we should consider but do not currently have, so for now, this works by:
		# 1. Reading files from the newsurvey folder
		# 2. Once changes are logged in airtable, user is ready to run update_source_strings
		# 3. Within update source strings, after all updates are made, it will delete the files in the newsurvey/ folder
		# This may soßme nuclear, but they will still be online
		
		response = requests.get(prodSurvey)
		response.raise_for_status()  # raises error if not 200
		surveyJsonProd = response.json()  # automatically parses JSON
		with open(surveyJs,"r") as f:
			surveyJsonEditor=json.load(f)

		surveyStringProd=json.dumps(surveyJsonProd)
		surveyStringEditor=json.dumps(surveyJsonEditor)
		seqmatch=SequenceMatcher(None, surveyStringProd,surveyStringEditor)
		flatProd=utils.flatten_custom_source(surveyJsonProd)
		flatSJS=utils.flatten_custom_source(surveyJsonEditor)
		if seqmatch==1:
			print(f"No changes found in {surveyJs}. Proceeding to next survey.")
		else:
			#check if they have all the same keys
			if flatProd.keys()==flatSJS.keys():
				#find what string(s) have changed...it may be none if there's just a change in order, in which case, flag that and just use the second file
				for key in flatSJS:
					if flatProd[key]!=flatSJS[key]:
						if isinstance(flatProd[key],dict) and isinstance(flatSJS[key],dict):
							#they're both strings
							now=datetime.now()
							dateTimeFound=now.isoformat()
							row = {
								"surveyFile":survey,
								"flatKey_Prod":key,
								"flatKey_SJS":key,
								"oldString":flatProd[key]["default"],
								"newString":flatSJS[key]["default"],
								"updated":False,
								"dateFound":dateTimeFound,
								"at_audiokey":key
							}
							changes.append(row)
							if survey not in changedFiles:
								changedFiles.append(survey)
			else:
				structureFlag=True
				print("The structure of `",surveyJs, "` has changed. A flattened key map will be needed to integrate changes, and new XLIFF source may be required. No changes have been added to the record for this file.")
				raise Exception("ERROR: JSON structure Changes")
	if len(changes)==0 and not structureFlag:
		print("No survey changes found")
	else:
		writetoairtable(config.AT_TRACKER_BASE,config.AT_SURVEY_DIFFTABLE,changes)
		print("Found ",len(changes), "changes in files: ",str(changedFiles), ".\nSee surveyDiff airtable to verify changes.\nOnce changes have been verified, to cascade changes to crowdin, run update_source_strings --platform survey")


if __name__ == "__main__":
	main()
