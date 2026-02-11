import http.client
import urllib.request
import urllib.parse
import hashlib
import hmac
import base64
import json
import time


class KrakenService:
    def get_nonce() -> str:
        return str(int(time.time() * 1000))

    def get_signature(self, private_key: str, data: str, nonce: str, path: str) -> str:
        return self.sign(
            private_key=private_key,
            message=path.encode() + hashlib.sha256((nonce + data).encode()).digest(),
        )

    def sign(self, private_key: str, message: bytes) -> str:
        return base64.b64encode(
            hmac.new(
                key=base64.b64decode(private_key),
                msg=message,
                digestmod=hashlib.sha512,
            ).digest()
        ).decode()

    def request(
        self,
        method: str = "GET",
        path: str = "",
        query: dict | None = None,
        body: dict | None = None,
        public_key: str = "",
        private_key: str = "",
        environment: str = "",
    ) -> http.client.HTTPResponse:
        url = environment + path
        query_str = ""
        if query is not None and len(query) > 0:
            query_str = urllib.parse.urlencode(query)
            url += "?" + query_str
        nonce = ""
        if len(public_key) > 0:
            if body is None:
                body = {}
            nonce = body.get("nonce")
            if nonce is None:
                nonce = self.get_nonce()
                body["nonce"] = nonce
        headers = {}
        body_str = ""
        if body is not None and len(body) > 0:
            body_str = json.dumps(body)
            headers["Content-Type"] = "application/json"
        if len(public_key) > 0:
            headers["API-Key"] = public_key
            headers["API-Sign"] = self.get_signature(private_key, query_str + body_str, nonce, path)
        req = urllib.request.Request(
            method=method,
            url=url,
            data=body_str.encode(),
            headers=headers,
        )
        return urllib.request.urlopen(req)

    def get_asset_pairs(self):
        response = self.request(
            method="GET",
            path="/0/public/AssetPairs",
            environment="https://api.kraken.com",
        )
        data = response.read()
        return json.loads(data)


class ApiService:
    FG_URL = "https://api.alternative.me/fng/?limit=1"

    def get_fear_and_greed_index(self) -> dict:
        try:
            with urllib.request.urlopen(self.FG_URL) as response:
                if response.status != 200:
                    return {"error": f"Failed to fetch data, status code: {response.status}"}
                data = response.read()
                json_data = json.loads(data)
                value = json_data["data"][0]
                return value
        except Exception as e:
            return {"error": str(e)}
