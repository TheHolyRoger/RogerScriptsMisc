# This script is written in Python3.5+
import time
import copy
import os
import argparse
from decimal import Decimal
Dec = Decimal
try:
    from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException
except Exception:
    print("This script requires the python-bitcoinrpc library available at: "
          "https://github.com/jgarzik/python-bitcoinrpc")
    quit()


def ParseArgs():
    parser = argparse.ArgumentParser(description='ConsolidateUTXO.py')
    parser.add_argument('from_addresses',
                        help="Address(es) to send transactions FROM. (Can be comma separated)")
    parser.add_argument('to_address',
                        help="Address to send transactions TO. (single)")
    parser.add_argument('--rpc-config', dest="rpc_config",
                        help=("Path to coinrpc_config.py file containing rpc_config dict. Sample file here:"
                              "https://github.com/TheHolyRoger/RogerScriptsMisc/blob/master/coinrpc_config.sample.py"))
    parser.add_argument('--dry-run', '-n', dest="dry_run", action='store_true',
                        help="Don't send transactions.")
    parser.add_argument('--max-tx-count', '-m', dest="max_tx_count", type=int, default=555,
                        help="Change Max inputs for each TX to X (Default: 555).")
    parser.add_argument('--max-total-tx', dest="max_total_txs", type=int, default=10000,
                        help="Max amount of TXs to send in this run (Default: 10000).")
    parser.add_argument('--min-confirms', dest="min_confirms", type=int, default=100,
                        help="Minimum confirmations required for UTXOs (Default: 100).")
    parser.add_argument('--max-confirms', dest="max_confirms", type=int, default=99999999,
                        help="Maximum confirmations required for UTXOs (Default: 99999999).")
    parser.add_argument('--pause-time', dest="pause_time", type=int, default=5,
                        help="Time to pause before sending (Default: 5).")
    parser.add_argument('--wallet-passphrase', dest="wallet_passphrase", type=str,
                        help="Wallet passphrase")
    args = parser.parse_args()
    if "," in args.from_addresses:
        args.from_addresses = args.from_addresses.split(',')
    else:
        args.from_addresses = [args.from_addresses]
    return args


class OutgoingTransaction:
    dummy_unsigned_hex = None
    dummy_unsigned_size = None
    dummy_unsigned_length = None
    utxo_list = None
    tx_fee = None
    unsigned_hex = None
    signed_hex = None
    unsigned_tx = None

    def __init__(self,
                 rpc_connection,
                 utxo_list=None,
                 receive_addresses=[],
                 wallet_passphrase=None):
        self.utxo_list = utxo_list
        self.rpc_connection = rpc_connection
        self.wallet_passphrase = wallet_passphrase
        self.create_dummy(receive_addresses=receive_addresses)

    def create_dummy(self, receive_addresses):
        # Create dummy TX first to estimate fee from size
        self.dummy_unsigned_hex = self.rpc_connection().createrawtransaction(self.utxo_list, receive_addresses)
        # Size as reported by RPC just in case it differs
        self.dummy_unsigned_size = self.rpc_connection().decoderawtransaction(self.dummy_unsigned_hex)["size"]
        # Get size in bytes
        self.dummy_unsigned_length = Dec(str(len(self.dummy_unsigned_hex)/2))

    def calculate_txfee(self, FeePerKByte):
        # Calc tx fee and receive amount from size
        tx_size = self.dummy_unsigned_length+Dec("120")
        self.tx_fee = Dec(Dec(str(FeePerKByte))*(tx_size/Dec("1000")))

    def set_zero_fee(self):
        # Set zero fee
        self.tx_fee = Dec("0")

    def create_tx(self, receive_addresses):
        # Now create the real TX
        self.unsigned_hex = self.rpc_connection().createrawtransaction(self.utxo_list, receive_addresses)
        # Sign it
        try:
            self.signed_hex = self.rpc_connection().signrawtransaction(self.unsigned_hex)
        except JSONRPCException:
            self.signed_hex = self.rpc_connection().signrawtransactionwithwallet(self.unsigned_hex)
        # Decode unsigned to check value and ID
        self.unsigned_tx = self.rpc_connection().decoderawtransaction(self.unsigned_hex)


class ConsolidateUTXO:
    def __init__(self):
        # Set default vars.
        self.FakeRun = False
        self.FeePerKByte = Dec("0.001")
        self.MinFeePerKByte = copy.deepcopy(self.FeePerKByte)
        self.path_rpc_config = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'coinrpc_config.py')
        args = ParseArgs()
        self.sendFromAddressList = args.from_addresses
        self.sendToAddress = args.to_address
        self.FakeRun = args.dry_run
        self.maxTXCount = args.max_tx_count
        self.txMaxSendCount = args.max_total_txs
        self.minConf = args.min_confirms
        self.maxConf = args.max_confirms
        self.pause_time = args.pause_time
        if self.pause_time < 1:
            self.pause_time = 0.1
        self.wallet_passphrase = args.wallet_passphrase
        print("Max inputs set to: %s\r\n" % (self.maxTXCount,))
        if args.rpc_config is not None:
            self.path_rpc_config = os.path.abspath(str(args.rpc_config))
            print("\r\nRPC Config file set to: %s\r\n" % (self.path_rpc_config,))
        self.rpc_config = None
        self.check_rpc_config()
        # Init Vars
        self.unspent = []
        self.toSpend = []
        self.txCount = 0
        self.txSentCount = 0
        self.sendTXs = []
        self.signedTXList = []
        self.totalToSend = Dec('0')
        self.toSpendCount = 0
        self.unspentCount = 0

    # Daemon Connection
    def rpc_connection(self):
        return AuthServiceProxy(
            "http://%s:%s@%s:%s" % (self.rpc_config['rpc_user'],
                                    self.rpc_config['rpc_password'],
                                    self.rpc_config['rpc_host'],
                                    self.rpc_config['rpc_port']),
            timeout=320)

    def check_rpc_config(self):
        # Check for RPC config file and load if there is one.
        if os.path.exists(self.path_rpc_config):
            try:
                import importlib.util
                coinrpc_config_spec = importlib.util.spec_from_file_location("coinrpc_config", self.path_rpc_config)
                coinrpc_config = importlib.util.module_from_spec(coinrpc_config_spec)
                coinrpc_config_spec.loader.exec_module(coinrpc_config)
                self.rpc_config = coinrpc_config.rpc_config
            except Exception:
                print("Error importing coinrpc_config.py")
                quit()
        # If not RPC config file fallback to coinrpc_readconfig helper
        # rpcuser and rpcpassword are read from the *coin.conf file
        else:
            try:
                import coinrpc_readconfig
                self.rpc_config = coinrpc_readconfig.get_rpc_connection_info(coin_name="the holy roger",
                                                                             rpc_host='127.0.0.1',
                                                                             rpc_port=9662)
            except Exception:
                print("This script requires the coinrpc_readconfig helper available at: "
                      "https://github.com/TheHolyRoger/RogerScriptsMisc/blob/master/coinrpc_readconfig.py")
                quit()

    # Build TX logic
    def Build_TX(self):
        TheTX = OutgoingTransaction(rpc_connection=self.rpc_connection,
                                    utxo_list=self.sendTXs,
                                    receive_addresses={self.sendToAddress: str(self.totalToSend)})
        TheTX.calculate_txfee(self.FeePerKByte)
        receive_amount = "{:.8f}".format(self.totalToSend - Dec(TheTX.tx_fee))
        # Wut u up to?
        print("Receiving: %s (%s fee deducted)\r\n" % (receive_amount, TheTX.tx_fee))
        print("Building and Signing TX...")
        try:
            TheTX.create_tx(receive_addresses={self.sendToAddress: str(receive_amount)})
        except Exception:
            self.unlock_wallet()
            TheTX.create_tx(receive_addresses={self.sendToAddress: str(receive_amount)})
        print("Unsigned TX ID: %s , Total: %s, Dummy size: %s, Hex Size: %s, Calc TX Fee: %s\r\n" % (
            TheTX.unsigned_tx["hash"],
            TheTX.unsigned_tx["vout"][0]["value"],
            TheTX.dummy_unsigned_size,
            TheTX.dummy_unsigned_length,
            TheTX.tx_fee))
        return TheTX.signed_hex["hex"]

    def unlock_wallet(self):
        try:
            if self.wallet_passphrase:
                self.rpc_connection().walletpassphrase(self.wallet_passphrase, 900)
                return True
        except Exception:
            pass
        print("\n\n\nWALLET IS LOCKED. EXITING.\n\n\n")
        quit()

    def gather_spends(self):
        if self.FakeRun is True:
            print('\r\nDRY RUN\r\n')
        print('')

        # Grab all UTXOs in wallet
        try:
            self.unspent = self.rpc_connection().listunspent(self.minConf, self.maxConf)
        except Exception:
            print("Unable to connect to daemon, quitting.")
            quit()

        # Try and get estimated fee
        try:
            self.FeePerKByte = self.rpc_connection().estimatesmartfee(self.minConf)["feerate"]
            print("Estimated Fee per KB: %s\r\n" % (self.FeePerKByte))
        except Exception:
            try:
                self.FeePerKByte = self.rpc_connection().estimaterawfee(self.minConf)["long"]["feerate"]
                print("Estimated Fee per KB: %s\r\n" % (self.FeePerKByte))
            except Exception:
                self.FeePerKByte = self.MinFeePerKByte
                print("Unable to estimate fee.\r\n")

        # Grab UTXOs for source addresses
        for theTx in self.unspent:
            if theTx['address'] in self.sendFromAddressList:
                self.toSpend.append(theTx)
        # Set counters
        self.toSpendCount = len(self.toSpend)
        self.unspentCount = len(self.unspent)
        # Delete full UTXO list
        self.unspent = []

    def main_run(self):
        self.gather_spends()

        # Ready to go
        print("%i TXs found in address of %i transactions available." % (self.toSpendCount, self.unspentCount))
        for theTx in self.toSpend:
            # If below max tx count for batch, add to batch.
            if self.txCount < self.maxTXCount:
                self.sendTXs.append({"txid": theTx['txid'], "vout": theTx['vout']})
                self.totalToSend += Dec(theTx['amount'])
                self.txCount += 1
            # If at max tx count for batch, start sending.
            if (self.txCount >= self.maxTXCount) or (self.txCount >= self.toSpendCount):
                print("Sending From: %s  To: %s (%s)" % (self.sendFromAddressList, self.sendToAddress, self.totalToSend))
                SignedTX_hex = self.Build_TX()
                print("Ready to send? (ctrl+c to cancel)\n")
                # You can quit the script here before "Sending" appears to exit without sending anything
                time.sleep(self.pause_time)
                print("Sending...")
                if self.FakeRun is not True:
                    txhash = self.rpc_connection().sendrawtransaction(SignedTX_hex)
                else:
                    txhash = "DRY RUN, NOT SENT"
                # except socket.timeout:
                #   txhash = "TIMEDOUT"
                print("TX Hash: %s\r\n\r\n\r\n" % (txhash,))
                # Increment TX counters
                self.toSpendCount -= self.txCount
                self.unspentCount -= self.txCount
                self.txSentCount += 1
                # Reset batch counters
                self.txCount = 0
                self.sendTXs = []
                self.totalToSend = Dec('0')
                # Onto the next batch
                if self.txSentCount < self.txMaxSendCount:
                    print("%i TXs found in address of %i transactions available." % (self.toSpendCount, self.unspentCount))
                # Finished UTXOs in this address
                else:
                    print("Max number of transactions hit.")
                    break

        if len(self.sendTXs) < 1:
            print("No Unspent TXs Found")
            quit()


if __name__ == "__main__":
    consolidator = ConsolidateUTXO()
    consolidator.main_run()
