from web_panel import app
from web_panel.models import db, Server, ServerLogEntry
import subprocess, atexit

servers = {}

#
#
# UPDATE FUNCTIONS
#    Called from callbacks, ie: timer or program exit.
#
#

def on_exit():
	print("minetest.on_exit() : Shutting down...")

	for _, server in servers.iteritems():
		server.kill()


atexit.register(on_exit)

def check_processes():
	print("Checking servers!")
	for key in servers.keys():
		value = servers[key]
		print("Checking " + key)
		if value.check():
			print("- ok!")
		else:
			print("- exited!")
			if value.retval != 0:
				server = Server.query.filter_by(id=value.id).first()
				if server:
					db.session.add(ServerLogEntry(server, "error",
							"Server Crashed!", value.getEndOfLog()))
			del servers[key]
	db.session.commit()



#
#
# MINETEST PROCESS CLASS
#   Holds process data
#
#
class MinetestProcess:
	def __init__(self, id, process, port, debuglog, key):
		print("Server " + str(id) + " started!")
		self.process = process
		self.id = id
		self.retval = None
		self.port = port
		self.debuglog = debuglog
		self.chat = []
		self.key = key
		self.toserver = []

	def _push_to_chat(self, msg):
		while len(self.chat) > app.config['CHAT_BUFFER_SIZE']:
			self.chat.pop(0)
		self.chat.append(msg)

	def getEndOfLog(self, lines=None, inc_all_sessions=False):

		log_blacklist = [
			"        .__               __                   __",
			"_____ |__| ____   _____/  |_  ____   _______/  |_",
			"/     \|  |/    \_/ __ \   __\/ __ \ /  ___/\   __\\",
			"|  Y Y  \  |   |  \  ___/|  | \  ___/ \___ \  |  |",
			"|__|_|  /__|___|  /\___  >__|  \___  >____  > |__|",
			"  \/        \/     \/          \/     \/  "
		]

		# From http://tinyurl.com/36hfa5s
		total_lines_wanted = lines or app.config['DEBUG_N_LINES']
		print("Getting " + str(total_lines_wanted) + " from debug.txt")
		f = open(self.debuglog, "r")
		BLOCK_SIZE = 1024
		f.seek(0, 2)
		block_end_byte = f.tell()
		lines_to_go = total_lines_wanted
		block_number = -1
		blocks = []
		while lines_to_go > 0 and block_end_byte > 0:
			if (block_end_byte - BLOCK_SIZE > 0):
				# read the last block we haven't yet read
				f.seek(block_number*BLOCK_SIZE, 2)
				blocks.append(f.read(BLOCK_SIZE))
			else:
				# file too small, start from begining
				f.seek(0,0)
				# only read what was not read
				blocks.append(f.read(block_end_byte))
			lines_found = blocks[-1].count('\n')
			lines_to_go -= lines_found
			block_end_byte -= BLOCK_SIZE
			block_number -= 1
		all_read_text = ''.join(reversed(blocks))
		lines = all_read_text.splitlines()
		if not inc_all_sessions:
			for i, line in enumerate(reversed(lines)):
				if line.strip() == "Separator":
					lines = lines[-i+1:]
					break
		while len(lines) > 0 and lines[0].strip() == "":
			lines.pop(0)

		def is_ok(line):
			for black in log_blacklist:
				if black in line:
					return False
			return True
		lines = [line for line in lines if is_ok(line)]
		lines = '\n'.join(lines[-total_lines_wanted:])

		return lines

	def check(self):
		if self.process is None:
			return False
		retval = self.process.poll()
		if retval is None:
			return True

		self.process = None
		self.retval = retval
		print("Process stopped with " + str(retval))
		return False

	def kill(self):
		print("Killing " + str(self.id))
		self.process.terminate()

	def stop(self, username):
		self.send({
			"mode": "cmd_sudo",
			"username": username,
			"content": "shutdown"
		})

	def send(self, tosend):
		self.toserver.append(tosend)

	# Runs minetest.chat_send_all() on server
	def send_chat(self, msg):
		self.send({
			"mode": "chat",
			"content": msg
		})

	# Runs command on server
	def send_cmd(self, username, cmd):
		self.send({
			"mode": "cmd",
			"username": username,
			"content": msg
		})

	# Runs cmd if starts with / else chat message
	def send_chat_or_cmd(self, username, msg):
		self.send({
			"mode": "chat_or_cmd",
			"username": username,
			"content": msg
		})



#
#
# API FUNCTIONS
#    Called by views etc
#
#

def start(server):
	try:
		mt = servers["sid_" + str(server.id)]
		return False
	except KeyError:
		# Build Parameters
		debuglog = server.getDebugLogPath()
		params = [app.config['MINETEST_EXE']]
		additional_params = app.config['MINETEST_EXE_PARAMS'] or []
		for param in additional_params:
			params.append(param)
		params.append("--world")
		params.append(server.getWorldPath())
		params.append("--logfile")
		params.append(debuglog)
		params.append("--port")
		params.append(str(server.port))

		# Create directories in debug path
		import os
		if not os.path.exists(os.path.dirname(debuglog)):
			os.makedirs(os.path.dirname(debuglog))

		# Debug: Print Parameters
		outval = ""
		for param in params:
			outval += " " + param
		print(outval.strip())

		# Write files
		import uuid
		key = uuid.uuid4().hex
		f = open(server.getWorldPath() + "/webpanel.txt", "w")
		if not f:
			print("Unable to write file!")
			return False
		f.write("return {\n\t[\"server_id\"] = \"")
		f.write(str(server.id))
		f.write("\",\n\t[\"auth_key\"] = \"")
		f.write(key)
		f.write("\",\n\t[\"webpanel_host\"] = \"http://")
		f.write(app.config['ADDRESS'])
		f.write(":")
		f.write(str(app.config['PORT']))
		f.write("\",\n\t[\"sync_interval\"] = ")
		f.write(str(app.config['HTTP_SYNC_INTERVAL']))
		f.write(",\n\t[\"sync_timeout\"] = ")
		f.write(str(app.config['HTTP_SYNC_TIMEOUT']))
		f.write("\n}\n")
		f.close()

		# Copy mods
		import shutil
		worldmods = server.getWorldPath() + "/worldmods/"
		if not os.path.exists(worldmods):
			os.makedirs(worldmods)
		if os.path.exists(worldmods + "mwcp/"):
			shutil.rmtree(worldmods + "mwcp/")
		shutil.copytree(os.path.abspath(os.path.dirname(__file__) + "/../mods/mwcp/"), worldmods + "mwcp/")

		# Start Process
		log = open('/tmp/blah.txt', 'a')
		proc = subprocess.Popen(params)
		servers["sid_" + str(server.id)] = MinetestProcess(server.id, proc,\
				server.port, debuglog, key)
		server.is_on = True
		db.session.commit()
		return proc.poll() is None

def stop(server, username):
	try:
		mt = servers["sid_" + str(server.id)]

		if mt and mt.check():
			mt.stop(username)

	except KeyError:
		pass

def kill(server):
	try:
		mt = servers["sid_" + str(server.id)]

		if mt and mt.check():
			mt.kill()
			server.is_on = False
			db.session.commit()

		del servers["sid_" + str(server.id)]
	except KeyError:
		pass

def socket_is_up(address, port):
	import sys, time, socket

	try:
		start = time.time()
		sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		sock.settimeout(0.5)
		buf = "\x4f\x45\x74\x03\x00\x00\x00\x01"
		sock.sendto(buf, (address, port))
		data, addr = sock.recvfrom(1000)
		if data:
			peer_id = data[12:14]
			buf = "\x4f\x45\x74\x03" + peer_id + "\x00\x00\x03"
			sock.sendto(buf, (address, port))
			sock.close()
			end = time.time()
			return True
		else:
			return False
	except:
		return False

def status(server):
	check_processes()

	try:
		mt = servers["sid_" + str(server.id)]

		if mt and mt.check():
			is_up = socket_is_up("localhost", mt.port)
			if is_up:
				if mt.port != server.port:
					return "restart-required"
				else:
					return "on"
			else:
				return "no-connect"
	except KeyError:
		pass


	is_up = socket_is_up("localhost", server.port)

	if is_up:
		return "blocked"
	else:
		return "off"

def get_chat(server):
	try:
		mt = servers["sid_" + str(server.id)]
		return mt.chat
	except KeyError:
		return []

def get_log(server, lines, inc_all_sessions):
	try:
		mt = servers["sid_" + str(server.id)]
		return mt.getEndOfLog(lines, inc_all_sessions)
	except KeyError:
		return None

def send_chat_or_cmd(server, player, msg):
	check_processes()

	try:
		mt = servers["sid_" + str(server.id)]

		if mt and mt.check():
			print(player + " sends to " + server.name  + " " + msg)
			mt.send_chat_or_cmd(player, msg)
	except KeyError:
		pass

def flush(server, key):
	check_processes()

	try:
		mt = servers["sid_" + str(server.id)]

		if mt and mt.check():
			if mt.key != key:
				return "auth"

			retval = mt.toserver
			mt.toserver = []
			return retval
	except KeyError:
		return "offline"
