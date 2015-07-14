
import sys, os, time
import glob, json, argparse, copy
import tempfile
import socket, webbrowser
from wsgiref.simple_server import WSGIRequestHandler, make_server
from bottle import *
from serial_manager import SerialManager
from filereaders import read_svg, read_dxf, read_ngc
from subprocess import call

APPNAME = "LaserRaptor"
VERSION = "0.0.2"
COMPANY_NAME = "com.hackerfriendly"
SERIAL_PORT = None
SMOOTHIE_PORT = "/dev/ttyACM0"
BITSPERSECOND = 115200
NETWORK_PORT = 4444
CONFIG_FILE = "lasaurapp.conf"
TOLERANCE = 0.08
GCODE_PATH = "/smoothie/"

def resources_dir():
	"""This is to be used with all relative file access.
	   _MEIPASS is a special location for data files when creating
	   standalone, single file python apps with pyInstaller.
	   Standalone is created by calling from 'other' directory:
	   python pyinstaller/pyinstaller.py --onefile app.spec
	"""
	if hasattr(sys, "_MEIPASS"):
		return sys._MEIPASS
	else:
		# root is one up from this file
		return os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../'))


def storage_dir():
	directory = ""
	if sys.platform == 'darwin':
		directory = os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', COMPANY_NAME, APPNAME)
	else:
		directory = os.path.join(os.path.expanduser('~'), "." + APPNAME)

	if not os.path.exists(directory):
		os.makedirs(directory)

	return directory


class HackedWSGIRequestHandler(WSGIRequestHandler):
	""" This is a heck to solve super slow request handling
	on the BeagleBone and RaspberryPi. The problem is WSGIRequestHandler
	which does a reverse lookup on every request calling gethostbyaddr.
	For some reason this is super slow when connected to the LAN.
	(adding the IP and name of the requester in the /etc/hosts file
	solves the problem but obviously is not practical)
	"""
	def address_string(self):
		"""Instead of calling getfqdn -> gethostbyaddr we ignore."""
		# return "(a requester)"
		return str(self.client_address[0])

	def log_request(*args, **kw):
		# if debug:
			# return wsgiref.simple_server.WSGIRequestHandler.log_request(*args, **kw)
		pass


def run_with_callback(host, port):
	""" Start a wsgiref server instance with control over the main loop.
		This is a function that I derived from the bottle.py run()
	"""
	handler = default_app()
	server = make_server(host, port, handler, handler_class=HackedWSGIRequestHandler)
	server.timeout = 0.01
	server.quiet = True
	print "Persistent storage root is: " + storage_dir()
	print "-----------------------------------------------------------------------------"
	print "Bottle server starting up ..."
	print "Serial is set to %d bps" % BITSPERSECOND
	print "Point your browser to: "
	print "http://%s:%d/      (local)" % ('127.0.0.1', port)
	print "Use Ctrl-C to quit."
	print "-----------------------------------------------------------------------------"
	print
	# auto-connect on startup
	global SERIAL_PORT
	SerialManager.connect(SERIAL_PORT, BITSPERSECOND)
	if args.browser:
		# open web-browser
		try:
			webbrowser.open_new_tab('http://127.0.0.1:'+str(port))
			pass
		except webbrowser.Error:
			print "Cannot open Webbrowser, please do so manually."
	sys.stdout.flush()  # make sure everything gets flushed
	server.timeout = 0
	while 1:
		try:
			SerialManager.process_queue()
			server.handle_request()
			time.sleep(0.0004)
		except KeyboardInterrupt:
			break
	print "\nShutting down..."
	SerialManager.close()

# @route('/longtest')
# def longtest_handler():
#     fp = open("longtest.ngc")
#     for line in fp:
#         SerialManager.queue_gcode_line(line)
#     return "Longtest queued."

@route('/css/:path#.+#')
def static_css_handler(path):
	return static_file(path, root=os.path.join(resources_dir(), 'frontend/css'))

@route('/js/:path#.+#')
def static_js_handler(path):
	return static_file(path, root=os.path.join(resources_dir(), 'frontend/js'))

@route('/img/:path#.+#')
def static_img_handler(path):
	return static_file(path, root=os.path.join(resources_dir(), 'frontend/img'))

@route('/favicon.ico')
def favicon_handler():
	return static_file('favicon.ico', root=os.path.join(resources_dir(), 'frontend/img'))


### LIBRARY

@route('/library/get/:path#.+#')
def static_library_handler(path):
	return static_file(path, root=os.path.join(resources_dir(), 'library'), mimetype='text/plain')

@route('/library/list')
def library_list_handler():
	# return a json list of file names
	file_list = []
	cwd_temp = os.getcwd()
	try:
		os.chdir(os.path.join(resources_dir(), 'library'))
		file_list = glob.glob('*')
	finally:
		os.chdir(cwd_temp)
	return json.dumps(file_list)



### QUEUE

def encode_filename(name):
	str(time.time()) + '-' + base64.urlsafe_b64encode(name)

def decode_filename(name):
	index = name.find('-')
	return base64.urlsafe_b64decode(name[index+1:])


@route('/queue/get/:name#.+#')
def static_queue_handler(name):
	return static_file(name, root=storage_dir(), mimetype='text/plain')


@route('/queue/list')
def library_list_handler():
	# return a json list of file names
	files = []
	cwd_temp = os.getcwd()
	try:
		os.chdir(storage_dir())
		files = filter(os.path.isfile, glob.glob("*"))
		files.sort(key=lambda x: os.path.getmtime(x))
	finally:
		os.chdir(cwd_temp)
	return json.dumps(files)

@route('/queue/save', method='POST')
def queue_save_handler():
	ret = '0'
	if 'job_name' in request.forms and 'job_data' in request.forms:
		name = request.forms.get('job_name')
		job_data = request.forms.get('job_data')
		filename = os.path.abspath(os.path.join(storage_dir(), name.strip('/\\')))
		if os.path.exists(filename) or os.path.exists(filename+'.starred'):
			return "file_exists"
		try:
			fp = open(filename, 'w')
			fp.write(job_data)
			print "file saved: " + filename
			ret = '1'
		finally:
			fp.close()
	else:
		print "error: save failed, invalid POST request"
	return ret

@route('/queue/rm/:name')
def queue_rm_handler(name):
	# delete queue item, on success return '1'
	ret = '0'
	filename = os.path.abspath(os.path.join(storage_dir(), name.strip('/\\')))
	if filename.startswith(storage_dir()):
		if os.path.exists(filename):
			try:
				os.remove(filename);
				print "file deleted: " + filename
				ret = '1'
			finally:
				pass
	return ret

@route('/queue/clear')
def queue_clear_handler():
	# delete all queue items, on success return '1'
	ret = '0'
	files = []
	cwd_temp = os.getcwd()
	try:
		os.chdir(storage_dir())
		files = filter(os.path.isfile, glob.glob("*"))
		files.sort(key=lambda x: os.path.getmtime(x))
	finally:
		os.chdir(cwd_temp)
	for filename in files:
		if not filename.endswith('.starred'):
			filename = os.path.join(storage_dir(), filename)
			try:
				os.remove(filename);
				print "file deleted: " + filename
				ret = '1'
			finally:
				pass
	return ret

@route('/queue/star/:name')
def queue_star_handler(name):
	ret = '0'
	filename = os.path.abspath(os.path.join(storage_dir(), name.strip('/\\')))
	if filename.startswith(storage_dir()):
		if os.path.exists(filename):
			os.rename(filename, filename + '.starred')
			ret = '1'
	return ret

@route('/queue/unstar/:name')
def queue_unstar_handler(name):
	ret = '0'
	filename = os.path.abspath(os.path.join(storage_dir(), name.strip('/\\')))
	if filename.startswith(storage_dir()):
		if os.path.exists(filename + '.starred'):
			os.rename(filename + '.starred', filename)
			ret = '1'
	return ret




@route('/')
@route('/index.html')
@route('/app.html')
def default_handler():
	return static_file('app.html', root=os.path.join(resources_dir(), 'frontend') )


@route('/stash_download', method='POST')
def stash_download():
	"""Create a download file event from string."""
	filedata = request.forms.get('filedata')
	fp = tempfile.NamedTemporaryFile(mode='w', delete=False)
	filename = fp.name
	with fp:
		fp.write(filedata)
		fp.close()
	print filedata
	print "file stashed: " + os.path.basename(filename)
	return os.path.basename(filename)

@route('/download/:filename/:dlname')
def download(filename, dlname):
	print "requesting: " + filename
	return static_file(filename, root=tempfile.gettempdir(), download=dlname)


@route('/serial/:connect')
def serial_handler(connect):
	if connect == '1':
		# print 'js is asking to connect serial'
		if not SerialManager.is_connected():
			try:
				global SERIAL_PORT, BITSPERSECOND
				SerialManager.connect(SERIAL_PORT, BITSPERSECOND)
				ret = "Serial connected to %s:%d." % (SERIAL_PORT, BITSPERSECOND)  + '<br>'
				time.sleep(1.0) # allow some time to receive a prompt/welcome
				SerialManager.flush_input()
				SerialManager.flush_output()
				return ret
			except serial.SerialException:
				SERIAL_PORT = None
				print "Failed to connect to serial."
				return ""
	elif connect == '0':
		# print 'js is asking to close serial'
		if SerialManager.is_connected():
			if SerialManager.close(): return "1"
			else: return ""
	elif connect == "2":
		# print 'js is asking if serial connected'
		if SerialManager.is_connected(): return "1"
		else: return ""
	else:
		print 'ambigious connect request from js: ' + connect
		return ""

@route('/status')
def get_status():
	status = copy.deepcopy(SerialManager.get_hardware_status())
	status['serial_connected'] = SerialManager.is_connected()
	return json.dumps(status)


@route('/pause/:flag')
def set_pause(flag):
	# returns pause status
	if flag == '1':
			# pause
			SerialManager.status['paused'] = True
			SerialManager.queue_gcode('M25')
			return '1'
	elif flag == '0':
			# resume
			SerialManager.status['paused'] = False
			SerialManager.queue_gcode('M24')
			return '0'

@route('/gcode', method='POST')
def job_submit_handler():
	job_data = request.forms.get('job_data')
	if job_data and SerialManager.is_connected():
		SerialManager.queue_gcode(job_data)
		return "__ok__"
	else:
		return "serial disconnected"

@route('/play', method='POST')
def job_play_handler():
	job_data = request.forms.get('job_data')
	if job_data and SerialManager.is_connected():
		print "going to play file here."
		try:
			with open(GCODE_PATH + "/job.gcode", "w") as f:
				f.write(job_data)
		except IOError:
			return "Could not write file {0}/job.gcode".format(GCODE_PATH)

		call("/bin/sync")

		SerialManager.queue_gcode("M32 job.gcode")
		return "__ok__"
	else:
		return "serial disconnected"


@route('/queue_pct_done')
def queue_pct_done_handler():
	return SerialManager.get_queue_percentage_done()


@route('/file_reader', method='POST')
def file_reader():
	"""Parse SVG string."""
	filename = request.forms.get('filename')
	filedata = request.forms.get('filedata')
	dimensions = request.forms.get('dimensions')
	try:
		dimensions = json.loads(dimensions)
	except TypeError:
		dimensions = None
	# print "dims", dimensions[0], ":", dimensions[1]


	dpi_forced = None
	try:
		dpi_forced = float(request.forms.get('dpi'))
	except:
		pass

	optimize = True
	try:
		optimize = bool(int(request.forms.get('optimize')))
	except:
		pass

	if filename and filedata:
		print "You uploaded %s (%d bytes)." % (filename, len(filedata))
		if filename[-4:] in ['.dxf', '.DXF']:
			res = read_dxf(filedata, TOLERANCE, optimize)
		elif filename[-4:] in ['.svg', '.SVG']:
			res = read_svg(filedata, dimensions, TOLERANCE, dpi_forced, optimize)
		elif filename[-4:] in ['.ngc', '.NGC']:
			res = read_ngc(filedata, TOLERANCE, optimize)
		else:
			print "error: unsupported file format"

		# print boundarys
		jsondata = json.dumps(res)
		# print "returning %d items as %d bytes." % (len(res['boundarys']), len(jsondata))
		return jsondata
	return "You missed a field."


### Setup Argument Parser
argparser = argparse.ArgumentParser(description='Run LaserRaptor.', prog='LaserRaptor')
argparser.add_argument('port', metavar='serial_port', nargs='?', default=False,
					help='serial port for the SmoothieBoard')
argparser.add_argument('-v', '--version', action='version', version='%(prog)s ' + VERSION)
argparser.add_argument('-p', '--public', dest='host_on_all_interfaces', action='store_true',
					default=False, help='bind to all network devices (default: bind to 127.0.0.1)')
argparser.add_argument('-l', '--list', dest='list_serial_devices', action='store_true',
					default=False, help='list all serial devices currently connected')
argparser.add_argument('-b', '--browser', action='store_true',
					default=False, help='automatically launch the app in a web browser')
argparser.add_argument('-d', '--debug', dest='debug', action='store_true',
					default=False, help='print more verbose for debugging')
args = argparser.parse_args()


print "LaserRaptor " + VERSION

if args.list_serial_devices:
	SerialManager.list_devices(BITSPERSECOND)
else:
	if args.port:
		# (1) get the serial device from the argument list
		SERIAL_PORT = args.port
		print "Using serial device '"+ SERIAL_PORT +"' from command line."
	elif os.path.exists(SMOOTHIE_PORT):
		SERIAL_PORT = SMOOTHIE_PORT

	if not SERIAL_PORT:
		print "-----------------------------------------------------------------------------"
		print "WARNING: LaserRaptor doesn't know what serial device to connect to!"
		print "Make sure the SmoothieBoard hardware is connected to the USB interface,"
		print "or specify a different port on the command line."
		print "-----------------------------------------------------------------------------"

	# run
	if args.debug:
		debug(True)
		if hasattr(sys, "_MEIPASS"):
			print "Data root is: " + sys._MEIPASS

	if args.host_on_all_interfaces:
		run_with_callback('', 80)
	else:
		run_with_callback('127.0.0.1', NETWORK_PORT)
