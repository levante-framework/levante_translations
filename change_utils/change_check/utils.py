from typing import Any, Dict, Optional

from crowdin_api import CrowdinClient
from crowdin_api.sorting import Sorting, SortingOrder, SortingRule
from crowdin_api.api_resources.string_translations.enums import ListStringTranslationsOrderBy
from flatten_json import flatten, unflatten_list
from pyairtable import Api
from change_check import config
import warnings
from google.cloud import storage


def build_task_file_map() -> Dict[str, Any]:
	"""
	Map Airtable ``taskManual`` → Crowdin split itembank file id from the source-strings table
	(``split_itembank_fileId``).
	"""
	airtable_levante = Api(config.LEV_AT_PAT)
	ss_table = airtable_levante.table(config.LEV_AT_BASE, config.LEV_AT_SSTABLE)
	task_file_map: Dict[str, Any] = {}
	for record in ss_table.all():
		fields = record.get("fields", {})
		task_manual = fields.get("taskManual")
		split_file_id = fields.get("split_itembank_fileId")
		if task_manual and split_file_id:
			if task_manual not in task_file_map:
				task_file_map[task_manual] = split_file_id
	return task_file_map


def getSourceString(stringId):
	levanteMain=CrowdinClient(token=config.LEV_CI, project_id=config.LEV_CI_PID)
	source_string=levanteMain.source_strings.get_string(stringId=stringId)
	return source_string["data"]

def get_approved_translation_text(
	client: CrowdinClient,
	string_id: int,
	language_id: str,
) -> Optional[str]:
	"""Return text of an **approved** translation for ``language_id``, or ``None`` if none."""
	sorting = Sorting([SortingRule(ListStringTranslationsOrderBy.CREATED_AT, SortingOrder.DESC)])
	try:
		translation = client.string_translations.list_string_translations(
			stringId=string_id,
			languageId=language_id,
			orderBy=sorting,
		)
		for t in translation.get("data") or []:
			approval = client.string_translations.list_translation_approvals(
				orderBy=sorting,
				translationId=t["data"]["id"],
				limit=1,
			)
			if len(approval.get("data") or []) > 0:
				return t["data"]["text"]
	except Exception:
		return None
	return None


def getTranslation(stringId,fileId,lcode,translationFilter):
	levanteMain=CrowdinClient(token=config.LEV_CI, project_id=config.LEV_CI_PID)
	sorting = Sorting([SortingRule(ListStringTranslationsOrderBy.CREATED_AT, SortingOrder.DESC),])
	try:
		translation=levanteMain.string_translations.list_string_translations(
			stringId=stringId,
			languageId=lcode,
			orderBy=sorting
		)
		if translationFilter=="latest":
			if len(translation["data"])>0:
				text=translation["data"][0]["data"]["text"]
				return text
			else:
				#if it gets here this means it hasn't found any translations at all
				return False
		elif translationFilter=="approved":
			translations=translation["data"]
			for t in translations:
				approval=levanteMain.string_translations.list_translation_approvals(
					orderBy=sorting,
					translationId=t["data"]["id"],
					limit=1
				)
				if len(approval["data"])>0:
					text=t["data"]["text"]
					return text
			#if it gets here, this means it hasn't found any approved translations
			return False
	except Exception as e:
		print("ERROR TYPE:", type(e).__name__)
		print("ERROR MESSAGE:", e)
		#print("Crowdin returned 404 error for",str(stringId),". Source string not found.")
		return False

def getStringID(stringKey,fileId):
	levanteMain=CrowdinClient(token=config.LEV_CI, project_id=config.LEV_CI_PID)
	response=levanteMain.source_strings.list_strings(fileId=fileId, filter=stringKey, scope="identifier")
	# If there are no matching strings, return False instead of raising
	if "data" in response and response["data"]:
		return response["data"][0]["data"]["id"]
	return False

def flatten_custom(y):
	out = {}
	def flatten_c(x, name=''):
		# If the Nested key-value
		# pair is of dict type
		if isinstance(x,dict):
			if "default" in x:
				out[name[:-1]]=x
			else:
				for a in x:
					flatten_c(x[a], name + a + '_')
		# If the Nested key-value
		# pair is of list type
		elif isinstance(x,list):
			i = 0
			for a in x:
				flatten_c(a, name + str(i) + '_')
				i += 1
		else:
			out[name[:-1]] = x
	flatten_c(y)
	return out

def flatten_custom_source(y):
	out = {}
	def flatten_c(x, name=''):
		# If the Nested key-value
		# pair is of dict type
		if isinstance(x,dict):
			if "en-US" in x:
				out[name[:-1]]={"default":x["default"]}
			else:
				for a in x:
					flatten_c(x[a], name + a + '_')
		# If the Nested key-value
		# pair is of list type
		elif isinstance(x,list):
			i = 0
			for a in x:
				flatten_c(a, name + str(i) + '_')
				i += 1
		else:
			out[name[:-1]] = x
	flatten_c(y)
	return out

def initialize_gcs():
	"""Initialize Google Cloud Storage client using GOOGLE_APPLICATION_CREDENTIALS environment variable."""
	import os
	from pathlib import Path
	
	creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
	if not creds_path:
		raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS environment variable is not set")
	
	# Resolve relative paths - try multiple possible base directories
	if not os.path.isabs(creds_path):
		# Try resolving from different possible base directories
		possible_bases = [
			Path(__file__).parent.parent.parent,  # change_utils/change_check -> change_utils -> project root
			Path(__file__).parent.parent.parent.parent,  # workspace root (one level up from change_utils)
			Path.cwd(),  # Current working directory
		]
		
		resolved_path = None
		for base in possible_bases:
			candidate = (base / creds_path).resolve()
			if candidate.exists():
				resolved_path = candidate
				break
		
		if resolved_path:
			os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(resolved_path)
		else:
			# If we can't find it, try the original path anyway (might be absolute or work from CWD)
			pass
	
	try:
		return storage.Client()
	except Exception as e:
		raise RuntimeError(f"Failed to initialize Google Cloud Storage client: {e}. Check that GOOGLE_APPLICATION_CREDENTIALS points to a valid credentials file.")