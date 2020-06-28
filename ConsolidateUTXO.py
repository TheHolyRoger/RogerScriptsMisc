import sys, time, socket, copy
from decimal import Decimal
try:
	from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException
except:
	print("This script requires the python-bitcoinrpc library available at: https://github.com/jgarzik/python-bitcoinrpc")
	quit()
try:
	import coinrpc_readconfig
except:
	print("This script requires the coinrpc_readconfig helper available at: https://github.com/TheHolyRoger/RogerScriptsMisc/blob/master/coinrpc_readconfig.py")
	quit()
Dec = Decimal

def PrintHelp():
	print("\r\n\r\n\r\nConsolidateUTXO.py <FROM_ADDRESS> <TO_ADDRESS> ... --options")
	print("(FROM_ADDRESS can be a comma separated list)\r\n")
	print("Options:")
	print("    --dry-run             Don't send transactions")
	print("    --max-tx-count X      Change Max inputs for each TX to X (Default: 555)\r\n\r\n\r\n")
	quit()
	sys.exit(0)

if len(sys.argv) < 3:
	PrintHelp()

PAUSE_BEFORE_SEND = 5
FakeRun = False
FeePerKByte = Dec("0.001")
MinFeePerKByte = copy.deepcopy(FeePerKByte)
maxTXCount = 555
txMaxSendCount = 600
minConf = 100
maxConf = 99999999
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
if FakeRun is True:
	print('DRY RUN\r\n')

# Daemon Connection
rpc_config = coinrpc_readconfig.get_rpc_connection_info(coin_name="the holy roger", rpc_host = '127.0.0.1', rpc_port = 9662)
def rpc_connection():
	# rpc_user and rpc_password are set in the bitcoin.conf file
	return AuthServiceProxy(
		"http://%s:%s@%s:%s"%(rpc_config['rpc_user'], rpc_config['rpc_password'], rpc_config['rpc_host'], rpc_config['rpc_port']),
		timeout=320)

# Build TX logic
def BuildTX(utxo_list, receive_address, send_amount):
	# Create dummy TX first to estimate fee from size
	unsignedTX_hex = rpc_connection().createrawtransaction(utxo_list, {receive_address: str(send_amount)})
	# Size as reported by RPC just in case it differs
	dummy_unsignedTX_size = rpc_connection().decoderawtransaction(unsignedTX_hex)["size"]
	# Get size in bytes
	unsignedTX_length = Dec(str(len(unsignedTX_hex)/2))
	del unsignedTX_hex
	# Calc tx fee and receive amount from size
	tx_fee = Dec(str(FeePerKByte))*(unsignedTX_length/Dec("1000"))
	receive_amount = "{:.8f}".format(send_amount - Dec(tx_fee))
	# Wut u up to?
	print("Receiving: %s (%s fee deducted)\r\n" % (receive_amount, tx_fee))
	print("Building and Signing TX...")
	# Now create the real TX
	unsignedTX_hex = rpc_connection().createrawtransaction(utxo_list, {receive_address: str(receive_amount)})
	# Sign it
	signedTX = rpc_connection().signrawtransaction(unsignedTX_hex)
	# Decode unsigned to check value and ID
	unsignedTX = rpc_connection().decoderawtransaction(unsignedTX_hex)
	print("Unsigned TX ID: %s , Total: %s, Dummy size: %s, Hex Size: %s, Calc TX Fee: %s\r\n" % (unsignedTX["hash"], unsignedTX["vout"][0]["value"], dummy_unsignedTX_size, unsignedTX_length, tx_fee))
	return signedTX["hex"]

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

