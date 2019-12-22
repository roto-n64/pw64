#!/usr/bin/env python3

# UPWT Parser v0.04 by roto
#
# UPWT blocks are the Missions or "Tests" throughout the game. This parser attempts to explain
# all the sections in the UPWT chunks and what they do to set up a test.
# For an definitions of a lot of these acronyms and more RE info, see:
#     https://github.com/magcius/noclip.website/wiki/Pilotwings-64-Research-&-Development
#
#
# Thanks to: queueRAM, pfedak, Jasper
#

# 1) Add the filename of your ROM in the PW64_Rom var (only supports US at the moment)
# 2) Run as: ./pw64_upwt_parser.py <TEST_ID> (or without Test ID to see a list of them)

# Needs more research as data doesn't make sense: CNTG / FALC / HOPD / HPAD / LWND / PHTS

# ToDo:
# Add JSON output/dump
# ArgParse for flags (such as JSON output above)

# ToDo Later:
# More Verbose Array Data dump descriptions (like in COMM/BALS) for each chunk type (for vimdiff)

import binascii
import itertools
import struct
import sys

# Global variables shared between some functions
COMM_Object_Thermals = 0
COMM_Object_LocalWinds = 0
COMM_Object_TPADs = 0
COMM_Object_LPADs = 0
COMM_Object_LSTPs = 0
COMM_Object_Rings = 0
COMM_Object_Balloons = 0
COMM_Object_Rocket_Targets = 0
COMM_Object_Floating_Pads = 0
COMM_Object_Ball_Target = 0
COMM_Object_Photo_Target = 0
COMM_Object_Falcos = 0
COMM_Object_Unknown = 0
COMM_Object_Cannon_Targets = 0
COMM_Object_HM_Goals = 0
Game_Text_Data = {} # Dict of game (Test) names and accompanying mission text
Game_Test_Data = {} # Dict of the tests/missions available

# Will hold our table of files: File Type, File Offset, and File Size
fs_table = {}
# Shortcuts for the above dict
FS_FILE_TYPE = 0
FS_FILE_OFFSET = 1
fs_file_size = 2

# PW64 ROM File Name
PW64_Rom = ""

def main():
	Chunk_Types = ['JPTX', 'NAME', 'INFO', 'COMM', 'FALC',
				   'THER', 'TPAD', 'LPAD', 'BALS', 'HOPD',
				   'RNGS', 'LSTP', 'TARG', 'PAD ', 'HPAD',
				   'PHTS', 'LWIN', 'BTGT', 'CNTG']

	if PW64_Rom == '':
		print("Update the 'PW64_Rom' variable and run me again!")
		sys.exit(1)
	
	# Unpack and decode the FS
	global fs_table
	fs_table = unpack_full_tabl()

	# Read the ADAT chunk from the ROM and store in a global dict
	game_text_builder()

	# Build the list of available Test IDs and populate "Game_Test_Data"
	tests_list = mission_index_builder()
	
	# Did we get a Test ID?
	if len(sys.argv) < 2:
		print("Please provide a Test ID!\n")
		print("Here's some options:\n\n%s" % tests_list)
		sys.exit(1)
	else:
		Test_ID = sys.argv[1]
	
	if Test_ID not in Game_Test_Data:
		print("Unknown Test ID!")
		sys.exit(1)

	# This whole section REALLY needs to be rewritten. It doesn't work right.
	# I kept it mostly as is from when I was feeding this script raw FORM rips.
	# Since it now reads the ROM it doesn't work correctly...
	# e.g. if it reads an "unknown" chunk (change HPAD to HPOD) it just skips it.
	with open(PW64_Rom, 'rb') as pw64_rom:
		# Find the test ID in the dict, go to the offset of the provided Test ID and start parsing it
		pw64_rom.seek(int(Game_Test_Data[Test_ID], 16))
		#print("*** %s" % hex(pw64_rom.tell()))
		while True:
			Marker = pw64_rom.read(4).decode()
			if Marker == "FORM":
				# This is special because we don't want to read in the entire block.
				Marker_Length = pw64_rom.read(4).hex()
				Marker_Data_Start = pw64_rom.tell()
				FORM_Length = Marker_Length
			elif Marker == "UPWT": # No Length. Data Descriptor: "Ultra Pilot Wings Test"
				Marker_Length = 0
				pass
			elif Marker == "UPWL":
				print("Soon...")
				sys.exit(1)
			elif Marker in Chunk_Types:
				Marker_Length = pw64_rom.read(4).hex()
				Marker_Data_Start = pw64_rom.tell()
			else:
				if int(hex(pw64_rom.tell()), 16) >= int(FORM_Length, 16):
					break
				else:
					# Unknown data chunk. NOTE: This doesn't even work right now.
					print("%s: %s | %s" % (hex(pw64_rom.tell()), binascii.b2a_hex(Marker), Marker))
					print("What is this?")
					#sys.exit(1)
					break

			print("-------")
			print("Marker: %s" % Marker)
			print("\tLength: %s" % Marker_Length)
			print("\tData Offset: %s" % hex(Marker_Data_Start)) # Marker, Length -> Data Start (Offset)


			if Marker == "NAME" or Marker == "INFO":
				# Usually ASCII that doesn't need parsing
				Marker_Data = pw64_rom.read(int(Marker_Length, 16))
				print("\t\tData: %s" % Marker_Data.decode())
			elif Marker == "BALS":
				BALS_parser(pw64_rom, Marker_Length)
			elif Marker == "BTGT" or Marker == "HOPD":
				BTGT_HOPD_parser(pw64_rom, Marker_Length)
			elif Marker == "CNTG":
				CNTG_parser(pw64_rom, Marker_Length)
			elif Marker == "COMM":
				COMM_parser(pw64_rom, Marker_Length)
			elif Marker == "FALC":
				FALC_parser(pw64_rom, Marker_Length)
			elif Marker == "HPAD":
				HPAD_parser(pw64_rom, Marker_Length)
			elif Marker == "JPTX":
				JPTX_parser(pw64_rom, Marker_Length)
			elif Marker == "LPAD" or Marker == "LSTP" or Marker == "TPAD": # These seem to have identical structures.
				LPAD_LSTP_TPAD_parser(pw64_rom, Marker_Length)
			elif Marker == "LWIN":
				LWIN_parser(pw64_rom, Marker_Length)
			elif Marker == "PHTS":
				PHTS_parser(pw64_rom, Marker_Length)
			elif Marker == "RNGS":
				RNGS_parser(pw64_rom, Marker_Length)
			elif Marker == "TARG":
				TARG_parser(pw64_rom, Marker_Length)
			elif Marker == "THER":
				THER_parser(pw64_rom, Marker_Length)

			# Another reason this needs to be rewritten.
			if Marker != "FORM" and Marker != "UPWT":
				# We're done here, go back to start of this chunk + length of chunk (to get to next one)
				pw64_rom.seek(Marker_Data_Start + int(Marker_Length, 16), 0)
				#print("*** %s" % hex(pw64_rom.tell()))

			# Ugh this is a hacky "stop".
			# If we're past Test_ID's offset + size of FORM, bail out.
			# Should rewrite this whole section to read in whole FORM and process it properly.
			#
			# Comment this out and run with "A_EX_1" as the Test ID to dump ALL the tests.
			if pw64_rom.tell() >= int(FORM_Length, 16)+int(Game_Test_Data[Test_ID], 16):
				#print("DONE")
				#print("*** %s" % hex(pw64_rom.tell()))
				pw64_rom.close()
				sys.exit(0)

		pw64_rom.close()
		sys.exit(0)

def grouper(iterable, n, fillvalue=None):
	# For grouping n number of characters together for display
    args = [iter(iterable)] * n
    return itertools.zip_longest(fillvalue=fillvalue, *args)

def dsplit(data, convert=False):
	# Doubleword Split with base 16 conversion if needed
	if convert == True:
		return int(data[0:2],16), int(data[2:4],16), int(data[4:6],16), int(data[6:8],16)
	else:
		return data[0:2], data[2:4], data[4:6], data[6:8]

def mission_index_builder():
	# Seeks out each UPWT chunk in the ROM and builds a dict with TestID->Offsets
	# This function is probably reduntant because of unpack_full_tabl() since it was previously only meant for UPWT.
	# Maybe redo that other function to find UPWT's instead of here.

	global Game_Test_Data
	global fs_table

	task_list = [] # Build a list of Test ID's for user consumption and populate list to be returned by this func

	# Open the ROM and find the first UPWT chunk (since they are grouped in the FS, this is safe-ish)
	with open(PW64_Rom, 'rb') as pw64_rom:
		# Find our first instance of the file type. Files are grouped together. This is fine. Probably.
		pw_file_type = "UPWT"
		for file_index in fs_table:
			if fs_table[file_index][FS_FILE_TYPE] == pw_file_type:
				file_first_hit = int(fs_table[file_index][FS_FILE_OFFSET], 16)
				break

		# This is an unnecessary ROM read. Only pulls mission ID for UPWT. But for all other files reads junk into "task_ID".
		with open(PW64_Rom, 'rb') as pw64_rom:
			location = file_first_hit
			for fs_index in range(len(fs_table)):
				file_type = fs_table[fs_index][FS_FILE_TYPE]
				if  file_type == pw_file_type:
					file_size = fs_table[fs_index][fs_file_size]

					# This is the only reason we read the ROM yet again...
					if file_type == "UPWT":
						pw64_rom.seek(location + 0x20, 0) # Skip 0x20 bytes to go straight to the test/task name/ID
						task_ID = pw64_rom.read(6).decode()
					else:
						task_ID = "" # We don't _really_ needs this since we never read out the Task ID for non-UPWT.

					# The Canon missions have identical ID's for 4 tests each...
					# e.g. A_EX_[1-3]
					# Need a better solution here. Nested dicts? 
					if task_ID in Game_Test_Data:
							# For now, append the offset to the ID if it "already exists" (dupe)
							task_ID = task_ID + '-' + hex(location)

					Game_Test_Data.update({ task_ID: hex(location) })
					task_list.append(task_ID)
					location = location + file_size # Very critical this is updated last.

		pw64_rom.close()

		# For main program help "options"
		task_list.sort()
		return ", ".join(task_list)

def game_text_builder():
	global Game_Text_Data
	global fs_table

	# Find our ADAT chunk in the FS
	for fs_index, fs_attrs in fs_table.items():
		if fs_attrs[FS_FILE_TYPE] == "ADAT":
			adat_offset = fs_attrs[FS_FILE_OFFSET]

	# Open the ROM and process the ADAT chunk
	with open(PW64_Rom, 'rb') as pw64_rom:
		pw64_rom.seek(int(adat_offset, 16), 0)

		FORM_block_marker = pw64_rom.read(4).decode()
		FORM_block_length = binascii.b2a_hex(pw64_rom.read(4))
		
		# Hardcode skip 0x20 bytes from current position to get to the first NAME:
		#		ADAT marker (name 0x4 bytes, no length), 
		#		PAD (name 0x4 bytes + length 0x4 bytes + data 0x4 bytes)
		#		SIZE (name 0x4 bytes + length 0x4 bytes + data 0x8 bytes)
		pw64_rom.seek(0x20, 1)
		
		while True:
			NAME_chunk_marker = pw64_rom.read(4).decode()
			NAME_chunk_length = binascii.b2a_hex(pw64_rom.read(4))
		
			if NAME_chunk_marker == "NAME":
				data = pw64_rom.read(int(NAME_chunk_length, 16)).decode().rstrip('\0')
		
				DATA_chunk_marker = pw64_rom.read(4).decode()
				DATA_chunk_length = binascii.b2a_hex(pw64_rom.read(4))
				data_text = binascii.b2a_hex(pw64_rom.read(int(DATA_chunk_length, 16))).decode()
				
				Game_Text_Data.update({data: data_text})
		
				# Dump all the text?
				#print_adat_decoded(binascii.b2a_hex(Game_Text_Data[data]), True)

			# Bail out if we're reading past START+END_OF_FORM 
			if pw64_rom.tell() >= int(FORM_block_length, 16)+0x35C08C:
				break
			
		pw64_rom.close()

def print_adat_decoded(hex_data):
	# This is the same code as what I added to queueRAM's PW64 FS dumper
	#
	# The DATA blocks in the ADAT container appear to be "coded" ASCII strings.
	# The strings use a sort of look-up table as seen below.
	# This was probably done for easier localization (Kanji font textures?)
	# The Font Sprite/Texture maps are in the "STRG" container/blocks.
	# This table was extrapolated from the FS dump and PJ64 memory searches.
	char_map_combined = { # // Normal Font //
						'00': '0', '01': '1', '02': '2', '03': '3', '04': '4',
						'05': '5', '06': '6', '07': '7', '08': '8', '09': '9',
						'0A': 'A', '0B': 'B', '0C': 'C', '0D': 'D', '0E': 'E',
						'0F': 'F', '10': 'G', '11': 'H', '12': 'I', '13': 'J',
						'14': 'K', '15': 'L', '16': 'M', '17': 'N', '18': 'O',
						'19': 'P', '1A': 'Q', '1B': 'R', '1C': 'S', '1D': 'T',
						'1E': 'U', '1F': 'V', '20': 'W', '21': 'X', '22': 'Y',
						'23': 'Z', '24': 'a', '25': 'b', '26': 'c', '27': 'd',
						'28': 'e', '29': 'f', '2A': 'g', '2B': 'h', '2C': 'i',
						'2D': 'j', '2E': 'k', '2F': 'l', '30': 'm', '31': 'n',
						'32': 'o', '33': 'p', '34': 'q', '35': 'r', '36': 's',
						'37': 't', '38': 'u', '39': 'v', '3A': 'w', '3B': 'x',
						'3C': 'y', '3D': 'z', '3E': '-', '3F': '#', '40': '<',
						'41': '>', '42': ' ', '43': '\"', '44': '(', '45': ')',
						'46': '*', '47': '&', '48': ',', '49': '.', '4A': '/',
						'4B': '!', '4C': '?', '4D': '\'', '4E': '#', '4F': ':',
						'50': '0', '51': '1', '52': '2', '53': '3', '54': '4',
						'55': '5', '56': '6', '57': '7', '58': '8', '59': '9',
						'5A': '\\', '5B': '\\', '5C': '\\', '5D': '\\',
						'5E': '\\', '5F': '\\',
						# // Bold Font //
						# This obviously doesn't show up in this code.
						# But it is bold in the game. Trust me.
						'60': '0', '61': '1', '62': '2', '63': '3', '64': '4',
						'65': '5', '66': '6', '67': '7', '68': '8', '69': '9',
						'6A': 'A', '6B': 'B', '6C': 'C', '6D': 'D', '6E': 'E',
						'6F': 'F', '70': 'G', '71': 'H', '72': 'I', '73': 'J',
						'74': 'K', '75': 'L', '76': 'M', '77': 'N', '78': 'O',
						'79': 'P', '7A': 'Q', '7B': 'R', '7C': 'S', '7D': 'T',
						'7E': 'U', '7F': 'V', '80': 'W', '81': 'X', '82': 'Y',
						'83': 'Z', '84': 'a', '85': 'b', '86': 'c', '87': 'd',
						'88': 'e', '89': 'f', '8A': 'g', '8B': 'h', '8C': 'i',
						'8D': 'j', '8E': 'k', '8F': 'l', '90': 'm', '91': 'n',
						'92': 'o', '93': 'p', '94': 'q', '95': 'r', '96': 's',
						'97': 't', '98': 'u', '99': 'v', '9A': 'w', '9B': 'x',
						'9C': 'y', '9D': 'z', '9E': '-', '9F': '#', 'A0': '<',
						'A1': '>', 'A2': ' ', 'A3': '\"', 'A4': '(', 'A5': ')',
						'A6': '*', 'A7': '&', 'A8': ',', 'A9': '.', 'AA': '/',
						'AB': '!', 'AC': '?', 'AD': '\'', 'AE': '}', 'AF': ':',
						'B0': '0', 'B1': '1', 'B2': '2', 'B3': '3', 'B4': '4',
						'B5': '5', 'B6': '6', 'B7': '7', 'B8': '8', 'B9': '9',
						'BA': '\\', 'BB': '\\', 'BC': '\\', 'BD': '\\',
						'BE': '\\', 'BF': '\\' }


	hex_split = [(hex_data[i:i+2]) for i in range(0, len(hex_data), 2)]

   # Empty list for storing final string
	adat_final_string = []

	# Read a pair of hex bytes
	for i in range(0, len(hex_split), 2):
		hex_pair = hex_split[i:i+2]

		char_byte1 = hex_pair[0].upper()
		char_byte2 = hex_pair[1].upper()

		if char_byte1 == '00':
		  if char_byte2 == 'CA':
			  # slash? '\' ?
			  pass
		  elif char_byte2 == 'D4':
			  # Unknown char
			  pass
		  elif char_byte2 == 'FE':
			  # Newline
			  adat_final_string.append('\n')
		  elif char_byte2 == 'FD':
			  # Tab?
			  pass
		  elif char_byte2 == 'FF':
			  # EOF/EOS
			  break
		  else:
			  adat_final_string.append(char_map_combined[char_byte2])
		else:
		  # We found some weird control char in our pair?
		  adat_final_string.append('?0')

	return adat_final_string

def BALS_parser(BALS_Data, length):
	# BALS missions: E_RP_1 B_RP_1 P_RP_2 B_RP_3
	# Still needs further research but is mostly reliable.
	BALS_Data_Start = BALS_Data.tell()

	# 0x68 bytes per Ball
	UPWT_BALS_Data = []
	for ball in range(1, COMM_Object_Balloons+1):
		UPWT_BALS_Data.append(binascii.b2a_hex(BALS_Data.read(0x68)))

	counter = 0
	for ball in UPWT_BALS_Data:	
		counter += 1	

		# Convert from bytes to str of hex chars because of python3
		ball = ball.decode()

		# Groups 8 byte blocks, makes into a list, joins tuple, converts to bytearray from hex. disgusting.
		BALS_x = bytearray.fromhex(''.join(list(grouper(ball, 8, '?'))[0]))
		BALS_z = bytearray.fromhex(''.join(list(grouper(ball, 8, '?'))[1]))
		BALS_y = bytearray.fromhex(''.join(list(grouper(ball, 8, '?'))[2]))

		# Bouncy (solid) green ball in RP missions (push to cylinder zone)
		# ^-- 0x8036AB67 == 43fa0000, 0x8036AAE8 = 3f333333 == solid ball in E_RP_1
		BALS_color = ''.join(list(grouper(ball, 2, '?'))[32])
		BALS_type = ''.join(list(grouper(ball, 2, '?'))[33])

		BALS_solidity = ''.join(list(grouper(ball, 8, '?'))[9])
		BALS_weight = ''.join(list(grouper(ball, 8, '?'))[10])
		BALS_popforce = ''.join(list(grouper(ball, 8, '?'))[11])
		BALS_scale = bytearray.fromhex(''.join(list(grouper(ball, 8, '?'))[12]))


		# Round FP precision to 6 digits		
		UPWT_BALS_Coordinates_Floats = [round(struct.unpack('>f', BALS_x)[0],6), 
										round(struct.unpack('>f', BALS_z)[0],6),
										round(struct.unpack('>f', BALS_y)[0],6),
										round(struct.unpack('>f', BALS_scale)[0],6)]

		# Array Index to description "map"
		array_index_map = { 0: "X",
							1: "Z",
							2: "Y",
							9: "Solid or Poppable",
							10: "Weight",
							11: "Force needed to Pop Balloon",
							12: "Scale (Size)",
							32: "Color",
							33: "Type (Single or Splits into multiple balloons)"}

		print("\n\t\tBall # %s:" % counter)
		print("\t\tBall Data: ")
		print("\t\t\tArray Index | Data         | Data Description")
		print("\t\t\t---------------------------------------------")
		array_index = 0
		for byte_group in ["".join(x) for x in list(grouper(ball, 8, '?'))]:
			if array_index in array_index_map:
				data_chunk_type = array_index_map[array_index]
			else:
				data_chunk_type = ""
			print("\t\t\t    (%s)       %s       %s" % (array_index, byte_group, data_chunk_type))
			array_index += 1

		if BALS_color == '00':
			print("\t\tBall / Balloon Color: Orange (%s)" % BALS_color)
		if BALS_color == '01':
			print("\t\tBall / Balloon Color: Green (%s)" % BALS_color)
		if BALS_color == '02':
			print("\t\tBall / Balloon Color: Blue (%s)" % BALS_color)
		if BALS_type == '00':
			print("\t\tBall / Balloon Type: Normal (%s)" % BALS_type)
		if BALS_type == '01': # Seems anything >= 01 is the same.
			print("\t\tBall / Balloon Type: Splits into 5 Orange Balloons(%s)" % BALS_type)

		# Can't be popped
		if BALS_solidity == '43fa0000':
			print("\t\tBall / Balloon Can Pop: NO") # B_RP_3
		else:
			print("\t\tBall / Balloon Can Pop: YES")
		# /\ --- \/ wait wat? Double check these two...
		# This is a weird one, you need some speed to pop this balloon (check B_RP_1)
		if BALS_popforce == '43fa0000':
			print("\t\tBall Pop Requires Speed/Force (%s ?)" % round(struct.unpack('>f', bytearray.fromhex(BALS_popforce))[0],6))

		# If != 0 the ball moves / bounces and has "gravity" (but might NOT be solid!)
		if BALS_weight != '00000000':
			print("\t\tBall / Balloon Mass (g?): %s" % round(struct.unpack('>f', bytearray.fromhex(BALS_weight))[0],6))

		print("\t\tX: %s\n\t\tY: %s\n\t\tZ: %s" % (UPWT_BALS_Coordinates_Floats[0],
															UPWT_BALS_Coordinates_Floats[2],
															UPWT_BALS_Coordinates_Floats[1]))
		print("\t\tScale: %s" % UPWT_BALS_Coordinates_Floats[3])

def BTGT_HOPD_parser(BTGT_HOPD_data, length):
	# BTGT and HOPD needs verification... seems busted. Sample: B_RP_3
	BTGT_HOPD_Data_Start = BTGT_HOPD_data.tell()

	UPWT_BH_data = binascii.b2a_hex(BTGT_HOPD_data.read(int(length, 16)))

	UPWT_BH_data = UPWT_BH_data.decode()
	
	print("\t\tData: ")
	print("\t\t\tArray Index | Data")
	array_index = 0
	for byte_group in ["".join(x) for x in list(grouper(UPWT_BH_data, 8, '?'))]:
		print("\t\t\t    (%s)       %s" % (array_index, byte_group))
		array_index += 1
			
	BTGT_HOPD_data.seek(BTGT_HOPD_Data_Start, 0) # Go back to start

	# Read the Float coordinates and width/heigh of destination cylinder area
	BTGT_HOPD_x = BTGT_HOPD_data.read(4)		# X
	BTGT_HOPD_z = BTGT_HOPD_data.read(4)		# Z
	BTGT_HOPD_y = BTGT_HOPD_data.read(4)		# Y
	BTGT_HOPD_yaw = BTGT_HOPD_data.read(4)		# Yaw
	BTGT_HOPD_width = BTGT_HOPD_data.read(4)	# Width
	BTGT_HOPD_height = BTGT_HOPD_data.read(4)	# Height

	UPWT_BTGT_HOPD_Coordinates_Floats = [round(struct.unpack('>f', BTGT_HOPD_x)[0],6), 
									round(struct.unpack('>f', BTGT_HOPD_z)[0],6),
									round(struct.unpack('>f', BTGT_HOPD_y)[0],6),
									round(struct.unpack('>f', BTGT_HOPD_yaw)[0],6),
									round(struct.unpack('>f', BTGT_HOPD_width)[0],6),
									round(struct.unpack('>f', BTGT_HOPD_height)[0],6)]

	print("\t\tX: %s\n\t\tY: %s\n\t\tZ: %s\n\t\tWidth %s\n\t\tHeight: %s" % (UPWT_BTGT_HOPD_Coordinates_Floats[0],
														UPWT_BTGT_HOPD_Coordinates_Floats[2],
														UPWT_BTGT_HOPD_Coordinates_Floats[1],
														UPWT_BTGT_HOPD_Coordinates_Floats[4],
														UPWT_BTGT_HOPD_Coordinates_Floats[5]))


def COMM_parser(COMM_Data, length):
	# Data shared between multiple functions
	global COMM_Object_Thermals
	global COMM_Object_LocalWinds
	global COMM_Object_TPADs
	global COMM_Object_LPADs
	global COMM_Object_LSTPs
	global COMM_Object_Rings
	global COMM_Object_Balloons
	global COMM_Object_Rocket_Targets
	global COMM_Object_Floating_Pads
	global COMM_Object_Ball_Target
	global COMM_Object_Photo_Target
	global COMM_Object_Falcos
	global COMM_Object_Unknown
	global COMM_Object_Cannon_Targets
	global COMM_Object_HM_Goals

	# Array/List that will hold COMM data in 4 "hex-byte" chunks
	COMM_DW_List = []

	# Array Index to description "map"
	array_index_map = { 0: "Pilot Class / Vehicle / Test Number / Level",
						2: "Weather (Time of Day) / Snow",
						4: "West/East Wind",
						5: "South/North Wind",
						6: "Up/Down Wind",
						263: "THER / LWND / TPAD / LPAD",
						264: "LSTP / RNGS / BALS / TARG",
						265: "HPAD / BTGT / PHTS / FALC",
						266: "UNKNOWN / CNTG / HOPD"}

	### Debug
	# Read in and dump whole COMM into a list 4-bytes at a time
	UPWT_COMM_data = binascii.b2a_hex(COMM_Data.read(int(length, 16))).decode()

	print("\t\tData: ")
	print("\t\t\tArray Index | Data         | Data Description")
	print("\t\t\t---------------------------------------------")
	array_index = 0
	for byte_group in ["".join(x) for x in list(grouper(UPWT_COMM_data, 8, '?'))]:
		if array_index in array_index_map:
			data_chunk_type = array_index_map[array_index]
		else:
			data_chunk_type = ""
		print("\t\t\t    (%s)       %s       %s" % (array_index, byte_group, data_chunk_type))
		COMM_DW_List.append(byte_group)
		array_index += 1

	# These 4 values are from the first doubleword (4-bytes) in the COMM array/list
	COMM_Class = dsplit(COMM_DW_List[0])[0]
	COMM_Vehicle = dsplit(COMM_DW_List[0])[1]
	COMM_Test_Number = dsplit(COMM_DW_List[0])[2]
	COMM_Level = dsplit(COMM_DW_List[0])[3]

	COMM_Skybox = dsplit(COMM_DW_List[2])[0]
	COMM_Snow = dsplit(COMM_DW_List[2])[1] # Only visible on real HW or in Emu with S/W rendering.

	# Constant Level Wind Data
	# 4X == Positive, CX == Negative (West/East, South/North, Up/Down)
	COMM_WestEast_Wind = round(struct.unpack('>f', bytes.fromhex(COMM_DW_List[4]))[0],6) # +West, -East
	COMM_SouthNorth_Wind = round(struct.unpack('>f', bytes.fromhex(COMM_DW_List[5]))[0],6) # +South, -North
	COMM_UpDown = round(struct.unpack('>f', bytes.fromhex(COMM_DW_List[6]))[0],6) # Y-axis lift
											# Needs to go back to 'b'ytes because we .decode()ed the data before.

	# Counts of Objects / Targets / etc
	COMM_Object_Thermals = dsplit(COMM_DW_List[263], True)[0]
	COMM_Object_LocalWinds = dsplit(COMM_DW_List[263], True)[1]
	COMM_Object_TPADs = dsplit(COMM_DW_List[263], True)[2] # Takeoff "Pad" coordinates (not always on ground, e.g. HG)
	COMM_Object_LPADs = dsplit(COMM_DW_List[263], True)[3] # HG/RP/SD Landing Pad

	COMM_Object_LSTPs = dsplit(COMM_DW_List[264], True)[0] # Gyro Landing Strip
	COMM_Object_Rings = dsplit(COMM_DW_List[264], True)[1]
	COMM_Object_Balloons = dsplit(COMM_DW_List[264], True)[2]
	COMM_Object_Rocket_Targets = dsplit(COMM_DW_List[264], True)[3]

	COMM_Object_Floating_Pads = dsplit(COMM_DW_List[265], True)[0]
	COMM_Object_Ball_Target = dsplit(COMM_DW_List[265], True)[1] # BTGT (Ball Target/Destination cylinder marker)
	COMM_Object_Photo_Target = dsplit(COMM_DW_List[265], True)[2]
	COMM_Object_Falcos = dsplit(COMM_DW_List[265], True)[3] # "Falcos Domains" from debug_printf

	COMM_Object_Unknown = dsplit(COMM_DW_List[266], True)[0] # Nothing in Debug output upon changing this value.
	COMM_Object_Cannon_Targets = dsplit(COMM_DW_List[266], True)[1]
	COMM_Object_HM_Goals = dsplit(COMM_DW_List[266], True)[2] # Jumble Hopper destination

	# Thanks to 'pfedak' for initial findings on these dicts
	classes = {'00': 'Beginner', '01': 'Class A', '02': 'Class B', '03': 'Pilot Class'}
	vehicles = {'00': 'Hang Glider', '01': 'Rocket Pack', '02': 'Gyro Copter', '03': 'Cannon Ball', '04': 'Sky Diver', '05': 'Jumble Hopper', '06': 'Birdman'}
	# Test, 00 = 1, 01 = 2
	levels = {'00': 'Holiday Island', '01': 'Crescent Island', '02': 'Little States', '03': 'Ever-Frost Island'}
	skybox = {'00': 'Sunny', '01': 'Sunny Part 2', '02': 'Cloudy', '03': '???', '04': 'Evening', '05': 'Starry Night'}
                                                                      #^-- P_RP_2, very cloudy?
	print("\t-------")
	print("\tMission / Test Details:")
	print("\t\tClass: %s (%s)" % (classes[COMM_Class], COMM_Class))
	print("\t\tVehicle: %s (%s)" % (vehicles[COMM_Vehicle], COMM_Vehicle))
	print("\t\tTest Number: %s (%s)" % (int(COMM_Test_Number, 16)+1, COMM_Test_Number))
	print("\t\tLevel: %s (%s)" % (levels[COMM_Level], COMM_Level))
	print("\t\tWeather / Time: %s (%s)" % (skybox[COMM_Skybox], COMM_Skybox))
	if COMM_Snow == '01':
		print("\t\t\tSnowing: Yes (%s)" % (COMM_Snow))
	#---
	# If 0 ; show nothing
	if COMM_WestEast_Wind < 0:
		print("\t\tWind Force East: %s" % COMM_WestEast_Wind)
	elif COMM_WestEast_Wind > 0:
		print("\t\tWind Force West: %s" % COMM_WestEast_Wind)
	if COMM_SouthNorth_Wind < 0:
		print("\t\tWind Force North: %s" % COMM_SouthNorth_Wind)
	elif COMM_SouthNorth_Wind > 0:
		print("\t\tWind Force South: %s" % COMM_SouthNorth_Wind)
	if COMM_UpDown < 0:
		print("\t\tWind Force Down: %s" % COMM_UpDown)
	elif COMM_UpDown > 0:
		print("\t\tWind Force Up: %s" % COMM_UpDown)
	#---
	print("\t-------")
	print("\tMission Parameters:")
	print("\t\tHang Glider Thermals: %s" % COMM_Object_Thermals)
	print("\t\tLocal Winds: %s" % COMM_Object_LocalWinds)
	print("\t\tTakeoff Pads/Strips: %s" % COMM_Object_TPADs)
	print("\t\tLanding Pads: %s" % COMM_Object_LPADs)
	print("\t\tLanding Strips: %s" % COMM_Object_LSTPs)
	print("\t\tRings: %s" % COMM_Object_Rings)
	print("\t\tBalloons: %s" % COMM_Object_Balloons)
	print("\t\tRocket Targets: %s" % COMM_Object_Rocket_Targets)
	print("\t\tFloating Pads: %s" % COMM_Object_Floating_Pads)
	print("\t\tBall Targets: %s" % COMM_Object_Ball_Target)
	print("\t\tPhoto Targets: %s" % COMM_Object_Photo_Target)
	print("\t\t\"Falcos Domains\" (Meca Hawk): %s" % COMM_Object_Falcos)
	print("\t\tUNKNOWN: %s" % COMM_Object_Unknown)
	print("\t\tCannon Targets: %s" % COMM_Object_Cannon_Targets)
	print("\t\tJumble Hopper Goals: %s" % COMM_Object_HM_Goals)
	
	#print("** %s" % hex(COMM_Data.tell()))

def CNTG_parser(CNTG_data, length):
	# Seems identical to LPAD/LSTP/TPAD ? Needs more checking.
	CNTG_Data_Start = CNTG_data.tell()

	# Read the Float coordinates
	CNTG_x = CNTG_data.read(4) 		# X
	CNTG_z = CNTG_data.read(4)		# Z
	CNTG_y = CNTG_data.read(4)		# Y
	CNTG_yaw = CNTG_data.read(4)	# Yaw
	CNTG_pitch = CNTG_data.read(4)	# Pitch
	CNTG_roll = CNTG_data.read(4)	# Roll

	UPWT_CNTG_Coordinates_Floats = [round(struct.unpack('>f', CNTG_x)[0],6), 
									round(struct.unpack('>f', CNTG_z)[0],6),
									round(struct.unpack('>f', CNTG_y)[0],6),
									round(struct.unpack('>f', CNTG_yaw)[0],6),
									round(struct.unpack('>f', CNTG_pitch)[0],6),
									round(struct.unpack('>f', CNTG_roll)[0],6)]

	print("\t\tX: %s\n\t\tY: %s\n\t\tZ: %s\n\t\tYaw: %s\n\t\tPitch: %s\n\t\tRoll: %s" % (UPWT_CNTG_Coordinates_Floats[0],
														UPWT_CNTG_Coordinates_Floats[2],
														UPWT_CNTG_Coordinates_Floats[1],
														UPWT_CNTG_Coordinates_Floats[3],
														UPWT_CNTG_Coordinates_Floats[4],
														UPWT_CNTG_Coordinates_Floats[5]))	

def HPAD_parser(HPAD_data, length):
	# Needs verification
	HPAD_Data_Start = HPAD_data.tell()

	# 0x40 bytes per HPAD
	UPWT_HPAD_data = []
	for HPAD in range(1, COMM_Object_Floating_Pads+1):
		UPWT_HPAD_data.append(binascii.b2a_hex(HPAD_data.read(0x40)))

	counter = 0
	for HPAD in UPWT_HPAD_data:
		HPAD = HPAD.decode()
		counter += 1								 
		
		# Groups 8 byte blocks, makes into a list, joins tuple, converts to bytearray from hex. disgusting.
		HPAD_x = bytearray.fromhex(''.join(list(grouper(HPAD, 8, '?'))[0]))
		HPAD_z = bytearray.fromhex(''.join(list(grouper(HPAD, 8, '?'))[1]))
		HPAD_y = bytearray.fromhex(''.join(list(grouper(HPAD, 8, '?'))[2]))
		HPAD_yaw = bytearray.fromhex(''.join(list(grouper(HPAD, 8, '?'))[3]))
		HPAD_pitch = bytearray.fromhex(''.join(list(grouper(HPAD, 8, '?'))[4]))
		HPAD_roll = bytearray.fromhex(''.join(list(grouper(HPAD, 8, '?'))[5]))
		HPAD_number = int(''.join(list(grouper(HPAD, 8, '?'))[10]))

		# Round FP precision to 6 digits		
		UPWT_HPAD_Coordinates_Floats = [round(struct.unpack('>f', HPAD_x)[0],6), 
										round(struct.unpack('>f', HPAD_z)[0],6),
										round(struct.unpack('>f', HPAD_y)[0],6),
										round(struct.unpack('>f', HPAD_yaw)[0],6),
										round(struct.unpack('>f', HPAD_pitch)[0],6)]						

		print("\t\tHPAD # %s:" % counter)
		print("\t\tHPAD Data: ")
		print("\t\t\tArray Index | Data")
		array_index = 0
		for byte_group in ["".join(x) for x in list(grouper(HPAD, 8, '?'))]:
			print("\t\t\t    (%s)       %s" % (array_index, byte_group))
			array_index += 1

		print("\t\t\tHPAD Sequence Number: %s\n\t\t\tX: %s\n\t\t\tY: %s\n\t\t\tZ: %s\n\t\t\tYaw: %s\n\t\t\tPitch: %s" % (HPAD_number,
															UPWT_HPAD_Coordinates_Floats[0],
															UPWT_HPAD_Coordinates_Floats[2],
															UPWT_HPAD_Coordinates_Floats[1],
															UPWT_HPAD_Coordinates_Floats[3],
															UPWT_HPAD_Coordinates_Floats[4]))

def FALC_parser(FALC_data, length):
	# Surprise! This, too, needs verification.
	FALC_Data_Start = FALC_data.tell()

	# 0xAC bytes per FALC
	UPWT_FALC_data = []
	for FALC in range(1, COMM_Object_Falcos+1):
		UPWT_FALC_data.append(binascii.b2a_hex(FALC_data.read(0xAC)))

	counter = 0
	for FALC in UPWT_FALC_data:
		FALC = FALC.decode()
		counter += 1								 
		
		# Groups 8 byte blocks, makes into a list, joins tuple, converts to bytearray from hex. disgusting.
		FALC_x = bytearray.fromhex(''.join(list(grouper(FALC, 8, '?'))[0]))
		FALC_z = bytearray.fromhex(''.join(list(grouper(FALC, 8, '?'))[1]))
		FALC_y = bytearray.fromhex(''.join(list(grouper(FALC, 8, '?'))[2]))
		FALC_yaw = bytearray.fromhex(''.join(list(grouper(FALC, 8, '?'))[3]))
		FALC_pitch = bytearray.fromhex(''.join(list(grouper(FALC, 8, '?'))[4]))
		FALC_roll = bytearray.fromhex(''.join(list(grouper(FALC, 8, '?'))[5]))

		# Round FP precision to 6 digits		
		UPWT_FALC_Coordinates_Floats = [round(struct.unpack('>f', FALC_x)[0],6), 
										round(struct.unpack('>f', FALC_z)[0],6),
										round(struct.unpack('>f', FALC_y)[0],6),
										round(struct.unpack('>f', FALC_yaw)[0],6),
										round(struct.unpack('>f', FALC_pitch)[0],6)]
									

		print("\t\tFALC # %s:" % counter)
		print("\t\tFALC Data: ")
		print("\t\t\tArray Index | Data")
		array_index = 0
		for byte_group in ["".join(x) for x in list(grouper(FALC, 8, '?'))]:
			print("\t\t\t    (%s)       %s" % (array_index, byte_group))
			array_index += 1
				
		print("\t\t\tX: %s\n\t\t\tY: %s\n\t\t\tZ: %s\n\t\t\tYaw: %s\n\t\t\tPitch: %s" % (UPWT_FALC_Coordinates_Floats[0],
															UPWT_FALC_Coordinates_Floats[2],
															UPWT_FALC_Coordinates_Floats[1],
															UPWT_FALC_Coordinates_Floats[3],
															UPWT_FALC_Coordinates_Floats[4]))

def LPAD_LSTP_TPAD_parser(XPAD_data, length):
	XPAD_Data_Start = XPAD_data.tell()

	# Read the Float coordinates
	XPAD_x = XPAD_data.read(4)
	XPAD_z = XPAD_data.read(4)
	XPAD_y = XPAD_data.read(4)
	XPAD_yaw = XPAD_data.read(4)
	XPAD_pitch = XPAD_data.read(4)
	XPAD_roll = XPAD_data.read(4)

	UPWT_XPAD_Coordinates_Floats = [round(struct.unpack('>f', XPAD_x)[0],6), 
									round(struct.unpack('>f', XPAD_z)[0],6),
									round(struct.unpack('>f', XPAD_y)[0],6),
									round(struct.unpack('>f', XPAD_yaw)[0],6),
									round(struct.unpack('>f', XPAD_pitch)[0],6),
									round(struct.unpack('>f', XPAD_roll)[0],6)]

	print("\t\tX: %s\n\t\tY: %s\n\t\tZ: %s\n\t\tYaw: %s\n\t\tPitch: %s\n\t\tRoll: %s" % (UPWT_XPAD_Coordinates_Floats[0],
														UPWT_XPAD_Coordinates_Floats[2],
														UPWT_XPAD_Coordinates_Floats[1],
														UPWT_XPAD_Coordinates_Floats[3],
														UPWT_XPAD_Coordinates_Floats[4],
														UPWT_XPAD_Coordinates_Floats[5]))

def LWIN_parser(LWIN_data, length):
	# Not sure how to parse this one yet... seems "off" somehow
	# What even is a Local Wind?
	LWIN_Data_Start = LWIN_data.tell()

	# First 0x4 bytes always appear as 0x0
	LWIN_data.seek(0x4, 1)
	
	# 0x54 bytes per local wind, n+1? seems like 0x2c + 0x28 sections?
	UPWT_LWIN_Data = []
	for wind in range(1, COMM_Object_LocalWinds+1):
		UPWT_LWIN_Data.append(binascii.b2a_hex(LWIN_data.read(0x54)))

	counter = 0
	for wind in UPWT_LWIN_Data:
		wind = wind.decode()
		counter += 1
		print("\t\tLocal Wind # %s:" % counter)
		print("\t\tLocal Wind Data: ")
		print("\t\t\tArray Index | Data")
		array_index = 0
		for byte_group in ["".join(x) for x in list(grouper(wind, 8, '?'))]:
			print("\t\t\t    (%s)       %s" % (array_index, byte_group))
			array_index += 1

def JPTX_parser(JPTX_data, length):
	test_name = JPTX_data.read(int(length, 16)).decode().rstrip('\0')
	
	# Should probably just do the decoding prior to adding to dict in game_text_builder()?
	# _N = Name / Title
	# _M = Message / Mission
	test_title = "".join(print_adat_decoded(Game_Text_Data[test_name+'_N']))
	test_mission = "".join(print_adat_decoded(Game_Text_Data[test_name+'_M']))

	print("\t\t* Test ID: %s\n" % test_name)
	print("\t\t* Test Name (%s) and Mission Text / Message (%s):" % (test_name + '_N', test_name + '_M'))
	print('\t\t----------------------------------')
	print("\t\t %s" % test_title.rstrip())
	print('\t\t----------------------------------')
	for line in "".join(test_mission).splitlines():
		print ('\t\t %s' % line)
	print('\t\t----------------------------------')

def PHTS_parser(PHTS_data, length):
	# Still needs work, what else is new?
	PHTS_Data_Start = PHTS_data.tell()
	#print("\t\t%s" % binascii.b2a_hex(PHTS_data.read(int(length, 16))))

	UPWT_PHTS_data = []
	for PHTS in range(1, COMM_Object_Photo_Target+1):
		UPWT_PHTS_data.append(binascii.b2a_hex(PHTS_data.read(int(length, 16))))

	counter = 0
	for photo in UPWT_PHTS_data:
		photo = photo.decode()
		counter += 1
		print("\t\tPhoto # %s:" % counter)
		print("\t\t\tArray Index | Data")
		array_index = 0
		for byte_group in ["".join(x) for x in list(grouper(photo, 8, '?'))]:
			print("\t\t\t    (%s)       %s" % (array_index, byte_group))
			array_index += 1

def RNGS_parser(RNGS_data, length):
	# Pretty damn thorough. Spent too much time on this.
	# BUT... (of course there's a but...) still need to figure out Timer rings.
	RNGS_Data_Start = RNGS_data.tell()
	
	# 0x84 bytes per ring
	UPWT_RNGS_Data = []
	for ring in range(1, COMM_Object_Rings+1):
		UPWT_RNGS_Data.append(binascii.b2a_hex(RNGS_data.read(0x84)))

	counter = 0
	for ring in UPWT_RNGS_Data:	
		counter += 1

		# Needed for Python3 because we read() in b'ytes' now.
		ring = ring.decode()

		# Hold our data in 4-byte easy to eat pieces
		RNGS_stack = []

		print("\t\tRing # %s:" % counter)
		print("\t\tRing Data: ")
		print("\t\t\tArray Index | Data")
		array_index = 0
		for byte_group in ["".join(x) for x in list(grouper(ring, 8, '?'))]:
			print("\t\t\t    (%s)       %s" % (array_index, byte_group))
			RNGS_stack.append(byte_group)
			array_index += 1

		# Last number is "Array Index" seen below in Ring Data. Useful for stuff.
		RNGS_x = RNGS_stack[0]
		RNGS_z = RNGS_stack[1]
		RNGS_y = RNGS_stack[2]
		RNGS_yaw = RNGS_stack[3]
		RNGS_pitch = RNGS_stack[4]
		RNGS_roll = RNGS_stack[5]
		RNGS_size_state = RNGS_stack[21]
		RNGS_motion_rad_start = RNGS_stack[22]
		RNGS_motion_rad_end = RNGS_stack[23]
		RNGS_motion_axis = RNGS_stack[24]
		RNGS_spin_speed = RNGS_stack[25]
		RNGS_type = RNGS_stack[28]

		# Round FP precision to 6 digits
		UPWT_RNGS_Coordinates_Floats = [round(struct.unpack('>f', bytes.fromhex(RNGS_x))[0],6),
										round(struct.unpack('>f', bytes.fromhex(RNGS_z))[0],6),
										round(struct.unpack('>f', bytes.fromhex(RNGS_y))[0],6),
										round(struct.unpack('>f', bytes.fromhex(RNGS_yaw))[0],6),
										round(struct.unpack('>f', bytes.fromhex(RNGS_pitch))[0],6)]

		### ToDo: More ring parsing:
		# B_RP_2, 2nd ring is timer, 3rd ring spins on X- axis really fast?
		# Index [13, 14] has something to do with Timed rings?:
		#  "rings: Untimed ring index %d in ring %d's timechild list"
		# Add ring rotation "speed" at 0x8036DC0C, try 00/40
		ring_ss = list(grouper(RNGS_size_state, 2, '?'))
		ring_size = ''.join(ring_ss[0])
		ring_state = ''.join(ring_ss[1])
		print("\t\t\tRing Size (01-04): %s" % ring_size) # 00/05 are invalid: "bad ring size"
		if ring_state == "00":
			print("\t\t\tRing State: Inactive (Closed)")
		elif ring_state == "01":
			print("\t\t\tRing State: Active (Open)")

		#ring_type = list(grouper(binascii.b2a_hex(RNGS_type), 2, '?'))
		ring_type = list(grouper(RNGS_type, 2, '?'))
		print("\t\t\tRing Details:")

		ring_rotation = ''.join(ring_type[0])
		ring_unknown1 = ''.join(ring_type[1])
		ring_special = ''.join(ring_type[2])
		ring_unknown2 = ''.join(ring_type[3])
		
		# Hex:   78 79 7a 6e
		# ASCII: x  y  z  n
		# (thanks pfedak)
		#
		# Motion around axis as seen in B_RP_2 (Ring #10)
		ring_motion_axis = ''.join(list(grouper(RNGS_motion_axis, 2, '?'))[0])
		if ring_motion_axis == "78":
			print("\t\t\t\tMotion: %s (X-Axis)" % ring_motion_axis)
		elif ring_motion_axis == "79":
			print("\t\t\t\tMotion: %s (Y-Axis)" % ring_motion_axis)
		elif ring_motion_axis == "7a":
			print("\t\t\t\tMotion: %s (Z-Axis)" % ring_motion_axis)
		elif ring_motion_axis == "6e":
			print("\t\t\t\tMotion: %s (None)" % ring_motion_axis)
		if ring_motion_axis != "6e":
			print("\t\t\t\t\tMotion Rad Start: %s" % round(struct.unpack('>f', bytes.fromhex(RNGS_motion_rad_start))[0],6))
			print("\t\t\t\t\tMotion Rad End: %s" % round(struct.unpack('>f', bytes.fromhex(RNGS_motion_rad_end))[0],6))

		# Rotation of ring
		if ring_rotation == "78":
			print("\t\t\t\tRotation: %s (X-Axis)" % ring_rotation)
		elif ring_rotation == "79":
			print("\t\t\t\tRotation: %s (Y-Axis)" % ring_rotation)
		elif ring_rotation == "7a":
			print("\t\t\t\tRotation: %s (Z-Axis)" % ring_rotation)
		elif ring_rotation == "6e":
			print("\t\t\t\tRotation: %s (None)" % ring_rotation) # P_RP_1
		if ring_rotation != "6e":
			print("\t\t\t\t\tRotation Speed: %s" % round(struct.unpack('>f', bytes.fromhex(RNGS_spin_speed))[0],6))

		print("\t\t\t\tUnknown1: %s" % ring_unknown1)

		if ring_special == "01":
			print("\t\t\t\tSpecial: %s (Bonus ring)" % ring_special)
		elif ring_special == "02":
			print("\t\t\t\tSpecial: %s ('Hidden' ring)" % ring_special) # You just have to be near it to trigger.
		elif ring_special == "03":
			print("\t\t\t\tSpecial: %s (Multicolored 'GOAL' ring)" % ring_special) # P_RP_1
		else:
			print("\t\t\t\tSpecial: %s (Normal)" % ring_special)
		print("\t\t\t\tUnknown2: %s" % ring_unknown2)
		

		print("\t\t\tX: %s\n\t\t\tY: %s\n\t\t\tZ: %s\n\t\t\tYaw: %s\n\t\t\tPitch: %s" % (UPWT_RNGS_Coordinates_Floats[0],
															UPWT_RNGS_Coordinates_Floats[2],
															UPWT_RNGS_Coordinates_Floats[1],
															UPWT_RNGS_Coordinates_Floats[3],
															UPWT_RNGS_Coordinates_Floats[4]))

def TARG_parser(TARG_data, length):
	# GC Missile targets, e.g. A_GC_2, B_GC_2, P_GC_2 (Balloon Targets)
	global COMM_Object_Rocket_Targets
	TARG_Data_Start = TARG_data.tell()

	# 0x20 bytes per TARG
	UPWT_TARG_data = []
	for TARG in range(1, COMM_Object_Rocket_Targets+1):
		UPWT_TARG_data.append(binascii.b2a_hex(TARG_data.read(0x20)))

	counter = 0
	for TARG in UPWT_TARG_data:	
		counter += 1

		TARG = TARG.decode()
		
		# Groups 8 byte blocks, makes into a list, joins tuple, converts to bytearray from hex. disgusting.
		TARG_x = bytearray.fromhex(''.join(list(grouper(TARG, 8, '?'))[0]))
		TARG_z = bytearray.fromhex(''.join(list(grouper(TARG, 8, '?'))[1]))
		TARG_y = bytearray.fromhex(''.join(list(grouper(TARG, 8, '?'))[2]))
		TARG_yaw = bytearray.fromhex(''.join(list(grouper(TARG, 8, '?'))[3]))
		TARG_pitch = bytearray.fromhex(''.join(list(grouper(TARG, 8, '?'))[4]))
		TARG_roll = bytearray.fromhex(''.join(list(grouper(TARG, 8, '?'))[5]))
		TARG_rotation = bytearray.fromhex(''.join(list(grouper(TARG, 8, '?'))[6]))

		# Round FP precision to 6 digits		
		UPWT_TARG_Coordinates_Floats = [round(struct.unpack('>f', TARG_x)[0],6), 
										round(struct.unpack('>f', TARG_z)[0],6),
										round(struct.unpack('>f', TARG_y)[0],6),
										round(struct.unpack('>f', TARG_yaw)[0],6),
										round(struct.unpack('>f', TARG_pitch)[0],6)]

		print("\t\tTARG # %s:" % counter)
		print("\t\tTARG Data: ")
		print("\t\t\tArray Index | Data")
		array_index = 0
		for byte_group in ["".join(x) for x in list(grouper(TARG, 8, '?'))]:
			print("\t\t\t    (%s)       %s" % (array_index, byte_group))
			array_index += 1
				
		print("\t\t\tX: %s\n\t\t\tY: %s\n\t\t\tZ: %s\n\t\t\tYaw: %s\n\t\t\tPitch: %s" % (UPWT_TARG_Coordinates_Floats[0],
															UPWT_TARG_Coordinates_Floats[2],
															UPWT_TARG_Coordinates_Floats[1],
															UPWT_TARG_Coordinates_Floats[3],
															UPWT_TARG_Coordinates_Floats[4]))
		# 020a0000 = A_GC_2 (Rotating pancake target)
		# 01030000 = B_GC_2 (Non-rotating pancake target)
		# 00010000 = P_GC_2 (Spinning Balloon target)
		if binascii.hexlify(TARG_rotation).decode() == "020a0000":
			print("\t\t\tTarget Always Faces Player: YES")

def THER_parser(THER_data, length):
	global COMM_Object_Thermals
	THER_Data_Start = THER_data.tell()

	# 0x28 bytes per THER
	UPWT_THER_data = []
	for THER in range(1, COMM_Object_Thermals+1):
		UPWT_THER_data.append(binascii.b2a_hex(THER_data.read(0x28)))

	counter = 0
	for THER in UPWT_THER_data:	
		counter += 1								 

		THER = THER.decode()

		# Groups 8 byte blocks, makes into a list, joins tuple, converts to bytearray from hex. disgusting.
		THER_x = bytearray.fromhex(''.join(list(grouper(THER, 8, '?'))[0]))
		THER_z = bytearray.fromhex(''.join(list(grouper(THER, 8, '?'))[1]))
		THER_y = bytearray.fromhex(''.join(list(grouper(THER, 8, '?'))[2]))
		THER_width = bytearray.fromhex(''.join(list(grouper(THER, 8, '?'))[3]))
		THER_height = bytearray.fromhex(''.join(list(grouper(THER, 8, '?'))[4]))
		THER_roll = bytearray.fromhex(''.join(list(grouper(THER, 8, '?'))[5]))

		# Round FP precision to 6 digits		
		UPWT_THER_Coordinates_Floats = [round(struct.unpack('>f', THER_x)[0],6), 
										round(struct.unpack('>f', THER_z)[0],6),
										round(struct.unpack('>f', THER_y)[0],6),
										round(struct.unpack('>f', THER_width)[0],6),
										round(struct.unpack('>f', THER_height)[0],6)]
									

		print("\t\tTHER # %s:" % counter)
		print("\t\tTHER Data: ")
		print("\t\t\tArray Index | Data")
		array_index = 0
		for byte_group in ["".join(x) for x in list(grouper(THER, 8, '?'))]:
			print("\t\t\t    (%s)       %s" % (array_index, byte_group))
			array_index += 1
				
		print("\t\t\tX: %s\n\t\t\tY: %s\n\t\t\tZ: %s\n\t\t\t\n\t\t\tWidth: %s\n\t\t\tHeight: %s\n" % (UPWT_THER_Coordinates_Floats[0],
															UPWT_THER_Coordinates_Floats[2],
															UPWT_THER_Coordinates_Floats[1],
															UPWT_THER_Coordinates_Floats[3],
															UPWT_THER_Coordinates_Floats[4]))

# Reads, unpacks TABL (FS layout)
def unpack_full_tabl():
	with open (PW64_Rom, 'rb') as pw64_rom:
		global fs_table
		pw64_tabl_mio0_data_start = 0xDE758 # Never changes
		pw64_fs_start = 0xDF5B0 # Offset of first file in "File System" (UVSY)

		# Get expected MIO0 uncompressed size
		pw64_rom.seek(int(pw64_tabl_mio0_data_start), 0)
		pw64_tabl_uncompressed_size = int(binascii.b2a_hex(pw64_rom.read(4)),16)

		# Go back 8 bytes to start of MIO0 compressed TABL data (skip futzing with FORM/GZIP/TABL/etc "chunks")
		pw64_rom.seek(-8, 1)

		# MIO0 data length == 0xe58 + MIO0 (marker) = 0xe5c
		# Read in the whole block, decompress MIO0 and convert to hex stream
		uncompressed_data = decompress_mio0(pw64_rom.read(int(0xe5c))).hex()

		# Build a list of 16-character "groups" which denote "files" (file type + file size)
		file_count = len(list(grouper(uncompressed_data, 16, '?')))

		fs_index = 0
		location = pw64_fs_start
		for filenum in range(0, file_count):
			# 16-character groups will hold our File Type and File Size to be later translated to Hex.
			data = ''.join(list(grouper(uncompressed_data, 16, '?'))[filenum])

			# Decoded File Type and File Size for printing
			file_type = binascii.unhexlify(data[0:8]).decode()
			file_size = int(data[9:16], 16)

			fs_table.update( {fs_index: [file_type, hex(location), file_size]})

			fs_index += 1
			location = location + file_size

	pw64_rom.close()
	return fs_table

# Copied from, and credit to, queueRAM: https://github.com/queueRAM/pilotwings_64/blob/master/pw64_filesys_dump.py
def decompress_mio0(raw_bytes):
	magic = raw_bytes[:4]
	assert magic == b'MIO0'

	uncompressed_size, lengths_offs, data_offs = struct.unpack('>LLL', raw_bytes[4:16])
	flags_offs = 0x10

	output = b""
	while True:
		command_byte = raw_bytes[flags_offs]
		flags_offs += 1

		for i in reversed(range(8)):
			if command_byte & (1 << i):
				# Literal
				uncompressed_size -= 1
				output += bytes([raw_bytes[data_offs]])
				data_offs += 1
			else:
				# LZSS
				tmp, = struct.unpack('>H', raw_bytes[lengths_offs:lengths_offs+2])
				lengths_offs += 2

				window_offset = (tmp & 0x0FFF) + 1
				window_length = (tmp >> 12) + 3
				uncompressed_size -= window_length
				for j in range(window_length):
					output += bytes([output[-window_offset]])

			if uncompressed_size <= 0:
				return output

if __name__== "__main__":
  main()
