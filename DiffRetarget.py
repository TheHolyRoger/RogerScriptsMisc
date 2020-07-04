# This script is written in Python3.5+
import sys, time, socket, copy, os
from decimal import Decimal
from datetime import datetime
Dec = Decimal
try:
	from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException
except:
	print("This script requires the python-bitcoinrpc library available at: https://github.com/jgarzik/python-bitcoinrpc")
	quit()

try:
	import Notifiers
except:
	print("Unable to import notifiers.")
	pass

def PrintHelp():
	print("\r\n\r\n\r\nDiffRetarget.py")
	print("Prints difficulty re-target info.\r\n")
	print("Options:")
	print("    --retarget-blocks X          X blocks before difficulty re-targets")
	print("    --block-time X               X minutes between blocks")
	print("    --rpc-config                 Path to coinrpc_config.py file containing rpc_config dict. Sample file here:")
	print("                                 https://github.com/TheHolyRoger/RogerScriptsMisc/blob/master/coinrpc_config.sample.py\r\n")
	quit()
	sys.exit(0)


# Set default vars.
DiffRetargetBlocks = 2016
BlockTime = "2.5"
path_rpc_config = './coinrpc_config.py'
# Get and set extra parameters
for x in range(len(sys.argv)):
	if sys.argv[x] == '--help' or sys.argv[x] == '-h':
		PrintHelp()
		break
	if sys.argv[x] == '--retarget-blocks':
		DiffRetargetBlocks = int(sys.argv[x+1])
		print("\r\nDifficulty re-target set to: %s\r\n" % (DiffRetargetBlocks,))
	if sys.argv[x] == '--block-time':
		BlockTime = str(sys.argv[x+1])
		print("\r\nBlock Time set to: %s\r\n" % (BlockTime,))
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

def display_time(seconds):
	granularity=2
	intervals = (
		('weeks', 604800),  # 60 * 60 * 24 * 7
		('days', 86400),    # 60 * 60 * 24
		('hrs', 3600),    # 60 * 60
		('mins', 60),
		('secs', 1),
		)
	result = []
	for name, count in intervals:
		value = seconds // count
		if value:
			seconds -= value * count
			if value == 1:
				name = name.rstrip('s')
			result.append("{} {}".format(value, name))
	return ', '.join(result[:granularity])


try:
	bestblock = rpc_connection().getbestblockhash()
except:
	print("Unable to connect to daemon, quitting.")
	quit()

best_blockData = rpc_connection().getblock(bestblock)
best_block_height = best_blockData['height']

StartingDiff = best_blockData['difficulty']

CheckDiff = copy.deepcopy(StartingDiff)

CheckBlock = copy.deepcopy(best_blockData)

# For estimated time calc:
# minutes between blocks = diff * 2**32 / nethashrate / 60

while CheckDiff == StartingDiff:

	prev_block = CheckBlock['previousblockhash']
	prev_blockData = rpc_connection().getblock(prev_block)

	if prev_blockData['difficulty'] != CheckDiff:
		next_retarget = int(CheckBlock['height']+DiffRetargetBlocks)
		hashrate = Dec(str(rpc_connection().getnetworkhashps()))
		cur_diff = Dec(str(CheckBlock['difficulty']))
		time_between_blocks_secs = (cur_diff * Dec("2")**Dec("32")) / hashrate
		time_to_next_diff = (next_retarget - best_block_height) * time_between_blocks_secs
		time_to_next_diff_str = display_time(time_to_next_diff)
		date_next_diff = int(time.time()) + time_to_next_diff
		date_next_diff_str = datetime.utcfromtimestamp(date_next_diff).strftime("%-d %b '%y %H:%M:%S")
		timewindow_curdiff = date_next_diff - prev_blockData['time']
		timewindow_expected = Dec(str(BlockTime))*Dec("60")*Dec(str(DiffRetargetBlocks))
		percent_change = ((timewindow_expected - timewindow_curdiff)/timewindow_curdiff)*100
		msg = "Current Diff: %.2f @ %s, Previous re-target @ %s, Previous diff: %.2f, Next re-target @ %s (Estimated in %s @ %s, up to %.1f%% change)" % (cur_diff, best_block_height, int(CheckBlock['height']), prev_blockData['difficulty'], next_retarget, time_to_next_diff_str, date_next_diff_str, percent_change)
		if 'Notifiers' in sys.modules:
			pass
			Notifiers.NotifyDiscord('RogerDiff', msg)
		print("\r\n\r\n%s\r\n\r\n" % (msg))
		CheckDiff = prev_blockData['difficulty']

	CheckBlock = prev_blockData


