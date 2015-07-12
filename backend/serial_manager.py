
import os
import re
import sys
import time
import serial
from collections import deque


class SerialManagerClass:

	def __init__(self):
		self.device = None

		self.remoteXON = True

		self.tx_queue = []

		# used for calculating percentage done
		self.job_active = False

		# status flags
		self.status = {}
		self.reset_status()

		self.fec_redundancy = 0  # use forward error correction
		# self.fec_redundancy = 1  # use error detection

	def reset_status(self):
		self.status = {
			'ready': False,  # ready after 'ok'
			'paused': False,  # this is also a control flag
			'limit_hit': False,
			'current_position': "",
			'door_open': False,
			'chiller_off': False,
			'x': False,
			'y': False,
			'firmware_version': None
		}


	def connect(self, port, baudrate):
		self.tx_queue = []
		self.remoteXON = True
		self.reset_status()

		self.device = serial.Serial(port, baudrate, timeout=1, writeTimeout=1)


	def close(self):
		if self.device:
			try:
				self.device.flushOutput()
				self.device.flushInput()
				self.device.close()
				self.device = None
			except:
				self.device = None
			return True
		else:
			return False

	def is_connected(self):
		return bool(self.device)

	def get_hardware_status(self):
		# if self.is_queue_empty():
		# 	# trigger a status report
		# 	# will update for the next status request
		# 	self.queue_gcode('?')
		self.queue_gcode('M114')
		return self.status


	def flush_input(self):
		if self.device:
			self.device.flushInput()

	def flush_output(self):
		if self.device:
			self.device.flushOutput()


	def queue_gcode(self, gcode):
		lines = gcode.split('\n')
		# print "Adding to queue:"
		# print lines
		for line in lines:
			line = line.strip()
			if line == '' or line[0] == '%':
				continue
			self.tx_queue.append(line)

		self.job_active = True


	def cancel_queue(self):
		self.tx_queue = []
		self.job_active = False
		self.status['ready'] = False


	def is_queue_empty(self):
		return len(self.tx_queue) == 0


	def get_queue_percentage_done(self):
		return "50"
		# buflen = len(self.tx_buffer)
		# if buflen == 0:
		# 	return ""
		# return str(100*self.tx_index/float(buflen))


	def set_pause(self, flag):
		# returns pause status
		if self.is_queue_empty():
			return False
		else:
			if flag:  # pause
				self.status['paused'] = True
				return True
			else:     # unpause
				self.status['paused'] = False
				return False


	def send_queue_as_ready(self):
		"""Continuously call this to keep processing queue."""
		if self.device and not self.status['paused']:
			time.sleep(0.001)  # yield a tiny bit
			try:
				### receiving
				line = self.device.readline()
				if len(line) > 0:
					## assemble lines
					self.process_status_line(line.rstrip())

				### sending
				if len(self.tx_queue) > 0:
					for line in self.tx_queue:
						try:
							print "> " + line
							self.device.write("{0}\n".format(line))
						except serial.SerialTimeoutException:
							# skip, report
							sys.stdout.write("\nsend_queue_as_ready: writeTimeoutError\n")
							sys.stdout.flush()
					self.tx_queue = []

				else:
					if self.job_active:
						# print "\nG-code stream finished!"
						# print "(LasaurGrbl may take some extra time to finalize)"
						self.job_active = False
						# ready whenever a job is done
						self.status['ready'] = True
			except OSError:
				# Serial port appears closed => reset
				# self.close()
				pass
			except ValueError:
				# Serial timeout?
				pass


	def process_status_line(self, line):
		sys.stdout.write("< %s\n" % line)
		sys.stdout.flush()

		if line.startswith('ok'):
			self.status['ready'] = True

		if re.match(r"ok C: X:(.*) Y:(.*) Z:(.*) A:(.*) B:(.*) C:(.*)", line):
			self.status['current_position'] = line

		if re.match(r"Limit switch (.*) was hit", line):  # Stop: A limit was hit
			self.status['limit_hit'] = True
			self.cancel_queue()
		else:
			self.status['limit_hit'] = False

		if '!!' in line:
			# halted! Should probably pause here, and continue if it goes away.
			self.cancel_queue()


			# if 'P' in line:  # Stop: Power is off
			# 	self.status['power_off'] = True
			# else:
			# 	self.status['power_off'] = False

			# if 'D' in line:  # Warning: Door Open
			# 	self.status['door_open'] = True
			# else:
			# 	self.status['door_open'] = False

			# if 'C' in line:  # Warning: Chiller Off
			# 	self.status['chiller_off'] = True
			# else:
			# 	self.status['chiller_off'] = False

			# if 'X' in line:
			# 	self.status['x'] = line[line.find('X')+1:line.find('Y')]
			# # else:
			# #     self.status['x'] = False

			# if 'Y' in line:
			# 	self.status['y'] = line[line.find('Y')+1:line.find('V')]
			# # else:
			# #     self.status['y'] = False

			# if 'V' in line:
			# 	self.status['firmware_version'] = line[line.find('V')+1:]


# singelton
SerialManager = SerialManagerClass()
