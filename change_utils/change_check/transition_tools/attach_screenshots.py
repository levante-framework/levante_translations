from crowdin_api import CrowdinClient
from pyairtable import Api, formulas
from change_check import config
from crowdin_api.api_resources.screenshots.types import AddTagRequest
import json

def main():
	with open('screenshotinfo.json') as json_file:
		screenshots = json.load(json_file)
	#dump to json to avoid re-querying
	#with open("screenshotInfo.json", "w",encoding="utf8") as outfile:
	#   json.dump(screenshots, outfile, indent=4, default=str)
	#print("Dumped to JSON. Attempting to add tags.")
	addTags(screenshots)

def getShots():
	levanteMain=CrowdinClient(token=config.LEV_CI, project_id=config.LEV_CI_PID)
	screenshots=[]
	limit = 100
	offset = 0
	while True:
		response = levanteMain.screenshots.list_screenshots(
			limit=limit,
			offset=offset
		)
		screenshot_snippet = response["data"]
		screenshots.extend(screenshot_snippet)
		if len(screenshot_snippet) < limit:
			# No more pages
			break
		offset += limit
	print(f"Fetched {len(screenshots)} screenshots")

def addTags(screenshotList):
	print("Found ",len(screenshotList), " screenshots")
	updateCounter=0
	levanteMain=CrowdinClient(token=config.LEV_CI, project_id=config.LEV_CI_PID)
	api = Api(config.LEV_AT_PAT)
	stringtable=api.table(config.LEV_AT_BASE,config.LEV_AT_SSTABLE)
	for shot in screenshotList:
		if updateCounter<397:
			updateCounter+=1
			continue
		screenshot_id = shot["data"]["id"]

	#List tags for each screenshot
		tags = levanteMain.screenshots.list_tags(
			screenshotId=screenshot_id,
			limit=10
		)["data"]
		for tag_entry in tags:
			tag = tag_entry["data"]

			old_string_id = tag.get("stringId")
			if not old_string_id:
				continue
			record = stringtable.first(formula=f"{{crowdin_stringId}} = '{old_string_id}'")
			
			if record:
				print("Found record:", record)
			else:
				print("No record found with stringid",old_string_id)
				continue
			new_string_id=record["fields"]["split_stringId"]
			if tag["position"] is not None:
				if tag["position"]["y"]>tag["position"]["height"]:
					posy=tag["position"]["height"]
				else:
					posy=tag["position"]["y"]
				
				if tag["position"]["x"]>tag["position"]["width"]:
					posx=tag["position"]["width"]
				else:
					posx=tag["position"]["x"]
				position = {
					"x": posx,
					"y": posy,
					"width": tag["position"]["width"],
					"height": tag["position"]["height"],
				}
			else:
				position = None

			tag_request = AddTagRequest(
				stringId=new_string_id,
				position=position
				
			)

			#Create a new tag pointing to the split file string
			levanteMain.screenshots.add_tag(
				screenshotId=screenshot_id,
				data=[tag_request]
			)

			updateCounter+=1
			print(screenshot_id, "updated to include string",new_string_id,".\n",updateCounter, "of ",len(screenshotList)," screenshots updated.")

if __name__ == "__main__":
	main()