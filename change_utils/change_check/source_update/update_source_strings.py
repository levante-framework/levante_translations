from crowdin_api import CrowdinClient
from pyairtable import Api
from pyairtable.formulas import match
from change_check import utils, config
import argparse
from datetime import datetime


def main():
	CLI = argparse.ArgumentParser(description="Update source strings in Crowdin")
	CLI.add_argument(
		"--platform",
		required=True,
		choices=["tasks", "surveys"],
		help="Platform element to update: 'tasks' or 'surveys'"
	)
	CLI.add_argument(
		"--pilot",
		choices=["done", "none"],
		help="Pilot status: 'done' or 'none' (required when --platform is 'tasks')"
	)
	
	args = CLI.parse_args()
	
	if args.platform == "tasks":
		if not args.pilot:
			raise ValueError("--pilot is required when --platform is 'tasks'. Chose 'none' to only change en-US translations in preparation for piloting changes, or 'done' to assume piloting has completed and update source strings.")
		updateTasks(args.pilot)
	elif args.platform == "surveys":
		# TODO: Implement survey updates
		print("Survey updates not yet implemented")
		exit()


def buildTaskFileMap():
	"""Build a map of taskManual to split_itembank_fileid from source string airtable."""
	airtableLevante = Api(config.LEV_AT_PAT)
	ss_table = airtableLevante.table(config.LEV_AT_BASE, config.LEV_AT_SSTABLE)
	
	taskFileMap = {}
	
	for record in ss_table.all():
		fields = record.get("fields", {})
		taskManual = fields.get("taskManual")
		splitFileId = fields.get("split_itembank_fileid")
		
		# Only add if both values exist and taskManual is not empty
		if taskManual and splitFileId:
			# If taskManual already exists, keep the first one (or we could validate they're the same)
			if taskManual not in taskFileMap:
				taskFileMap[taskManual] = splitFileId
	
	return taskFileMap


def updateSourceStringWithTranslations(levanteMain, stringId, newText, pilot, rowId=None, diffTable=None):
	"""
	Update a source string in Crowdin and manage its translations based on pilot status.
	
	Args:
		levanteMain: CrowdinClient instance
		stringId: Crowdin string ID to update
		newText: New text for the source string
		pilot: "done" or "none" - determines approval behavior
		rowId: Optional Airtable record ID to update after successful change
		diffTable: Optional Airtable table to update the record in
	"""
	# Get project info to identify languages
	project = levanteMain.projects.get_project(projectId=config.LEV_CI_PID)
	allLangs = project["data"]["targetLanguageIds"]
	sourceLang = project["data"]["sourceLanguageId"]  # Should be "en-US"
	
	# Identify en- variety languages (en-US, en-GH, etc.)
	enVarieties = [lang for lang in allLangs if lang.startswith("en-")]
	nonEnLangs = [lang for lang in allLangs if not lang.startswith("en-")]
	
	# Step 1: Update the source string
	patch_request = [{
		"op": "replace",
		"path": "/text",
		"value": newText
	}]
	levanteMain.source_strings.edit_string(
		stringId=int(stringId),
		data=patch_request
	)
	print(f"✅ Updated source string {stringId}")
	
	# Step 2: Handle en- variety translations
	for enLang in enVarieties:
		try:
			# Get existing translations for this language
			translations = levanteMain.string_translations.list_string_translations(
				stringId=int(stringId),
				languageId=enLang
			)
			
			# Check if translation exists
			existingTranslation = None
			if translations.get("data") and len(translations["data"]) > 0:
				existingTranslation = translations["data"][0]["data"]
			
			# Create or update translation to match source string
			if existingTranslation:
				# Update existing translation
				translationId = existingTranslation["id"]
				levanteMain.string_translations.restore_string_translation(
					translationId=translationId,
					stringId=int(stringId),
					languageId=enLang,
					text=newText
				)
			else:
				# Create new translation
				levanteMain.string_translations.add_string_translation(
					stringId=int(stringId),
					languageId=enLang,
					text=newText
				)
			
			# Get the translation ID (may need to fetch again after create/update)
			translations = levanteMain.string_translations.list_string_translations(
				stringId=int(stringId),
				languageId=enLang
			)
			if translations.get("data") and len(translations["data"]) > 0:
				translationId = translations["data"][0]["data"]["id"]
				
				# Handle approvals based on pilot status
				if pilot == "done":
					if enLang == "en-US":
						# Approve en-US translation
						try:
							levanteMain.translation_approvals.add_approval(
								stringId=int(stringId),
								languageId=enLang,
								translationId=translationId
							)
							print(f"   ✅ Approved en-US translation")
						except Exception as e:
							# Approval might already exist
							print(f"   ⚠️  Could not approve en-US (may already be approved): {e}")
					else:
						# Unapprove other en- varieties
						try:
							approvals = levanteMain.translation_approvals.list_approvals(
								stringId=int(stringId),
								languageId=enLang
							)
							for approval in approvals.get("data", []):
								levanteMain.translation_approvals.remove_approval(
									approvalId=approval["data"]["id"]
								)
							print(f"   ✅ Unapproved {enLang} translation")
						except Exception as e:
							# May not have approvals to remove
							pass
				else:  # pilot == "none"
					# Unapprove all en- varieties including en-US
					try:
						approvals = levanteMain.translation_approvals.list_approvals(
							stringId=int(stringId),
							languageId=enLang
						)
						for approval in approvals.get("data", []):
							levanteMain.translation_approvals.remove_approval(
								approvalId=approval["data"]["id"]
							)
						print(f"   ✅ Unapproved {enLang} translation")
					except Exception as e:
						# May not have approvals to remove
						pass
					
		except Exception as e:
			print(f"   ⚠️  Error handling {enLang} translation: {e}")
	
	# Step 3: Unapprove non-en language translations (content unchanged)
	for lang in nonEnLangs:
		try:
			approvals = levanteMain.translation_approvals.list_approvals(
				stringId=int(stringId),
				languageId=lang
			)
			for approval in approvals.get("data", []):
				levanteMain.translation_approvals.remove_approval(
					approvalId=approval["data"]["id"]
				)
			if len(approvals.get("data", [])) > 0:
				print(f"   ✅ Unapproved {lang} translation")
		except Exception as e:
			# May not have approvals to remove
			pass
	
	# Step 4: Update Airtable record if provided
	if rowId and diffTable:
		try:
			now = datetime.now()
			# Format: DDMMYY (e.g., 230125 for Jan 25, 2023)
			dateUpdated = now.strftime("%d%m%y")
			diffTable.update(rowId, {
				"updated": True,
				"DDMMYYUpdated": dateUpdated
			})
			print(f"   ✅ Updated Airtable record {rowId}")
		except Exception as e:
			print(f"   ⚠️  Failed to update Airtable record: {e}")


def updateTasks(pilot):
	"""Update source strings for tasks based on Airtable records."""
	
	# Build task file map
	print("Building task file map from source string airtable...")
	taskFileMap = buildTaskFileMap()
	print(f"Found {len(taskFileMap)} unique taskManual to fileId mappings")
	
	# Get rows from AT_IB_DIFFTABLE where updated is false or empty
	translationTracker = Api(config.AT_TRACKER)
	diffTable = translationTracker.table(config.AT_TRACKER_BASE, config.AT_IB_DIFFTABLE)
	
	# Filter directly in Airtable query: updated is False or empty
	# Formula: OR({updated} = FALSE(), {updated} = "")
	formula = "OR({updated} = FALSE(), {updated} = '')"
	rowsToUpdate = diffTable.all(formula=formula)
	
	print(f"Found {len(rowsToUpdate)} rows with updated=False or empty")
	
	# Split into changeString and newString rows
	changeStringRows = []
	newStringRows = []
	
	for record in rowsToUpdate:
		fields = record.get("fields", {})
		if fields.get("changeString") is True:
			changeStringRows.append({
				"id": record["id"],
				"fields": fields
			})
		elif fields.get("newString") is True:
			newStringRows.append({
				"id": record["id"],
				"fields": fields
			})
	
	print(f"Found {len(changeStringRows)} rows with changeString=True")
	print(f"Found {len(newStringRows)} rows with newString=True")
	
	# Initialize Crowdin client
	levanteMain = CrowdinClient(token=config.LEV_CI, project_id=config.LEV_CI_PID)
	
	# Process changeString rows
	for row in changeStringRows:
		fields = row["fields"]
		crowdinId = fields.get("crowdin_id")
		atString = fields.get("at_string")
		
		if not crowdinId or not atString:
			atAudiokey = fields.get("at_audiokey", "unknown")
			print(f"Skipping row with at_audiokey '{atAudiokey}': missing crowdin_id or at_string")
			continue
		
		try:
			print(f"\n📝 Processing string {crowdinId} (at_audiokey: {fields.get('at_audiokey', 'unknown')})")
			updateSourceStringWithTranslations(
				levanteMain=levanteMain,
				stringId=int(crowdinId),
				newText=atString,
				pilot=pilot,
				rowId=row["id"],
				diffTable=diffTable
			)
			print(f"✅ Completed update for string {crowdinId}")
		except Exception as e:
			print(f"❌ Failed to update string {crowdinId}: {e}")
			print(f"   Error type: {type(e).__name__}")
	
	# Process newString rows
	airtableLevante = Api(config.LEV_AT_PAT)
	ss_table = airtableLevante.table(config.LEV_AT_BASE, config.LEV_AT_SSTABLE)
	
	for row in newStringRows:
		fields = row["fields"]
		atAudiokey = fields.get("at_audiokey")
		
		if not atAudiokey:
			print(f"Skipping row {row['id']}: missing at_audiokey")
			continue
		
		# Look up row in LEV_AT_SSTABLE using at_audiokey (matches audio_file field)
		formula = match({"audio_file": atAudiokey})
		ssRecord = ss_table.first(formula=formula)
		
		if not ssRecord:
			print(f"❌ Could not find source string record for audio_file: {atAudiokey}")
			continue
		
		ssFields = ssRecord.get("fields", {})
		taskManual = ssFields.get("taskManual")
		
		if not taskManual:
			print(f"❌ Source string record for {atAudiokey} has no taskManual")
			continue
		
		# Find fileId in taskFileMap
		fileId = taskFileMap.get(taskManual)
		
		if not fileId:
			print(f"❌ Could not find fileId for taskManual: {taskManual}")
			continue
		
		# Get the source string text from at_string
		atString = fields.get("at_string")
		if not atString:
			print(f"❌ Row {row['id']} has no at_string")
			continue
		
		# Get the identifier from the source string record
		identifier = ssFields.get("source_string_of_truth") or atAudiokey
		
		try:
			print(f"\n📝 Creating new string (at_audiokey: {atAudiokey})")
			# Create new source string in Crowdin
			response = levanteMain.source_strings.add_string(
				fileId=int(fileId),
				text=atString,
				identifier=identifier
			)
			# Get the newly created string ID
			newStringId = response["data"]["id"]
			print(f"✅ Created new string {newStringId} in file {fileId} with identifier '{identifier}'")
			
			# Handle translations and approvals for the new string
			updateSourceStringWithTranslations(
				levanteMain=levanteMain,
				stringId=newStringId,
				newText=atString,
				pilot=pilot,
				rowId=row["id"],
				diffTable=diffTable
			)
			print(f"✅ Completed setup for new string {newStringId}")
		except Exception as e:
			print(f"❌ Failed to create string in file {fileId}: {e}")
			print(f"   Error type: {type(e).__name__}")
	
	print("\n✅ Task updates complete")


if __name__ == "__main__":
	main()
