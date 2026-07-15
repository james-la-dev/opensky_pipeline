# polls /states/all, handles auth token refresh, bounding box
import json
import requests
import time

PATH_TO_CREDS = "./credentials.json"
OPENSKY_URL = "https://opensky-network.org/api/states/all"
TOKEN_URL = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"


class ApiHandler:
    def __init__(self):
        self._client_id = ""
        self._client_secret = ""
        self._load_creds()
        self._token = None
        self._token_expires_at = 0.0

        # NZ airspace bounding box
        self.lamin = -47.5
        self.lomin = 165.0
        self.lamax = -33.5
        self.lomax = 179.0

    def _get_token(self):
        """Fetch token from TOKEN_URL"""
        if self._token and time.time() < self._token_expires_at - 30:
            return self._token
        response = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
        )
        response.raise_for_status()
        payload = response.json()
        self._token = payload["access_token"]
        self._token_expires_at = time.time() + payload.get("expires_in", 1800)
        return self._token

    def _load_creds(self):
        """Load Credentials to get token"""
        try:
            with open(PATH_TO_CREDS) as f:
                credentials = json.load(f)
                self._client_id = credentials["clientId"]
                self._client_secret = credentials["clientSecret"]
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Credentials file not found at {PATH_TO_CREDS}. "
                "Copy credentials.example.json and fill in your OpenSky client id/secret."
            )
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Credentials file at {PATH_TO_CREDS} is not valid JSON: {e}"
            )

    def get_states(self):
        """Fetches from /states/all"""
        params = {
            "lamin": self.lamin,
            "lomin": self.lomin,
            "lamax": self.lamax,
            "lomax": self.lomax,
        }
        response = requests.get(
            OPENSKY_URL,
            params=params,
            headers={"Authorization": f"Bearer {self._get_token()}"},
        )
        response.raise_for_status()
        return response.json()


if __name__ == "__main__":
    ah = ApiHandler()
    print(ah.get_states())

