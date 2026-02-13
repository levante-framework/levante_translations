from crowdin_api import CrowdinClient
from crowdin_api.sorting import Sorting, SortingOrder, SortingRule
from crowdin_api.api_resources.string_translations.enums import ListStringTranslationsOrderBy
import json

ciToken="376115245dbe1f4f3b960e8a9c64ece3d2201020a3ec8240925c949b5220ebb4e772655ad47f6142"
levanteMain=CrowdinClient(token=ciToken, project_id="756721")

sorting = Sorting(
    [
        SortingRule(ListStringTranslationsOrderBy.CREATED_AT, SortingOrder.DESC),
    ]
)

response=levanteMain.string_comments.list_string_comments(projectId="756721", limit=200, orderBy=sorting)

print(len(response["data"]))
for item in response["data"]:
	if item["data"]["string"]["fileId"]!=83:
		print("found a comment from another file: ")
		print("File ID: ",item["data"]["string"]["fileId"])

#with open("comments.json", "w",encoding="utf8") as outfile:
#		json.dump(response["data"], outfile, indent=4, default=str)
