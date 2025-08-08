from web3 import Web3
from web3.providers.rpc import HTTPProvider
from web3.middleware import ExtraDataToPOAMiddleware #Necessary for POA chains
from datetime import datetime
import json
import pandas as pd


def connect_to(chain):
    if chain == 'source':  # The source contract chain is avax
        api_url = f"https://api.avax-test.network/ext/bc/C/rpc" #AVAX C-chain testnet

    if chain == 'destination':  # The destination contract chain is bsc
        api_url = f"https://data-seed-prebsc-1-s1.binance.org:8545/" #BSC testnet

    if chain in ['source','destination']:
        w3 = Web3(Web3.HTTPProvider(api_url))
        # inject the poa compatibility middleware to the innermost layer
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    return w3


def get_contract_info(chain, contract_info):
    """
        Load the contract_info file into a dictionary
        This function is used by the autograder and will likely be useful to you
    """
    try:
        with open(contract_info, 'r')  as f:
            contracts = json.load(f)
    except Exception as e:
        print( f"Failed to read contract info\nPlease contact your instructor\n{e}" )
        return 0
    return contracts[chain]



def scan_blocks(chain, contract_info="contract_info.json"):
    """
        chain - (string) should be either "source" or "destination"
        Scan the last 5 blocks of the source and destination chains
        Look for 'Deposit' events on the source chain and 'Unwrap' events on the destination chain
        When Deposit events are found on the source chain, call the 'wrap' function the destination chain
        When Unwrap events are found on the destination chain, call the 'withdraw' function on the source chain
    """

    # This is different from Bridge IV where chain was "avax" or "bsc"
    if chain not in ['source','destination']:
        print( f"Invalid chain: {chain}" )
        return 0
    
    #YOUR CODE HERE
    # Connect to both chains
    w3_src = connect_to('source')
    w3_dst = connect_to('destination')

    # Load contract info (addresses + ABIs)
    src_info = get_contract_info('source', contract_info)
    dst_info = get_contract_info('destination', contract_info)

    if not src_info or not dst_info:
        print("Failed to load contract info")
        return 0

    cs = Web3.to_checksum_address
    src_addr = cs(src_info['address'])
    dst_addr = cs(dst_info['address'])

    src = w3_src.eth.contract(address=src_addr, abi=src_info['abi'])
    dst = w3_dst.eth.contract(address=dst_addr, abi=dst_info['abi'])

    # Read the private key
    warden_pk = None
    try:
        with open('sk.txt', 'r') as f:
            warden_pk = f.read().strip()
    except Exception as e:
        print(f"Failed to read private key: {e}")
        return 0

    # Prepare local accounts for signing
    acct_src = w3_src.eth.account.from_key(warden_pk)
    acct_dst = w3_dst.eth.account.from_key(warden_pk)

    def send_fn_tx(w3, account, fn):
        # Build a transaction for the given contract function
        base = {
            'from': account.address,
            'nonce': w3.eth.get_transaction_count(account.address),
            'value': 0
        }
        # EIP-1559 if supported, else legacy gasPrice
        try:
            latest = w3.eth.get_block('latest')
            base_fee = latest.get('baseFeePerGas', None)
            if base_fee is not None:
                max_priority = w3.to_wei(2, 'gwei')
                base['maxPriorityFeePerGas'] = max_priority
                base['maxFeePerGas'] = int(base_fee + max_priority * 2)
            else:
                base['gasPrice'] = w3.eth.gas_price
        except Exception:
            base['gasPrice'] = w3.eth.gas_price

        # Estimate gas (fallback if estimation fails)
        try:
            base['gas'] = int(fn.estimate_gas({'from': account.address}) * 1.2)
        except Exception:
            base['gas'] = 800000

        tx = fn.build_transaction(base)
        signed = w3.eth.account.sign_transaction(tx, private_key=warden_pk)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
        return receipt

    processed = 0
    if chain == 'source':
        # Look for Deposit events on the source chain
        latest = w3_src.eth.block_number
        frm = max(0, latest - 5)
        try:
            logs = src.events.Deposit().get_logs(fromBlock=frm, toBlock=latest)
        except Exception:
            logs = []
        for ev in logs:
            args = ev['args']
            token = cs(args['token'])
            recipient = cs(args['recipient'])
            amount = int(args['amount'])
            print(f"[{datetime.utcnow()}] Deposit detected on source: token={token}, to={recipient}, amount={amount}")
            # Call wrap on destination
            receipt = send_fn_tx(w3_dst, acct_dst, dst.functions.wrap(token, recipient, amount))
            print(f" -> wrap tx on destination: {receipt.transactionHash.hex()} status={receipt.status}")
            processed += 1

    elif chain == 'destination':
        # Look for Unwrap events on the destination chain
        latest = w3_dst.eth.block_number
        frm = max(0, latest - 5)
        try:
            logs = dst.events.Unwrap().get_logs(fromBlock=frm, toBlock=latest)
        except Exception:
            logs = []
        for ev in logs:
            args = ev['args']
            underlying = cs(args['underlying_token'])
            recipient = cs(args['to'])
            amount = int(args['amount'])
            print(f"[{datetime.utcnow()}] Unwrap detected on destination: underlying={underlying}, to={recipient}, amount={amount}")
            # Call withdraw on source
            receipt = send_fn_tx(w3_src, acct_src, src.functions.withdraw(underlying, recipient, amount))
            print(f" -> withdraw tx on source: {receipt.transactionHash.hex()} status={receipt.status}")
            processed += 1

    return processed
