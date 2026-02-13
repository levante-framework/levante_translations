import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

LEV_CI = os.getenv("CROWDIN_TOKEN")
LEV_CI_PID = os.getenv("CROWDIN_LEVANTE_PID")

LEV_AT_PAT = os.getenv("LEVANTE_AT_PAT")
LEV_AT_BASE = os.getenv("LEVANTE_AT_BASEID")
LEV_AT_SSTABLE = os.getenv("LEVANTE_AT_STRINGSTABLE")
LEV_AT_CORPUSTABLE = os.getenv("LEVANTE_CORPUSTABLE")

AT_TRACKER = os.getenv("AT_TRANSLATIONTRACKER")
AT_TRACKER_BASE = os.getenv("AT_TRACKER_BASE")
AT_IB_DIFFTABLE = os.getenv("AT_IB_DIFFTABLE")
AT_SURVEY_DIFFTABLE =  os.getenv("AT_SURVEY_DIFFTABLE")
AT_TRANSL_REVTABLE = os.getenv("AT_TRANSLATIONS_TABLE")

CROWDIN_TEST = os.getenv("CROWDIN_TESTTOKEN")
CROWDIN_TESTPID = os.getenv("CROWDIN_TESTPID")

GOOGLE_APPLICATION_CREDENTIALS_JSON_DEV = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON_DEV")

# Resolve the credentials path if it's relative
GOOGLE_APPLICATION_CREDENTIALS_DEV = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_DEV")
if GOOGLE_APPLICATION_CREDENTIALS_DEV and not os.path.isabs(GOOGLE_APPLICATION_CREDENTIALS_DEV):
	# Try resolving from different possible base directories
	# config.py is in change_utils/change_check/, so:
	# __file__.parent = change_utils/change_check/
	# __file__.parent.parent = change_utils/
	possible_bases = [
		Path(__file__).parent.parent,  # change_utils/ (where secrets/ is located)
		Path(__file__).parent.parent.parent,  # workspace root (one level up from change_utils)
		Path.cwd(),  # Current working directory
	]
	
	resolved_path = None
	for base in possible_bases:
		candidate = (base / GOOGLE_APPLICATION_CREDENTIALS_DEV).resolve()
		if candidate.exists():
			resolved_path = candidate
			break
	
	if resolved_path:
		os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(resolved_path)
	else:
		# If we can't resolve it, use the original path (might work from CWD)
		os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_APPLICATION_CREDENTIALS_DEV
else:
	os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_APPLICATION_CREDENTIALS_DEV

#Raise error if missing
REQUIRED = {
    "LEV_CI":LEV_CI, 
    "LEV_CI_PID":LEV_CI_PID,
    "LEV_AT_PAT":LEV_AT_PAT,
    "LEV_AT_BASE":LEV_AT_BASE,
    "LEV_AT_SSTABLE":LEV_AT_SSTABLE,
    "LEV_AT_CORPUSTABLE":LEV_AT_CORPUSTABLE,
    "AT_TRACKER":AT_TRACKER,
    "AT_TRACKER_BASE":AT_TRACKER_BASE,
    "AT_IB_DIFFTABLE":AT_IB_DIFFTABLE,
    "AT_SURVEY_DIFFTABLE":AT_SURVEY_DIFFTABLE,
    "AT_TRANSL_REVTABLE":AT_TRANSL_REVTABLE,
    "CROWDIN_TEST":CROWDIN_TEST,
    "CROWDIN_TESTPID":CROWDIN_TESTPID
}

for name, value in REQUIRED.items():
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
