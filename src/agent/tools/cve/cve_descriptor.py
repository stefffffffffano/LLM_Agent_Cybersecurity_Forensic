import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field


class CVEDescriptor(BaseModel):
    """Retrieve the information about a CVE from online repositories."""
    cve: str = Field(...)

    def run(self):
        if 'CVE' not in self.cve:
            self.cve = f'CVE-{self.cve}'
        # Construct the URL with the provided CVE ID
        url = f"https://nvd.nist.gov/vuln/detail/{self.cve}"

        # Fetch the HTML content of the page
        response = requests.get(url)

        # Check if the request was successful
        if response.status_code == 200:
            # Parse the HTML with BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract specific details for a cleaner output

            # Title and CVE ID
            title = soup.find(
                'span', {'data-testid': 'page-header-vuln-id'}).text.strip()

            # Description
            description = soup.find(
                'p', {'data-testid': 'vuln-description'}).text.strip()

            # Severity Score (CVSS Score)
            severity = soup.find('a', {'id': 'Cvss3NistCalculatorAnchor'})
            if severity:
                severity_score = severity.text.strip()
            else:
                severity = soup.find('a', {'id': 'Cvss3CnaCalculatorAnchor'})
                if severity:
                    severity_score = severity.text.strip()
                else:
                    severity_score = "N/A"

            # Vector String
            vector = soup.find('span', {'class': 'tooltipCvss3NistMetrics'})
            if vector:
                vector_string = vector.text.strip()
            else:
                vector = soup.find('span', {'class': 'tooltipCvss3CnaMetrics'})
                if vector:
                    vector_string = vector.text.strip()
                else:
                    vector_string = "N/A"

            # Display the extracted details in a readable format
            cve_details = f'{title}\n'
            cve_details += f'Description: {description}\n'
            cve_details += f'Severity (CVSSv3): {severity_score}\n'
            cve_details += f'Vector String: {vector_string}\n'

        else:
            cve_details = f"Failed to fetch data. Status code: {response.status_code}"

        return cve_details
