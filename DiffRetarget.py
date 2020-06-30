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
	print("\r\n\r\n\r\nDiffRetarget.py")
	print("Prints difficulty re-target info.\r\n")
	print("Options:")
	print("    --retarget-blocks X          X blocks before difficulty re-targets")
	print("    --rpc-config                 Path to coinrpc_config.py file containing rpc_config dict. Sample file here:")
	print("                                 https://github.com/TheHolyRoger/RogerScriptsMisc/blob/master/coinrpc_config.sample.py\r\n")
	quit()
	sys.exit(0)


# Set default vars.
DiffRetargetBlocks = 2016
path_rpc_config = './coinrpc_config.py'
# Get and set extra parameters
for x in range(len(sys.argv)):
	if sys.argv[x] == '--help' or sys.argv[x] == '-h':
		PrintHelp()
		break
	if sys.argv[x] == '--retarget-blocks':
		DiffRetargetBlocks = int(sys.argv[x+1])
		print("\r\nDifficulty re-target set to: %s\r\n" % (DiffRetargetBlocks,))
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

# Daemon Connection
def rpc_connection():
	return AuthServiceProxy(
		"http://%s:%s@%s:%s"%(rpc_config['rpc_user'], rpc_config['rpc_password'], rpc_config['rpc_host'], rpc_config['rpc_port']),
		timeout=320)


try:
	bestblock = rpc_connection().getbestblockhash()
except:
	print("Unable to connect to daemon, quitting.")
	quit()

best_blockData = rpc_connection().getblock(bestblock)

StartingDiff = best_blockData['difficulty']

CheckDiff = copy.deepcopy(StartingDiff)

CheckBlock = copy.deepcopy(best_blockData)

while CheckDiff == StartingDiff:

	prev_block = CheckBlock['previousblockhash']
	prev_blockData = rpc_connection().getblock(prev_block)

	if prev_blockData['difficulty'] != CheckDiff:
		next_retarget = int(CheckBlock['height']+DiffRetargetBlocks)
		print("\r\n\r\nCurrent Diff: %s, Last retarget @ %s, previous diff: %s, next retarget @ %s\r\n\r\n" % (CheckBlock['difficulty'], int(CheckBlock['height']), prev_blockData['difficulty'], next_retarget))
		CheckDiff = prev_blockData['difficulty']

	CheckBlock = prev_blockData


