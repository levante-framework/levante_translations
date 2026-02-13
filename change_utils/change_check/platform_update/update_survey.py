import argparse
import json
import os
import requests
import xml.etree.ElementTree as et
from crowdin_api import CrowdinClient
from crowdin_api.sorting import Sorting, SortingOrder, SortingRule
from crowdin_api.sorting import Sorting, SortingOrder, SortingRule
from collections import OrderedDict
import warnings
from flatten_json import flatten, unflatten_list
from change_check import utils
from change_check import config
#pulls prod deployed surveys to determine structure.
urlMap={
	"caregiver-child":"https://storage.googleapis.com/levante-assets-prod/surveys/parent_survey_child.json",
	"caregiver-family":"https://storage.googleapis.com/levante-assets-prod/surveys/parent_survey_family.json",
	"teacher-general":"https://storage.googleapis.com/levante-assets-prod/surveys/teacher_survey_general.json",
	"teacher-classroom":"https://storage.googleapis.com/levante-assets-prod/surveys/teacher_survey_classroom.json"
	}

fileMap= {
	"caregiver-child":776,
	"caregiver-family":778,
	"teacher-general":774,
	"teacher-classroom":782,
}

def main():
	CLI=argparse.ArgumentParser()

	# a list of languages, using codes, to update
	CLI.add_argument(
		"--whitelist",
		nargs="*",
		default=["none"]
		)

	#a list of surveys to update. options are caregiver-family, caregiver-child, teacher-general, teacher-classroom
	CLI.add_argument(
		"--types",
		nargs="*",
		default=["none"])
	
	args=CLI.parse_args()
	levanteMain=CrowdinClient(token=config.LEV_CI,project_id=config.LEV_CI_PID)
	project=levanteMain.projects.get_project(projectId=config.LEV_CI_PID)
	allLangs=project["data"]["targetLanguageIds"]
	print(allLangs)
	validSurveys=["caregiver-child","caregiver-family","teacher-general","teacher-classroom"]
	langs=args.whitelist
	surveys=args.types
	#fix this error to make more informative
	languageErr="No whitelist specified - use --whitelist approved to build languages with full approval for specified surveys. Alternatively, use --whitelist with a list of language codes to test unapproved translations. Current available languages in Crowdin are: "+str(allLangs)
	surveyErr="No valid surveys specified to --types. You must specify valid survey files to build. Specify caregiver-family, caregiver-child, teacher-classroom, or teacher-general. Use \"all\" to build all adult surveys."
	if langs == ["approved"] or set(langs).issubset(allLangs):
		pass
	else:
		raise ValueError(languageErr)
	
	if surveys==["all"] or set(surveys).issubset(validSurveys):
		print("Building new versions of all adult surveys...")
		if surveys==["all"]:
			surveys=[*fileMap]
	else:
		raise ValueError(surveyErr)
	if langs == ["approved"]:
		approvalTracker={}
		for s in surveys:
			approvalTracker[fileMap[s]]=[]
		fileIds=list(fileMap.values())
		fileCodes=[*fileMap]
		for s in surveys:
			approvalRate=levanteMain.translation_status.get_file_progress(fileId=fileMap[s])
			for item in approvalRate["data"]:
				if item["data"]["approvalProgress"]==100:
					approvalTracker[fileMap[s]].append(item["data"]["languageId"])

		#	for f in approvalRate["data"]:
		#		print(f["data"]["fileId"], lang, f["data"]["approvalProgress"],"\n_________________________")
		#		if f["data"]["fileId"] in fileIds and f["data"]["approvalProgress"]==100:
		#			approvalTracker[f["data"]["fileId"]].append(lang)

		# Check for files with no approved languages and warn
		for f in approvalTracker:
			if not approvalTracker[f]:
				scode=fileCodes[fileIds.index(f)]
				print(f"⚠️  WARNING: No approved languages found for survey '{scode}' (fileId: {f}). Skipping this survey.")
		# Process files that have approved languages
		for f in approvalTracker:
			if approvalTracker[f]:  # Only process if there are approved languages
				scode=fileCodes[fileIds.index(f)]
				updateSurvey(f,approvalTracker[f],scode,"approved")
	else:
		for s in surveys:
			updateSurvey(fileMap[s],langs,s,'latest')

#loads a survey in flattened format
def loadFlatSurvey(fkey):
	response=requests.get(urlMap[fkey])
	data = response.json()#json.load(response.json(), object_pairs_hook=OrderedDict)
	flatData=utils.flatten_custom(data)
	return flatData

def updateCodes(fsurvey, allowed_langs=None):
	for item in fsurvey:
		#if you find translations
		if isinstance(fsurvey[item],dict):
			#print(fsurvey[item])
			if "en" in fsurvey[item]:
				del fsurvey[item]["en"]
			if "es" in fsurvey[item]:
				del fsurvey[item]["es"]
			if "nl" in fsurvey[item]:
				fsurvey[item]["nl-NL"] = fsurvey[item].pop("nl")
			if "de" in fsurvey[item]:
				fsurvey[item]["de-DE"] = fsurvey[item].pop("de")
			# If a whitelist of allowed languages is provided (e.g. for --whitelist approved),
			# ensure only 'default' plus those approved languages remain.
			if allowed_langs is not None:
				keys_to_keep = set(["default"]) | set(allowed_langs)
				fsurvey[item] = {k: v for k, v in fsurvey[item].items() if k in keys_to_keep}
	return fsurvey

def updateSurvey(fileId,langList,sname,aType):
	flatSurvey=loadFlatSurvey(sname)
	for item in flatSurvey:
		#if you find translations
		if isinstance(flatSurvey[item],dict):
			#for each language to be updated
			if "_" in item:
				#the key is  nested - we've  found something embedded in pages
				stringId=utils.getStringID(item,fileId)
				if not stringId:
					print(f"⚠️  WARNING: No Crowdin string ID found for identifier '{item}' in fileId {fileId}. Skipping this item.")
					continue
				default=utils.getTranslation(stringId,fileId,'en-US',"approved")
				flatSurvey[item]={}
				flatSurvey[item]["en-US"]=default
				flatSurvey[item]["default"]=default
				for lang in langList:
					translation=utils.getTranslation(stringId,fileId,lang,aType)
					if translation:
						flatSurvey[item][lang]=translation
					else:
						flatSurvey[item][lang]="ERROR: No translation found."

	# When building with approved translations, restrict keys to default + approved languages.
	if aType == "approved":
		# Normalize language codes to match final JSON keys after updateCodes conversions.
		normalized_langs = []
		for lang in langList:
			if lang == "de":
				normalized_langs.append("de-DE")
			elif lang == "nl":
				normalized_langs.append("nl-NL")
			else:
				normalized_langs.append(lang)
		# Always keep en-US as well (since we set/enforce it above)
		allowed_langs = set(normalized_langs + ["en-US"])
		flatSurvey=updateCodes(flatSurvey, allowed_langs=allowed_langs)
	else:
		flatSurvey=updateCodes(flatSurvey)
	writeUnfoldedSurvey(flatSurvey, sname)
	#re-nest the json to make it SurveyJS readable


def writeUnfoldedSurvey(surveyDict, sname):
	fullFlat=flatten(surveyDict)
	newjson=unflatten_list(fullFlat)
	
	# Upload to GCS bucket
	storage_client = utils.initialize_gcs()
	bucket_name = "levante-assets-draft"
	bucket = storage_client.bucket(bucket_name)
	
	# Convert survey dict to JSON string
	json_str = json.dumps(newjson, indent=4, ensure_ascii=False)
	
	# Upload to GCS
	gcs_path = f"surveys/{sname}-draft.json"
	blob = bucket.blob(gcs_path)
	blob.upload_from_string(json_str, content_type="application/json")
	print(f"✅ Uploaded {sname} survey to gs://{bucket_name}/{gcs_path}")

if __name__ == "__main__":
	main()
