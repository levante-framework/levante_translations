from crowdin_api import CrowdinClient
from datetime import datetime
import os
import urllib.request
import xml.etree.ElementTree as et
import argparse
import tempfile
from pyairtable import Api, formulas
from change_check import config
from change_check import utils


def main():
	CLI=argparse.ArgumentParser(description="Backup translations from Crowdin")
	CLI.add_argument(
		"--langs",
		nargs="*",
		default=["none"],
		required=True,
		help="Backup needs a valid list of language codes to run, or use `--langs all` to backup all languages. Use `--langs show` to display a list of current languages."
		)

	args=CLI.parse_args()
	levanteMain=CrowdinClient(token=config.LEV_CI,project_id=config.LEV_CI_PID)
	project=levanteMain.projects.get_project(projectId=config.LEV_CI_PID)
	allLangs=project["data"]["targetLanguageIds"]
	langs=args.langs
	
	if len(langs) == 1:
		if langs[0] == "show":
			print(f"Currently available languages on levantetranslations Crowdin are: {allLangs}")
			exit()
		elif langs[0] == "all":
			langs = allLangs
		elif langs[0] not in allLangs:
			raise ValueError(f"{langs[0]} is not a valid language code. Available languages: {allLangs}")
	elif len(langs) > 1:
		invalid = [lang for lang in langs if lang not in allLangs]
		if invalid:
			raise ValueError(f"Invalid language codes: {invalid}. Available languages: {allLangs}")
	else:
		raise ValueError("At least one language code is required. Use --langs all to backup all languages.")
	
	# Initialize GCS client
	storage_client = utils.initialize_gcs()
	
	bucket_name = "levante-assets-draft"
	bucket = storage_client.bucket(bucket_name)
	
	for lang in langs:
		print(f"Backing up translations for language: {lang}")
		fileurl = levanteMain.translations.export_project_translation(lang, format="xliff", skipUntranslatedStrings=False, exportApprovedOnly=False)["data"]["url"]
		
		# Download to temporary file
		with tempfile.NamedTemporaryFile(delete=False, suffix=".xliff") as tmp_file:
			tmp_path = tmp_file.name
		
		# Download from Crowdin
		urllib.request.urlretrieve(fileurl, tmp_path)
		
		# Upload to GCS bucket
		timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
		gcs_path = f"translations/crowdin-backup/{lang}-backup-platform-{timestamp}.xliff"
		blob = bucket.blob(gcs_path)
		blob.upload_from_filename(tmp_path, content_type="application/xml")
		print(f"✅ Uploaded {lang} backup to gs://{bucket_name}/{gcs_path}")


if __name__ == "__main__":
	main()