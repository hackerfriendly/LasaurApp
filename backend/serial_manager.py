
import os
import re
import sys
import time
import serial
from collections import deque


class SerialManagerClass:

	def __init__(self):
		self.device = None

		self.rx_buffer = ""
		self.tx_buffer = ""
		self.tx_index = 0
		self.remoteXON = True

		# TX_CHUNK_SIZE - this is the number of bytes to be
		# written to the device in one go. It needs to match the device.
		self.TX_CHUNK_SIZE = 16
		self.RX_CHUNK_SIZE = 16
		self.nRequested = 0

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
		self.rx_buffer = ""
		self.tx_buffer = ""
		self.tx_index = 0
		self.remoteXON = True
		self.reset_status()

		# Create serial device with both read timeout set to 0.
		# This results in the read() being non-blocking
		# Write on the other hand uses a large timeout but should not be blocking
		# much because we ask it only to write TX_CHUNK_SIZE at a time.
		# BUG WARNING: the pyserial write function does not report how
		# many bytes were actually written if this is different from requested.
		# Work around: use a big enough timeout and a small enough chunk size.
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
		# if self.is_queue_empty():
		# 	# trigger a status report
		# 	# will update for the next status request
		# 	self.queue_gcode('?')
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
		job_list = []
		for line in lines:
			line = line.strip()
			if line == '' or line[0] == '%':
				continue

			job_list.append(line)

		gcode_processed = '\n'.join(job_list) + '\n'
		self.tx_buffer += gcode_processed
		self.job_active = True


	def cancel_queue(self):
		self.tx_buffer = ""
		self.tx_index = 0
		self.job_active = False
		self.status['ready'] = False


	def is_queue_empty(self):
		return self.tx_index >= len(self.tx_buffer)


	def get_queue_percentage_done(self):
		buflen = len(self.tx_buffer)
		if buflen == 0:
			return ""
		return str(100*self.tx_index/float(buflen))


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
			try:
				### receiving
				chars = self.device.read(self.RX_CHUNK_SIZE)
				if len(chars) > 0:
					self.nRequested = self.TX_CHUNK_SIZE
					## assemble lines
					self.rx_buffer += chars
					while(1):  # process all lines in buffer
						posNewline = self.rx_buffer.find('\n')
						if posNewline == -1:
							break  # no more complete lines
						else:  # we got a line
							line = self.rx_buffer[:posNewline]
							self.rx_buffer = self.rx_buffer[posNewline+1:]
						# print "received: " + line
						self.process_status_line(line.rstrip())
				else:
					if self.nRequested == 0:
						time.sleep(0.001)  # no rx/tx, rest a bit

				### sending
				if self.tx_index < len(self.tx_buffer):
					if self.nRequested > 0:
						try:
							t_prewrite = time.time()
							print "> " + self.tx_buffer[self.tx_index:self.tx_index+self.nRequested]
							actuallySent = self.device.write(
								self.tx_buffer[self.tx_index:self.tx_index+self.nRequested])
							if time.time()-t_prewrite > 0.02:
								sys.stdout.write("WARN: write delay 1\n")
								sys.stdout.flush()
						except serial.SerialTimeoutException:
							# skip, report
							actuallySent = 0  # assume nothing has been sent
							sys.stdout.write("\nsend_queue_as_ready: writeTimeoutError\n")
							sys.stdout.flush()
						self.tx_index += actuallySent
						self.nRequested -= actuallySent

				else:
					if self.job_active:
						# print "\nG-code stream finished!"
						# print "(LasaurGrbl may take some extra time to finalize)"
						self.tx_buffer = ""
						self.tx_index = 0
						self.job_active = False
						# ready whenever a job is done
						self.status['ready'] = True
			except OSError:
				# Serial port appears closed => reset
				self.close()
			except ValueError:
				# Serial port appears closed => reset
				self.close()


	def process_status_line(self, line):
		if line == 'ok':
			print '< ok'
			self.status['ready'] = True
			return

		if re.match(r"Limit switch (.*) was hit", line):  # Stop: A limit was hit
			self.status['limit_hit'] = True
			self.cancel_queue()
		else:
			self.status['limit_hit'] = False

		if '!!' in line:
			# halted!
			self.cancel_queue()

		sys.stdout.write("< %s\n" % line)
		sys.stdout.flush()

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
