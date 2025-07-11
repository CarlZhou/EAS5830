# 0xc8622c24

from web3 import Web3
from web3.middleware import proof_of_authority
import json

# Connect to Avalanche Fuji Testnet RPC node
w3 = Web3(Web3.HTTPProvider('https://api.avax-test.network/ext/bc/C/rpc'))

# Add Avalanche PoA middleware (correct middleware name)
w3.middleware_onion.inject(proof_of_authority, layer=0)

# Verify connection
assert w3.is_connected(), "Connection failed to Avalanche Fuji Testnet."

# Load contract ABI (Replace 'abi.json' with your actual ABI file)
with open("NFT.abi", "r") as abi_file:
    abi = json.load(abi_file)

contract_address = Web3.to_checksum_address("0x85ac2e065d4526FBeE6a2253389669a12318A412")
contract = w3.eth.contract(address=contract_address, abi=abi)

private_key = "995924619c455b72a9d201a83067a634e8124f080747f3bea2aeeef0e686b6b9"
account = w3.eth.account.from_key(private_key)
address = account.address

from eth_utils import keccak
from web3 import Web3

nonce = Web3.to_bytes(text="test")
# max_id = contract.functions.maxId().call()
token_id_claimed = int.from_bytes(keccak(nonce), "big") % 0xc8622c24

print("Token ID claimed:", token_id_claimed)

2082956656