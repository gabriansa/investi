import os
from dotenv import load_dotenv
import requests

load_dotenv()

class OpenRouterAPI:
    @staticmethod
    def validate_key(api_key: str) -> bool:
        """Validate OpenRouter API key by attempting to fetch key details."""
        try:
            headers = {"Authorization": f"Bearer {api_key}"}
            response = requests.get("https://openrouter.ai/api/v1/auth/key", headers=headers)
            return response.status_code == 200
        except:
            return False

    def __init__(self, api_key: str):
        self.url = "https://openrouter.ai/api/v1"
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

    def get_key_details(self):
        """
        Get the API key.
        """
        try:
            response = requests.get(f"{self.url}/key", headers=self.headers)
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, {"message": "Unknown error", "response": response.json()}
        except Exception as e:
            return False, {"message": "Unknown error", "response": str(e)}

    def get_remaining_credits(self):
        """
        Get the remaining credits.
        """
        try:
            response = requests.get(f"{self.url}/credits", headers=self.headers)
            if response.status_code == 200:
                remaining_credits = response.json()['data']['total_credits'] - response.json()['data']['total_usage']
                return True, {"remaining_credits": remaining_credits}
            else:
                return False, {"message": "Unknown error", "response": response.json()}
        except Exception as e:
            return False, {"message": "Unknown error", "response": str(e)}
