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
    w3_src = connect_to('avax')
    w3_dest = connect_to('bsc')

    src_contract_info = get_contract_info('source')
    src_contract = w3_src.eth.contract(address=src_contract_info['address'], abi=src_contract_info['abi'])

    dest_contract_info = get_contract_info('destination')
    dest_contract = w3_dest.eth.contract(address=dest_contract_info['address'], abi=dest_contract_info['abi'])

    w3 = w3_src if chain=='source' else w3_dest
    end_block = w3.eth.get_block_number()
    start_block = end_block - 5

    arg_filter = {}


    for block_num in range(start_block,end_block+1):
        if chain == 'source':
            event_filter = src_contract.events.Deposit.create_filter(fromBlock=start_block, \
                toBlock=end_block,argument_filters=arg_filter)
            events = event_filter.get_all_entries()
            return
            call_function('wrap', src_contract, dest_contract, events, w3_dest)
        elif chain == 'destination':
            event_filter = dest_contract.events.Unwrap.create_filter(fromBlock=start_block,  \
                toBlock=end_block,argument_filters=arg_filter)
            events = event_filter.get_all_entries()
            call_function('withdraw', src_contract, dest_contract, events, w3_src)
        
def call_function(f_name, src_contract, dest_contract, events, w3):
    warden_private_key = '0x2dba43e3a378aa051550f21be3fee843998d3e70ababd2c615a3dba3fc8c826b'
    warden_account = w3.eth.account.from_key(warden_private_key)
    gas = 500000 if f_name=='withdraw' else 5000000

    transaction_dict = {
            "from": warden_account.address,
            "nonce": w3.eth.get_transaction_count(warden_account.address),
            "gas": gas,
            "gasPrice": w3.eth.gas_price + 10000
        }
    for event in events:
        if f_name == 'wrap':
            returned = dest_contract.functions.wrap(event["args"]["token"],
                        event["args"]["recipient"],
                        event["args"]["amount"])
        elif f_name == 'withdraw':
            returned = src_contract.functions.withdraw(event["args"]["underlying_token"],
                        event["args"]["to"],
                        event["args"]["amount"])
        transaction = returned.build_transaction(transaction_dict)

        signed_tx = w3.eth.account.sign_transaction(transaction, private_key=warden_private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        w3.eth.wait_for_transaction_receipt(tx_hash)
        print("**Successfully send",f_name,"raw transaction! tx_hash:",tx_hash.hex())