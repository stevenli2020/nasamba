#!/usr/bin/python3

import os
import sys
import subprocess
import time
import json
import atexit
import signal
import base64
import random
import _thread

CONN = json.loads(base64.b64decode(sys.argv[1]))
PORT = 0
CLIENT_MNT = ""
SERVER_MNT = ""
FS_READY = False
EXITING = False
# print(CONN)

def handle_exit(signum, frame):
	global PORT,CLIENT_MNT,SERVER_MNT,SMB_CONF,LABEL,EXITING
	if not EXITING:
		EXITING = True
		DELAY = random.randint(0,10)/10
		time.sleep(DELAY)
		subprocess.run(['sudo', 'umount', SERVER_MNT], stdout=subprocess.PIPE)
		subprocess.run(['sudo', 'rm','-rf',SERVER_MNT], stdout=subprocess.PIPE)
		with open('/home/samba/conf/smb.conf', "r+") as f:
			data = f.read()
			data1 = delete_conf_entry(data, LABEL)
			f.seek(0)
			f.write(data1)
			f.truncate()	
		subprocess.run(['sudo','docker','restart','smb'], stdout=subprocess.PIPE)
		print("Clean exit")
		exit(1)
	else:
		exit(1)

def delete_conf_entry(CONF, ENTRY):
	C = CONF
	p1 = C.find("[@"+ENTRY,0)
	if p1 == 0:
		p1 = 1
	while p1 != -1:
		p2 = C.find("\n[",p1+2)
		C = C[:p1-1] + C[p2:]
		p1 = C.find("[@"+ENTRY,0)
	return C
	
atexit.register(handle_exit, None, None)


PORT = CONN["port"]
USER = CONN["user"]
LABEL = CONN["label"].replace(" ","_")
CLIENT_MNT = CONN["mountpoint"]
SERVER_MNT = CONN["server_mountpoint"]
if not os.path.exists('/home/samba/mnt/'+USER):
	subprocess.run(['sudo','mkdir','-p','/home/samba/mnt/'+USER], stdout=subprocess.PIPE)
if not os.path.exists(SERVER_MNT):
	# subprocess.run(['sudo','umount',SERVER_MNT], stdout=subprocess.PIPE)
	subprocess.run(['sudo','mkdir','-p',SERVER_MNT], stdout=subprocess.PIPE)
result = subprocess.run(['sudo','sshfs','-p'+str(PORT),'-oallow_other','-oStrictHostKeyChecking=no','-oreconnect,ServerAliveInterval=15,ServerAliveCountMax=3','root@localhost:'+CLIENT_MNT,SERVER_MNT], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
if result.stderr.decode('utf-8') != "":
	print(result.stderr.decode('utf-8'))
	exit()
time.sleep(1)
SMB_CONF = "\n[@"+LABEL+"]\n   path = /usr_mnt/"+USER+"/"+LABEL+"\n   browsable = yes\n   writeable = yes\n   read only = no\n   guest ok = no\n   valid users = "+USER+" \n   write list = "+USER+"\n   force user = root\n\n"
with open('/home/samba/conf/smb.conf', "a") as f:
	f.write(SMB_CONF)

subprocess.run(['sudo','docker','restart','smb'], stdout=subprocess.PIPE)
pppid = 0
while pppid != 1:
	ppid = os.getppid()
	pppid = int(subprocess.run(['ps','-o','ppid=',str(ppid)], stdout=subprocess.PIPE).stdout.decode('utf-8'))
	time.sleep(2)

