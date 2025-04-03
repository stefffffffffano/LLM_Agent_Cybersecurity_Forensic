import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
from typing import List


class GetCVEList(BaseModel):
    """Get a list of the most aligned CVEs given a set of keywords"""
    keywords: List = Field(...)

    def run(self):
        max_cves = 30
        url = 'https://cve.mitre.org/cgi-bin/cvekey.cgi'
        url = f"{url}?keyword={'+'.join(self.keywords)}"
        response = requests.get(url)
        if response.status_code != 200:
            cve_list = "Failed to fetch data from CVE site"
        else:
            soup = BeautifulSoup(response.text, 'html.parser')
            cve_table = soup.find('div', id='TableWithRules')
            if not cve_table:
                cve_list = "No results found."
            else:
                cves = []
                # Skip header row, get first X results
                for row in cve_table.find_all('tr')[1:max_cves+1]:
                    columns = row.find_all('td')
                    if len(columns) < 2:
                        continue
                    cve_id = columns[0].get_text(strip=True)
                    cve_desc = columns[1].get_text(strip=True)
                    cves.append(f"{cve_id}: {cve_desc}")
                cve_list = "\n".join(cves)
        return cve_list
