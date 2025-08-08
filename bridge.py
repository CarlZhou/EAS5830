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
    w3_src = connect_to('avax')
    w3_dst = connect_to('bsc')

    # Load contract metadata (addresses + ABIs) and the warden key
    import os
    try:
        with open(contract_info, 'r') as f:
            cfg = json.load(f)
    except Exception as e:
        print(f"Failed to read {contract_info}: {e}")
        return 0

    cs = Web3.to_checksum_address

    try:
        src_meta = cfg['source']
        dst_meta = cfg['destination']
        src_addr = cs(src_meta['address'])
        dst_addr = cs(dst_meta['address'])
        src_abi  = src_meta['abi']
        dst_abi  = dst_meta['abi']
    except Exception as e:
        print(f"Bad contract_info.json format/addresses: {e}")
        return 0

    # Build contract objects
    src = w3_src.eth.contract(address=src_addr, abi=src_abi)
    dst = w3_dst.eth.contract(address=dst_addr, abi=dst_abi)

    # Warden private key (throwaway test key)
    warden_pk = "0x2dba43e3a378aa051550f21be3fee843998d3e70ababd2c615a3dba3fc8c826b"

    acct_src = w3_src.eth.account.from_key(warden_pk)
    acct_dst = w3_dst.eth.account.from_key(warden_pk)

    # Maintain nonces so multiple txs in one run don't collide
    nonces = {
        ('source', acct_src.address): w3_src.eth.get_transaction_count(acct_src.address),
        ('destination', acct_dst.address): w3_dst.eth.get_transaction_count(acct_dst.address),
    }

    def send_fn_tx(w3, account, fn, which_chain):
        """Build, sign, and send a transaction for the given contract function."""
        base = {
            'from': account.address,
            'nonce': nonces[(which_chain, account.address)],
            'value': 0,
            'chainId': w3.eth.chain_id
        }
        # Prefer EIP-1559 if baseFee exists; else legacy gasPrice
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

        # Estimate gas with a safety bump
        try:
            base['gas'] = int(fn.estimate_gas({'from': account.address}) * 1.2)
        except Exception:
            base['gas'] = 800000

        tx = fn.build_transaction(base)
        signed = w3.eth.account.sign_transaction(tx, private_key=warden_pk)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        nonces[(which_chain, account.address)] += 1
        rcpt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
        return rcpt

    processed = 0

    if chain == 'source':
        # See Deposit(token, recipient, amount) on SOURCE → call wrap() on DESTINATION
        tip = w3_src.eth.block_number
        frm = max(0, tip - 5)
        try:
            logs = src.events.Deposit().get_logs(fromBlock=frm, toBlock=tip)
        except Exception:
            logs = []
        for ev in logs:
            args = ev['args']
            token     = cs(args['token'])
            recipient = cs(args['recipient'])
            amount    = int(args['amount'])
            print(f"[{datetime.utcnow()}] Deposit on SOURCE → wrap on DEST: token={token}, to={recipient}, amount={amount}")
            try:
                rcpt = send_fn_tx(w3_dst, acct_dst, dst.functions.wrap(token, recipient, amount), 'destination')
                print(f" wrap() tx: {rcpt.transactionHash.hex()} status={rcpt.status}")
                processed += 1
            except Exception as e:
                print(f" wrap() failed: {e}")

    elif chain == 'destination':
        # See Unwrap(underlying_token, wrapped_token, frm, to, amount) on DEST → call withdraw() on SOURCE
        tip = w3_dst.eth.block_number
        frm = max(0, tip - 5)
        try:
            logs = dst.events.Unwrap().get_logs(fromBlock=frm, toBlock=tip)
        except Exception:
            logs = []
        for ev in logs:
            args = ev['args']
            underlying = cs(args['underlying_token'])
            recipient  = cs(args['to'])
            amount     = int(args['amount'])
            print(f"[{datetime.utcnow()}] Unwrap on DEST → withdraw on SRC: underlying={underlying}, to={recipient}, amount={amount}")
            try:
                rcpt = send_fn_tx(w3_src, acct_src, src.functions.withdraw(underlying, recipient, amount), 'source')
                print(f" withdraw() tx: {rcpt.transactionHash.hex()} status={rcpt.status}")
                processed += 1
            except Exception as e:
                print(f" withdraw() failed: {e}")

    return processed
