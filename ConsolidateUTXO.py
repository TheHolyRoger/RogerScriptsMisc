# This script is written in Python3.5+
import sys, time, socket, copy, os
from decimal import Decimal
Dec = Decimal
try:
	from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException
except:
	print("This script requires the python-bitcoinrpc library available at: https://github.com/jgarzik/python-bitcoinrpc")
	quit()

def PrintHelp():
	print("\r\n\r\n\r\nConsolidateUTXO.py <FROM_ADDRESS> <TO_ADDRESS> ... --options")
	print("(FROM_ADDRESS can be a comma separated list)\r\n")
	print("Options:")
	print("    --rpc-config          Path to coinrpc_config.py file containing rpc_config dict. Sample file here:")
	print("                          https://github.com/TheHolyRoger/RogerScriptsMisc/blob/master/coinrpc_config.sample.py\r\n")
	print("    --dry-run             Don't send transactions\r\n")
	print("    --max-tx-count X      Change Max inputs for each TX to X (Default: 555)\r\n\r\n\r\n")
	quit()
	sys.exit(0)

if len(sys.argv) < 3:
	PrintHelp()

# Set default vars.
PAUSE_BEFORE_SEND = 5
FakeRun = False
FeePerKByte = Dec("0.001")
MinFeePerKByte = copy.deepcopy(FeePerKByte)
maxTXCount = 555
txMaxSendCount = 600
minConf = 100
maxConf = 99999999
path_rpc_config = './coinrpc_config.py'
# Split FROM_ADDRESS
if "," in sys.argv[1]:
	sendFromAddressList = sys.argv[1].split(',')
else:
	sendFromAddressList = [sys.argv[1]]
sendToAddress = sys.argv[2]
# Get and set extra parameters
for x in range(len(sys.argv)):
	if sys.argv[x] == '--help' or sys.argv[x] == '-h':
		PrintHelp()
		break
	if sys.argv[x] == '--dry-run':
		FakeRun = True
	if sys.argv[x] == '--max-tx-count':
		maxTXCount = int(sys.argv[x+1])
		print("Max inputs set to: %s\r\n" % (maxTXCount,))
	if sys.argv[x] == '--rpc-config':
		path_rpc_config = os.path.abspath(str(sys.argv[x+1]))
		print("\r\nRPC Config file set to: %s\r\n" % (path_rpc_config,))
# Check for RPC config file and load if there is one.
if os.path.exists(path_rpc_config):
	try:
		import importlib.util
		coinrpc_config_spec = importlib.util.spec_from_file_location("coinrpc_config", path_rpc_config)
		coinrpc_config = importlib.util.module_from_spec(coinrpc_config_spec)
		coinrpc_config_spec.loader.exec_module(coinrpc_config)
		rpc_config = coinrpc_config.rpc_config
	except:
		print("Error importing coinrpc_config.py")
		quit()
# If not RPC config file fallback to coinrpc_readconfig helper
# rpcuser and rpcpassword are read from the *coin.conf file
else:
	try:
		import coinrpc_readconfig
		rpc_config = coinrpc_readconfig.get_rpc_connection_info(coin_name="the holy roger", rpc_host = '127.0.0.1', rpc_port = 9662)
	except:
		print("This script requires the coinrpc_readconfig helper available at: https://github.com/TheHolyRoger/RogerScriptsMisc/blob/master/coinrpc_readconfig.py")
		quit()
if FakeRun is True:
	print('\r\nDRY RUN\r\n')

# Daemon Connection
def rpc_connection():
	return AuthServiceProxy(
		"http://%s:%s@%s:%s"%(rpc_config['rpc_user'], rpc_config['rpc_password'], rpc_config['rpc_host'], rpc_config['rpc_port']),
		timeout=320)

class OutgoingTransaction:
	dummy_unsigned_hex = None
	dummy_unsigned_size = None
	dummy_unsigned_length = None
	utxo_list = None
	tx_fee = None
	unsigned_hex = None
	signed_hex = None
	unsigned_tx = None
	def __init__(self, utxo_list=None, receive_addresses=[]):
		self.create_dummy(utxo_list=utxo_list, receive_addresses=receive_addresses)
		self.utxo_list = utxo_list
	def create_dummy(self, utxo_list, receive_addresses):
		# Create dummy TX first to estimate fee from size
		self.dummy_unsigned_hex = rpc_connection().createrawtransaction(utxo_list, receive_addresses)
		# Size as reported by RPC just in case it differs
		self.dummy_unsigned_size = rpc_connection().decoderawtransaction(self.dummy_unsigned_hex)["size"]
		# Get size in bytes
		self.dummy_unsigned_length = Dec(str(len(self.dummy_unsigned_hex)/2))
	def calculate_txfee(self, FeePerKByte):
		# Calc tx fee and receive amount from size
		self.tx_fee = Dec(str(FeePerKByte))*(self.dummy_unsigned_length/Dec("1000"))
	def create_tx(self, receive_addresses):
		# Now create the real TX
		self.unsigned_hex = rpc_connection().createrawtransaction(self.utxo_list, receive_addresses)
		# Sign it
		self.signed_hex = rpc_connection().signrawtransaction(self.unsigned_hex)
		# Decode unsigned to check value and ID
		self.unsigned_tx = rpc_connection().decoderawtransaction(self.unsigned_hex)

# Build TX logic
def BuildTX(utxo_list, receive_address, send_amount):
	TheTX = OutgoingTransaction(utxo_list=utxo_list, receive_addresses={receive_address: str(send_amount)})
	TheTX.calculate_txfee(FeePerKByte)
	receive_amount = "{:.8f}".format(send_amount - Dec(TheTX.tx_fee))
	# Wut u up to?
	print("Receiving: %s (%s fee deducted)\r\n" % (receive_amount, TheTX.tx_fee))
	print("Building and Signing TX...")
	TheTX.create_tx(receive_addresses={receive_address: str(receive_amount)})
	print("Unsigned TX ID: %s , Total: %s, Dummy size: %s, Hex Size: %s, Calc TX Fee: %s\r\n" % (
		TheTX.unsigned_tx["hash"], TheTX.unsigned_tx["vout"][0]["value"], TheTX.dummy_unsigned_size, TheTX.dummy_unsigned_length, TheTX.tx_fee))
	return TheTX.signed_hex["hex"]

# Init Vars
toSpend = []
txCount = 0
txSentCount = 0
sendTXs = []
totalToSend = Dec('0')
print('')

# Grab all UTXOs in wallet
try:
	unspent=rpc_connection().listunspent(minConf,maxConf)
except:
	print("Unable to connect to daemon, quitting.")
	quit()

# Try and get estimated fee
try:
	FeePerKByte=rpc_connection().estimatesmartfee(minConf)["feerate"]
	print("Estimated Fee per KB: %s\r\n" % (FeePerKByte))
except:
	try:
		FeePerKByte=rpc_connection().estimaterawfee(minConf)["long"]["feerate"]
		print("Estimated Fee per KB: %s\r\n" % (FeePerKByte))
	except:
		FeePerKByte=MinFeePerKByte
		print("Unable to estimate fee.\r\n")

# Grab UTXOs for source addresses
for theTx in unspent:
	if theTx['address'] in sendFromAddressList:
		toSpend.append(theTx)
# Set counters
toSpendCount = len(toSpend)
unspentCount = len(unspent)
# Delete full UTXO list
del unspent


# Ready to go
print("%i TXs found in address of %i transactions available." % (toSpendCount,unspentCount))
for theTx in toSpend:
	# If below max tx count for batch, add to batch.
	if txCount < maxTXCount:
		sendTXs.append({"txid": theTx['txid'], "vout": theTx['vout']})
		totalToSend += Dec(theTx['amount'])
		txCount += 1
	# If at max tx count for batch, start sending.
	if (txCount >= maxTXCount) or (txCount >= toSpendCount): 
		print("Sending From: %s  To: %s (%s)" % (sendFromAddressList, sendToAddress, totalToSend))
		SignedTX_hex = BuildTX(sendTXs, sendToAddress, totalToSend)
		print("Ready to send? (ctrl+c to cancel)\n")
		# You can quit the script here before "Sending" appears to exit without sending anything
		time.sleep(PAUSE_BEFORE_SEND)
		print("Sending...")
		if FakeRun is not True:
			txhash = rpc_connection().sendrawtransaction(SignedTX_hex)
		else:
			txhash = "DRY RUN, NOT SENT"
		# except socket.timeout:
		# 	txhash = "TIMEDOUT"
		print("TX Hash: %s\r\n\r\n\r\n" % (txhash,))
		# Increment TX counters
		toSpendCount -= txCount
		unspentCount -= txCount
		txSentCount += 1
		# Reset batch counters
		txCount = 0
		sendTXs = []
		totalToSend = Dec('0')
		# Onto the next batch
		if txSentCount < txMaxSendCount:
			print("%i TXs found in address of %i transactions available." % (toSpendCount,unspentCount))
		# Finished UTXOs in this address
		else:
			print("Max number of transactions hit.")
			break

if len(sendTXs) < 1:
	print("No Unspent TXs Found")
	quit()

