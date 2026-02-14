from crowdin_api import CrowdinClient
import os
import urllib.request
import xml.etree.ElementTree as et
from pyairtable import Api, formulas
import config



def crowdinCurrent():
	levanteMain=CrowdinClient(token=config.LEV_CI, project_id=config.LEV_CI_PID)
	fileurl=levanteMain.translations.export_project_translation("en-US",format="xliff",skipUntranslatedStrings=False,exportApprovedOnly=False)["data"]["url"]
	os.makedirs("sync_tmp/", exist_ok=True)
	urllib.request.urlretrieve(fileurl, "sync_tmp/en-US-source.xliff")

def crowdinCurrentSplit():
	levanteMain=CrowdinClient(token=config.LEV_CI, project_id=config.LEV_CI_PID)
	api = Api(config.LEV_AT_PAT)
	table=api.table(config.LEV_AT_BASE,config.LEV_AT_SSTABLE)
	records=table.all(fields=["audio_file","split_itembank_fileId"])
	fileIds=[]
	for record in records:
		fileIds.append(record['fields']["split_itembank_fileId"])
	fileIds=list(set(fileIds))
	for f in fileIds:
		fileurl=levanteMain.translations.export_project_translation("en-US",fileId=f,format="xliff",skipUntranslatedStrings=False,exportApprovedOnly=False)["data"]["url"]
	os.makedirs("sync_tmp/", exist_ok=True)
	urllib.request.urlretrieve(fileurl, "sync_tmp/en-US-source-"+str(f)+".xliff")
	return fileIds

def getItembankItems():
	tree=et.parse("sync_tmp/en-US-source.xliff")
	root=tree.getroot()
	itembank=False
	for f in root:
		if "item-bank" in f.attrib["original"]:
			itembank=f[1]
			break
	return itembank

def syncAirtable_legacy():
	crowdinCurrent()
	api = Api(config.LEV_AT_PAT)
	itembank=getItembankItems()
	table=api.table(config.LEV_AT_BASE,config.LEV_AT_SSTABLE)
	for item in itembank:
		crowdin_stringID = int(item.attrib["id"])
		resname=item.attrib["resname"]
		sourceString=item[0].text
		formula=formulas.match({"audio_file":resname})
		records=table.all(formula=formula)
		if records==[]:
			print(resname,"not found in airtable, proceed to add function")
			newRow= {
				"audio_file":resname,
				"crowdin_stringId":crowdin_stringID,
				"crowdin_source_string":sourceString
			}
			table.create(newRow)

#ONLY to cascade changes from Crowdin to Airtable, which eventually we should not be doing...
def syncAirtable_split():
	levanteMain=CrowdinClient(token=config.LEV_CI, project_id=config.LEV_CI_PID)
	api = Api(config.LEV_AT_PAT)
	table=api.table(config.LEV_AT_BASE,config.LEV_AT_SSTABLE)
	records=table.all(fields=["audio_file","split_itembank_fileId","split_stringId","source_string_of_truth"])
	for item in itembank:
		crowdin_stringID = int(item.attrib["id"])
		resname=item.attrib["resname"]
		sourceString=item[0].text
		formula=formulas.match({"audio_file":resname})
		records=table.all(formula=formula)
		if records==[]:
			print(resname,"not found in airtable, proceed to add function")
			newRow= {
				"audio_file":resname,
				"crowdin_stringId":crowdin_stringID,
				"crowdin_source_string":sourceString
			}
			table.create(newRow)

langs=["de","de-CH","es-AR","es-CO","en-GB","en-GH","en-US","fr-CA","nl"]
for lang in langs:
	getCurrent(lang)
	print("Finished ", lang)
#sourceFile=getCurrent("en")
#checkAirtable("en11Dec-levante.xliff")

