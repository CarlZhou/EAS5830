from web3 import Web3

# Initialize Web3 (no provider needed just for local key management)
w3 = Web3()

# Create a new random account
account = w3.eth.account.create()

print("New address:", account.address)
print("Private key (hex):", account.key.hex())

# — optionally save the key for later use —
with open("secret_key.txt", "w") as f:
    # store with 0x-prefix so our signer code picks it up straight
    f.write(account.key.hex())