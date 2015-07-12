
import os
import re
import sys
import time
import serial
from collections import deque

class SerialManagerClass:

	def __init__(self):
		self.device = None

		# gcode as a deque
		self.tx_queue = deque()

		# used for calculating percentage done
		self.job_active = False

		# status flags
		self.status = {}
		self.reset_status()


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
		self.tx_queue.clear()
		self.reset_status()

		self.device = serial.Serial(port, baudrate, timeout=0.1, writeTimeout=0.1)


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
		if self.is_queue_empty():
			self.queue_gcode('M114\nM119')
		return self.status


	def flush_input(self):
		if self.device:
			self.device.flushInput()


	def flush_output(self):
		if self.device:
			self.device.flushOutput()


	def queue_gcode(self, gcode):
		lines = gcode.split('\n')

		for line in lines:
			line = line.strip()
			if line == '' or line[0] == '%':
				continue
			self.tx_queue.append(line)

		self.job_active = True


	def cancel_queue(self):
		self.tx_queue.clear()
		self.job_active = False
		self.status['ready'] = False


	def is_queue_empty(self):
		return len(self.tx_queue) == 0

	def get_queue_percentage_done(self):
		return "50"
		# TODO
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


	def process_queue(self):
		"""Continuously call this to keep processing queue."""
		if self.device and not self.status['paused']:
			try:
				### receiving
				line = self.device.readline()
				if len(line) > 0:
					## assemble lines
					self.process_status_line(line.rstrip())

				### sending
				if len(self.tx_queue) > 0:
					line = self.tx_queue.popleft()
					try:
						print "> " + line
						self.device.write("{0}\n".format(line))
					except serial.SerialTimeoutException:
						# skip, report
						sys.stdout.write("\nprocess_queue: writeTimeoutError\n")
						sys.stdout.flush()

				else:
					if self.job_active:
						# print "\nG-code stream finished!"
						# print "(LasaurGrbl may take some extra time to finalize)"
						self.job_active = False
						# ready whenever a job is done
						self.status['ready'] = True
			except OSError:
				# Serial port appears closed => reset
				self.close()
			except ValueError:
				# Serial timeout?
				self.close()


	def process_status_line(self, line):
		sys.stdout.write("< %s\n" % line)
		sys.stdout.flush()

		if line.startswith('ok'):
			self.status['ready'] = True

		if re.match(r"ok C: X:(.*) Y:(.*) Z:(.*) A:(.*) B:(.*) C:(.*)", line):
			self.status['current_position'] = line

		if re.match(r"(min|max)_(x|y|z):", line):
			if '1' in line:
				self.status['limit_hit'] = True
			else:
				self.status['limit_hit'] = False

		if re.match(r"Limit switch (.*) was hit", line):  # Stop: A limit was hit
			self.status['limit_hit'] = True
			self.cancel_queue()

		if '!!' in line:
			if 'G28' in self.tx_queue:
				self.set_pause(False)
			else:
				self.set_pause(True)

# singelton
SerialManager = SerialManagerClass()
