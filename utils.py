import requests
from bs4 import BeautifulSoup
import json
import os

def scrape_website_content(url):
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        text_content = ''
        seen_texts = set()

        # List of classes to exclude
        classes_to_exclude = [
            'w-full bg-infinia',
            'container-inner flex flex-col justify-center items-center',
        ]

        # Remove specific divs and navs by their class names
        for class_name in classes_to_exclude:
            for element in soup.find_all(class_=class_name):
                element.decompose()

        # Remove unwanted text
        unwanted_texts = [
            "EN", "COMPANY", "SOLUTIONS", "PRODUCTS", "PROJECTS", "Visit Website"
        ]

        # Collect text from all remaining div elements
        for div in soup.find_all('div'):
            div_text = div.get_text(separator='\n', strip=True)
            # Remove unwanted text lines
            div_text_lines = div_text.split('\n')
            div_text_lines = [line for line in div_text_lines if line not in unwanted_texts]
            div_text = '\n'.join(div_text_lines)

            # Split the div text into lines and add each line to the seen_texts set to avoid duplicates
            lines = div_text.split('\n')
            unique_lines = []
            for line in lines:
                if line not in seen_texts:
                    unique_lines.append(line)
                    seen_texts.add(line)
            if unique_lines:
                text_content += '\n'.join(unique_lines) + '\n'

        return text_content.strip()
    else:
        print(f"Failed to retrieve content from {url}")
        return None
        
def read_json_file(file_path):
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
        return data
    except FileNotFoundError:
        print("File not found.")
        return None
    except json.JSONDecodeError:
        print("Error decoding JSON.")
        return None
    
def is_empty_json(data):
    if data is None:
        return True
    if isinstance(data, dict) and not data:
        return True
    if isinstance(data, list) and not data:
        return True
    return False

def is_chunk_infos_empty(INDEX_PATH, CHUNK_INFOS_PATH):
    chunk_json = read_json_file(CHUNK_INFOS_PATH)
    if not os.path.exists(INDEX_PATH) or not os.path.exists(CHUNK_INFOS_PATH):
        return True

    if(is_empty_json(chunk_json)):
        return True
    return False
