import requests
import json

def pin_to_ipfs(data):
    assert isinstance(data, dict), "Error: pin_to_ipfs expects a dictionary"
    
    url = "https://ipfs.infura.io:5001/api/v0/cat?arg=QmPAg1mjxcEQPPtqsLoEcauVedaeMH81WXDPvPx3VC5zUz"
    json_data = json.dumps(data)
    files = {'file': ('data.json', json_data)}

    response = requests.post(url, files=files)
    response.raise_for_status()
    result = response.json()

    cid = result['Hash']
    return cid

def get_from_ipfs(cid, content_type="json"):
    assert isinstance(cid, str), "get_from_ipfs accepts a cid in the form of a string"

    url = f"https://ipfs.io/ipfs/{cid}"
    response = requests.get(url)
    response.raise_for_status()

    if content_type == "json":
        data = response.json()
    else:
        raise ValueError("Unsupported content type")

    assert isinstance(data, dict), "get_from_ipfs should return a dict"
    return data
