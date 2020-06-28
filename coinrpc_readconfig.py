# Helper functions to get coin rpc connection info from coin's .conf file
# 
# The 'coin_name' variable will capitalise and lowercase as required for each path.
# When given coin_name="the holy roger" it will use "TheHolyRoger" and "theholyroger" as required in paths
# e.g.
# coin_name="bit coin" would become "BitCoin" and "bitcoin" - whereas coin_name="bitcoin" would simply be "Bitcoin" and "bitcoin"
# 
# For example usage see https://github.com/TheHolyRoger/RogerScriptsMisc/blob/master/ConsolidateUTXO.py#L55


def read_config_file(filename):
	"""
	Read a simple ``'='``-delimited config file.
	Raises :const:`IOError` if unable to open file, or :const:`ValueError`
	if an parse error occurs.
	"""
	f = open(filename)
	try:
		cfg = {}
		for line in f:
			line = line.strip()
			if line and not line.startswith("#"):
				try:
					(key, value) = line.split('=', 1)
					cfg[key] = value
				except ValueError:
					pass  # Happens when line has no '=', ignore
	finally:
		f.close()
	return cfg


def read_default_config(coin_name="the holy roger", filename=None):
	"""
	Read coin default configuration from the current user's home directory.

	Arguments:

	- `coin_name`: The coin name to use for automatic path. See comments in script.
	- `filename`: Path to a configuration file in a non-standard location (optional)
	"""

	import string
	coin_name_slug = coin_name.lower().replace(" ","")
	coin_name_pretty = string.capwords(coin_name).replace(" ","")

	if filename is None:
		import os
		import platform
		home = os.getenv("HOME")
		if not home:
			raise IOError("Home directory not defined, don't know where to look for config file")

		if platform.system() == "Darwin":
			location = "Library/Application Support/%s/%s.conf" % (coin_name_pretty, coin_name_slug)
		else:
			location = ".%s/%s.conf" % (coin_name_slug, coin_name_slug)
		filename = os.path.join(home, location)

	elif filename.startswith("~"):
		import os
		filename = os.path.expanduser(filename)

	try:
		return read_config_file(filename)
	except (IOError, ValueError):
		pass  # Cannot read config file, ignore

def get_rpc_connection_info(coin_name = None, rpc_host = None, rpc_port = None):
	"""
	Read coin default configuration and return RPC connection info

	Arguments:

	- `coin_name`: The coin name to use for automatic path. See comments in script.
	- `rpc_host`: RPC Hostname/IP if not in .conf file (optional)
	- `rpc_port`: RPC Port if not in .conf file (optional)
	"""
	rpc_config = {
		'rpc_user': 'user',
		'rpc_password': 'pass',
		'rpc_host': rpc_host if rpc_host is not None else '127.0.0.1',
		'rpc_port': rpc_port if rpc_port is not None else 9662
	}
	if coin_name is not None:
		readconfig = read_default_config(coin_name=coin_name)
	else:
		readconfig = read_default_config()
	if readconfig is not None:
		if 'rpcuser' in list(readconfig.keys()):
			rpc_config['rpc_user'] = readconfig['rpcuser']
		if 'rpcpassword' in list(readconfig.keys()):
			rpc_config['rpc_password'] = readconfig['rpcpassword']
		if 'rpcport' in list(readconfig.keys()) and rpc_port is None:
			rpc_config['rpc_port'] = readconfig['rpcport']
		if 'rpchost' in list(readconfig.keys()) and rpc_host is None:
			rpc_config['rpc_host'] = readconfig['rpchost']
	else:
		return "Unable to find config file."
	return rpc_config
