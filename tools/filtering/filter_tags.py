## To filter out HTML or SSML tags
from bs4 import BeautifulSoup

# Params:
#   inputstring
#
# Returns:
#   filtered string

def filter_HTML(input_string):

    soup = BeautifulSoup(input_string, 'html.parser')
    filtered_content = soup.find('p', class_='content')
    return (filtered_content.text)

def filter_SSML(input_string):
    soup = BeautifulSoup(f"<root>{input_string}</root>", 'xml')
    for tag in soup.find_all(xmlns="http://www.w3.org/2001/10/synthesis"):
        tag.unwrap()
    return soup.root.decode_contents()
