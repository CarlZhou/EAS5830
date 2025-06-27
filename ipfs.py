import requests
import json

def pin_to_ipfs(data):
    assert isinstance(data, dict), "Error: pin_to_ipfs expects a dictionary"

    url = "https://api.pinata.cloud/pinning/pinJSONToIPFS"
    headers = {
        "Content-Type": "application/json",
        "pinata_api_key": "fc02ada113178410dcb6",
        "pinata_secret_api_key": "fe23c605031bde02214a7f032870700f6f60dc345784bddad5b9ae44e03fbbfa"
    }

    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    result = response.json()

    cid = result['IpfsHash']
    return cid

def get_from_ipfs(cid, content_type="json"):
    assert isinstance(cid, str), "get_from_ipfs accepts a cid in the form of a string"

    url = f"https://gateway.pinata.cloud/ipfs/{cid}"
    response = requests.get(url)
    response.raise_for_status()

    if content_type == "json":
        data = response.json()
    else:
        raise ValueError("Unsupported content type")

    assert isinstance(data, dict), "get_from_ipfs should return a dict"
    return data
