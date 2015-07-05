
import os
import sys
import time
import serial
from collections import deque


class SerialManagerClass:

	def __init__(self):
		self.device = None

		self.nRequested = 0

		# used for calculating percentage done
		self.job_active = False

		# status flags
		self.status = {}
		self.reset_status()

		self.job_list = []

	def reset_status(self):
		self.status = {
			'ready': True,  # turns True by querying status
			'paused': False,  # this is also a control flag
			'buffer_overflow': False,
			'transmission_error': False,
			'bad_number_format_error': False,
			'expected_command_letter_error': False,
			'unsupported_statement_error': False,
			'power_off': False,
			'limit_hit': False,
			'serial_stop_request': False,
			'door_open': False,
			'chiller_off': False,
			'x': False,
			'y': False,
			'firmware_version': None
		}


	def connect(self, port, baudrate):
		self.reset_status()
		self.device = serial.Serial(port, baudrate, timeout=0, writeTimeout=1)

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
		return self.status

	def flush_input(self):
		if self.device:
			self.device.flushInput()

	def flush_output(self):
		if self.device:
			self.device.flushOutput()


	def queue_gcode(self, gcode):
		lines = gcode.split('\n')
		# print "Adding to queue %s lines" % len(lines)
		print "Adding to queue:"
		print lines
		for line in lines:
			line = line.strip()
			if line == '' or line[0] == '%':
				continue

			self.job_list.append(line)


	def get_queue_percentage_done(self):
		return 100


	def set_pause(self, flag):
		# returns pause status
		if flag:  # pause
			self.status['paused'] = True
			return True
		else:     # unpause
			self.status['paused'] = False
			return False


	def send_queue_as_ready(self):
		"""Continuously call this to keep processing queue."""
		if self.device and not self.status['paused']:
			try:
				### receiving
				reply = self.device.read()
				if len(reply) > 0:
					self.process_status_line(reply.rstrip())
				else:
					time.sleep(0.001)  # no rx/tx, rest a bit

				### sending
				for line in self.job_list:
					self.device.write(line)
					self.job_list = []

			except OSError:
				# Serial port appears closed => reset
				self.close()
			except ValueError:
				# Serial port appears closed => reset
				self.close()


	def process_status_line(self, line):
		print 'processing status line: ' + line
		if line == 'ok':
			print 'All good.'
		elif '#' in line[:3]:
			# print and ignore
			sys.stdout.write(line + "\n")
			sys.stdout.flush()
		elif '^' in line:
			sys.stdout.write("\nFEC Correction!\n")
			sys.stdout.flush()
		else:
			if '!' in line:
				# in stop mode
				# not ready whenever in stop mode
				# self.status['ready'] = False
				sys.stdout.write(line + "\n")
				sys.stdout.flush()
			else:
				sys.stdout.write(".")
				sys.stdout.flush()

			if 'N' in line:
				self.status['bad_number_format_error'] = True
			if 'E' in line:
				self.status['expected_command_letter_error'] = True
			if 'U' in line:
				self.status['unsupported_statement_error'] = True

			if 'B' in line:  # Stop: Buffer Overflow
				self.status['buffer_overflow'] = True
			else:
				self.status['buffer_overflow'] = False

			if 'T' in line:  # Stop: Transmission Error
				self.status['transmission_error'] = True
			else:
				self.status['transmission_error'] = False

			if 'P' in line:  # Stop: Power is off
				self.status['power_off'] = True
			else:
				self.status['power_off'] = False

			if 'L' in line:  # Stop: A limit was hit
				self.status['limit_hit'] = True
			else:
				self.status['limit_hit'] = False

			if 'R' in line:  # Stop: by serial requested
				self.status['serial_stop_request'] = True
			else:
				self.status['serial_stop_request'] = False

			if 'D' in line:  # Warning: Door Open
				self.status['door_open'] = True
			else:
				self.status['door_open'] = False

			if 'C' in line:  # Warning: Chiller Off
				self.status['chiller_off'] = True
			else:
				self.status['chiller_off'] = False

			if 'X' in line:
				self.status['x'] = line[line.find('X')+1:line.find('Y')]
			# else:
			#     self.status['x'] = False

			if 'Y' in line:
				self.status['y'] = line[line.find('Y')+1:line.find('V')]
			# else:
			#     self.status['y'] = False

			if 'V' in line:
				self.status['firmware_version'] = line[line.find('V')+1:]





# singelton
SerialManager = SerialManagerClass()
