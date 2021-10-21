#!/usr/bin/python3

import functools
import os
import subprocess
import _thread
import time
import json
import random
import atexit


CONNECTIONS = {}

def cleaup():
	global CONNECTIONS
	print("Cleaning up ...")
	# print(CONNECTIONS)
	time.sleep(1)
	for UUID in CONNECTIONS:
		print(CONNECTIONS[UUID])
		if "port" in CONNECTIONS[UUID]:
			subprocess.run(['pkill', '-f', "NR"+str(CONNECTIONS[UUID]['port'])], stdout=subprocess.PIPE)
			print("Connections terminated at server port "+str(CONNECTIONS[UUID]["port"]))
		if "mountpoint" in CONNECTIONS[UUID]:
			subprocess.run(['umount', '-l', "./mnt/"+UUID], stdout=subprocess.PIPE)
			print("Umounted: %s" %("./mnt/"+UUID))	
		if "server_mountpoint" in CONNECTIONS[UUID]:
			SERVER_MNT_POINT = CONNECTIONS[UUID]["server_mountpoint"]
			subprocess.run(['ssh','samba@kgc.sbox.sg','sudo','umount', SERVER_MNT_POINT], stdout=subprocess.PIPE)
			print("Umounted server: %s" %(SERVER_MNT_POINT))
			subprocess.run(['ssh','samba@kgc.sbox.sg','sudo','rm','-rf',SERVER_MNT_POINT], stdout=subprocess.PIPE)		
	print("Exit")
	
def main():
	BLK_JSON = '{"blockdevices":[]}' 
	# print(BLK_JSON)
	while 1:
		BLK_JSON_NEW = subprocess.run(['lsblk','-JiI8','-oUUID,NAME,TYPE,LABEL,MOUNTPOINT','-xUUID'], stdout=subprocess.PIPE).stdout.decode('utf-8')
		if BLK_JSON_NEW == "":
			BLK_JSON_NEW = '{"blockdevices":[]}'	
		# print(BLK_JSON_NEW)
		if BLK_JSON_NEW != BLK_JSON:
			_thread.start_new_thread(process,(BLK_JSON,BLK_JSON_NEW))
			BLK_JSON = BLK_JSON_NEW
		time.sleep(2)

def process(BLK0, BLK1):
	# print(BLK0, BLK1)
	D0 = {}
	D1 = {}
	O = json.loads(BLK0)["blockdevices"]
	N = json.loads(BLK1)["blockdevices"]
	for dev in O:
		if dev['uuid'] != None:
			D0[dev['uuid']] = dev
	for dev in N:
		if dev['uuid'] != None:
			D1[dev['uuid']] = dev	
	# print(D1)
	if len(D1) > len(D0):
		print("Usb storage added")
		for UUID,DEV in D1.items():
			if UUID not in D0:
				print(DEV)
				if DEV["mountpoint"]!=None:
					print(DEV["mountpoint"])
					subprocess.run(['umount', '-l', DEV["mountpoint"]], stdout=subprocess.PIPE)
					time.sleep(1)
				_thread.start_new_thread(establish_connections,(DEV,))
	elif len(D1) < len(D0):
		print("Usb storage removed")
		for UUID,DEV in D0.items():
			if UUID not in D1:
				print(DEV)
				CONNECTIONS[UUID]["connected"] = False
				CONNECTIONS[UUID]['exit_flag'] = True

def tunneling(DEV):
	global CONNECTIONS
	UUID = DEV['uuid']
	SERVER_PROBE = "00000000"
	PORT = 0
	while str(PORT) in SERVER_PROBE:
		PORT = random.randint(60001,65000)
		SERVER_PROBE = subprocess.run(['ssh','samba@kgc.sbox.sg','netstat','-ntl'], stdout=subprocess.PIPE).stdout.decode('utf-8')	
	CONNECTIONS[UUID]["connected"] = True
	CONNECTIONS[UUID]["port"] = PORT
	print("Connections established at server port "+str(PORT))
	subprocess.run(['ssh', '-NR'+str(PORT)+':localhost:22','samba@kgc.sbox.sg'])
	CONNECTIONS[UUID]["connected"] = False
	del CONNECTIONS[UUID]["port"]
	print("Connections terminated at server port "+str(PORT))
	
	
def establish_connections(DEV):
	global CONNECTIONS
	UUID = DEV['uuid']
	CONNECTIONS[UUID]={}
	CONNECTIONS[UUID]['exit_flag']=False
	print(UUID)
	while not CONNECTIONS[UUID]['exit_flag']:
		MOUNT_POINT = os.getcwd()+"/mnt/"+UUID
		SYS_PATH = "/dev/"+DEV['name']
		if not os.path.isdir(MOUNT_POINT):
			os.mkdir(MOUNT_POINT)
		subprocess.run(['mount', SYS_PATH, MOUNT_POINT], stdout=subprocess.PIPE)
		DEV["mountpoint"] = MOUNT_POINT
		print("Mounted: %s ---> %s" %(SYS_PATH,MOUNT_POINT))	
		_thread.start_new_thread(tunneling,(DEV,))
		time.sleep(1)
		SERVER_MNT_POINT = '/home/samba/mnt/'+DEV['label'].replace(" ","_")
		CONNECTIONS[UUID]['server_mountpoint']=SERVER_MNT_POINT
		CONNECTIONS[UUID]["mountpoint"] = DEV['mountpoint']
		subprocess.run(['ssh','samba@kgc.sbox.sg','sudo','mkdir','-p',SERVER_MNT_POINT], stdout=subprocess.PIPE)
		subprocess.run(['ssh','samba@kgc.sbox.sg','sudo','sshfs','-p'+str(CONNECTIONS[UUID]["port"]),'-oallow_other','-oStrictHostKeyChecking=no','root@localhost:/root/usb_drive/mnt/'+UUID,SERVER_MNT_POINT], stdout=subprocess.PIPE)
		print("Server file system mounted at: "+SERVER_MNT_POINT)
		subprocess.run(['ssh','samba@kgc.sbox.sg','sudo','docker','restart','smb'], stdout=subprocess.PIPE)
		while CONNECTIONS[UUID]["connected"]:
			time.sleep(1)
		SYS_PATH = "/dev/"+DEV['name']	
		subprocess.run(['umount', '-l', DEV['mountpoint']], stdout=subprocess.PIPE)
		print("Umounted local: %s -x-> %s" %(SYS_PATH,DEV['mountpoint']))
		del CONNECTIONS[UUID]["mountpoint"]
		subprocess.run(['ssh','samba@kgc.sbox.sg','sudo','umount', SERVER_MNT_POINT], stdout=subprocess.PIPE)
		print("Umounted server: %s -x-> %s" %(SYS_PATH,SERVER_MNT_POINT))
		del CONNECTIONS[UUID]["server_mountpoint"]
		subprocess.run(['ssh','samba@kgc.sbox.sg','sudo','rm','-rf',SERVER_MNT_POINT], stdout=subprocess.PIPE)
		subprocess.run(['ssh','samba@kgc.sbox.sg','sudo','docker','restart','smb'], stdout=subprocess.PIPE)
		time.sleep(2)

	
atexit.register(cleaup)				
if __name__ == '__main__':
	main()
	
