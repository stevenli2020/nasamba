#!/usr/bin/python3

import os
import subprocess
import _thread
import time
import json
import random
import atexit
import socket
import base64
import signal

CONNECTIONS = {}
TUNNEL = {}
EXITING = False

if os.path.exists("/root/usb_drive/username"):
	with open("/root/usb_drive/username") as f:
		USER = f.read().strip()
else:
	USER = "Noname"
if not os.path.isdir("/root/usb_drive/mnt/"+USER):
	os.mkdir("/root/usb_drive/mnt/"+USER)		

def cleaup(signum, frame):
	global CONNECTIONS,TUNNEL,USER,EXITING
	if not EXITING:
		EXITING = True
		print("Cleaning up ...")
		time.sleep(1)
		for UUID in CONNECTIONS:
			subprocess.run(['umount', '-l', "/root/usb_drive/mnt/"+USER+"/"+UUID], stdout=subprocess.PIPE)
			print("Umounted: %s" %("/root/usb_drive/mnt/"+USER+"/"+UUID))
		if 'proc' in TUNNEL:
			TUNNEL["proc"].terminate()
			print("Connections terminated at server port "+str(TUNNEL["port"]))					
		print("Exit")
		exit(1)

def hostname_resolves(hostname):
    try:
        socket.gethostbyname(hostname)
        return True
    except socket.error:
        return False
		
def main():
	global TUNNEL
	BLK_JSON = '{"blockdevices":[]}' 
	# print(BLK_JSON)
	print("Checking network ...")
	while not hostname_resolves('kgc.sbox.sg'):
		print("Network not ready")
		time.sleep(5)
	print("Network ready!")

	while 1:
		BLK_JSON_NEW = subprocess.run(['lsblk','-JiI8','-oUUID,NAME,TYPE,LABEL,MOUNTPOINT','-xUUID'], stdout=subprocess.PIPE).stdout.decode('utf-8')
		if BLK_JSON_NEW == "":
			BLK_JSON_NEW = '{"blockdevices":[]}'
		if BLK_JSON_NEW != BLK_JSON:
			_thread.start_new_thread(process,(BLK_JSON,BLK_JSON_NEW))
			BLK_JSON = BLK_JSON_NEW
		time.sleep(3)
		# print("[CONNECTIONS]:",CONNECTIONS,"\n[TUNNEL]:",TUNNEL)
		if len(CONNECTIONS)==0 and "proc" in TUNNEL:
			TUNNEL["proc"].terminate()
			TUNNEL={}

def process(BLK0, BLK1):
	global TUNNEL
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
		if "proc" not in TUNNEL:
			_thread.start_new_thread(tunneling,())
		while "port" not in TUNNEL:
			time.sleep(0.5)
		print("Tunnel connected")
		for UUID,DEV in D1.items():
			if UUID not in D0:
				print(DEV)
				if DEV["mountpoint"]!=None:
					print(DEV["mountpoint"])
					if os.path.isdir(DEV["mountpoint"]):
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

				
def tunneling():
	global TUNNEL
	SERVER_PROBE = "00000000"
	PORT = 0
	while str(PORT) in SERVER_PROBE:
		PORT = random.randint(60001,65000)
		SERVER_PROBE = subprocess.run(['ssh','samba@kgc.sbox.sg','netstat','-ntl'], stdout=subprocess.PIPE).stdout.decode('utf-8')	
	TUNNEL["connected"] = True
	TUNNEL["port"] = PORT
	print("Tunnel established at server port "+str(TUNNEL["port"]))
	TUNNEL["proc"]=subprocess.Popen(['ssh', '-oServerAliveInterval=20', '-NR'+str(PORT)+':localhost:22','samba@kgc.sbox.sg'])
	print("Tunnel terminated at server port "+str(PORT))

def create_server_link(DEV):
	global CONNECTIONS,TUNNEL,USER
	UUID = DEV['uuid']
	if DEV['label'] == None:
		DEV['label'] = DEV['uuid']
	SERVER_MNT_POINT = '/home/samba/mnt/'+USER+'/'+DEV['label'].replace(" ","_")
	CONNECTIONS[UUID]['server_mountpoint']=SERVER_MNT_POINT
	CONNECTIONS[UUID]["mountpoint"] = DEV['mountpoint']	
	CONNECTIONS[UUID]["user"] = USER
	CONNECTIONS[UUID]["port"] = TUNNEL["port"]
	CONNECTIONS[UUID]["label"] = DEV['label']
	print("Creating server file system mounted at: "+SERVER_MNT_POINT)
	CONN = json.dumps(CONNECTIONS[UUID]).encode("utf-8")
	CONNECTIONS[UUID]["proc"]=subprocess.Popen(['ssh','samba@kgc.sbox.sg','/usr/bin/python3','/home/samba/smbsvc.py',base64.b64encode(CONN)])
	# print(stdout.decode('utf-8'))
	# print(base64.b64encode(CONN))
	while "proc" in CONNECTIONS[UUID]:
		time.sleep(2)
	print("Link disconnected")

	
def establish_connections(DEV):
	global CONNECTIONS,TUNNEL,USER
	UUID = DEV['uuid']
	CONNECTIONS[UUID]={}
	CONNECTIONS[UUID]['exit_flag']=False
	while not CONNECTIONS[UUID]['exit_flag']:
		MOUNT_POINT = "/root/usb_drive/mnt/"+USER+"/"+UUID
		SYS_PATH = "/dev/"+DEV['name']
		if not os.path.isdir(MOUNT_POINT):
			os.mkdir(MOUNT_POINT)
		subprocess.run(['mount', SYS_PATH, MOUNT_POINT], stdout=subprocess.PIPE)
		DEV["mountpoint"] = MOUNT_POINT
		print("Mounted: %s ---> %s" %(SYS_PATH,MOUNT_POINT))	
		_thread.start_new_thread(create_server_link,(DEV,))
		while TUNNEL["connected"] and CONNECTIONS[UUID]['exit_flag']!=True:
			time.sleep(1)
		SYS_PATH = "/dev/"+DEV['name']	
		subprocess.run(['umount', '-l', DEV['mountpoint']], stdout=subprocess.PIPE)
		print("Umounted local: %s -x-> %s" %(SYS_PATH,DEV['mountpoint']))
		del CONNECTIONS[UUID]["mountpoint"]
		print("Umounted server: %s -x-> %s" %(SYS_PATH,CONNECTIONS[UUID]["server_mountpoint"]))
		del CONNECTIONS[UUID]["server_mountpoint"]
		CONNECTIONS[UUID]["proc"].terminate()
		del CONNECTIONS[UUID]["proc"]
		time.sleep(2)
	del CONNECTIONS[UUID]
		

	
atexit.register(cleaup, None, None)
signal.signal(signal.SIGTERM, cleaup)
signal.signal(signal.SIGINT, cleaup)	
			
if __name__ == '__main__':
	main()
	
