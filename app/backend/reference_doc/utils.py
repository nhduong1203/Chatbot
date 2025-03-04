import requests
from bs4 import BeautifulSoup
import html2text

def crawl_website(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        return {"status": "success", "content": soup.get_text()}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def convert_html_to_text(html_content):
    text_maker = html2text.HTML2Text()
    text_maker.ignore_links = True
    return text_maker.handle(html_content)
