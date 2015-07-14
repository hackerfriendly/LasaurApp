
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

		# status flags
		self.status = {}
		self.reset_status()


	def reset_status(self):
		self.status = {
			'ready': False,  # ready after 'ok' if no job is running
			'limit_hit': False,
			'current_position': "",
			'door_open': False,
			'chiller_off': False,
			'x': False,
			'y': False,
			'z': False,
			'firmware_version': None,
			'percent_complete': 0,
			'estimated_time': 0
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
			self.queue_gcode('M114\nM119\nprogress')
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
			# Skip empty lines
			if line == '' or line[0] == '%':
				continue
			# Status, abort, homing, and reset always get queued
			if re.match(r"(G28|M26|M119|M114|M112|M999)", line):
				self.tx_queue.append(line)
			# Don't queue lines if a limit has been hit
			elif not self.status['limit_hit']:
				self.tx_queue.append(line)


	def cancel_queue(self):
		self.tx_queue.clear()
		self.status['ready'] = False


	def is_queue_empty(self):
		return len(self.tx_queue) == 0

	def get_queue_percentage_done(self):
		return self.status['percent_complete']

	def process_queue(self):
		"""Continuously call this to keep processing queue."""
		if self.device:
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

			except OSError:
				# Serial port appears closed => reset
				self.close()
			except ValueError:
				# Serial timeout?
				self.close()


	def process_status_line(self, line):

		# if line.startswith('ok'):
		# 	self.status['ready'] = True

		# if '!!' in line:

		match = re.search(r"ok C: X:(.*) Y:(.*) Z:(.*) A:(.*) B:(.*) C:(.*)", line)
		if match:
			self.status['current_position'] = line
			self.status['x'] = match.group(1)
			self.status['y'] = match.group(2)
			self.status['z'] = match.group(3)

		# file: /job.gcode, 2 % complete, elapsed time: 2 s
		# file: /job.gcode, 47 % complete, elapsed time: 71 s, est time: 77 s
		match = re.search(r"file.* (\d+).*complete", line)
		if match:
			self.status['percent_complete'] = match.group(1)

		if re.match(r"Not currently playing", line):
			self.status['ready'] = True
			self.status['percent_complete'] = 0

		if re.match(r"Limit switch (.*) was hit", line):  # Stop: A limit was hit
			self.status['limit_hit'] = True
			self.cancel_queue()

		if re.match(r"(min|max)_(x|y|z):", line):
			if '1' in line:
				self.status['limit_hit'] = True
			else:
				self.status['limit_hit'] = False

		sys.stdout.write("< %s\n" % line)
		sys.stdout.flush()

# singelton
SerialManager = SerialManagerClass()
