#!/usr/bin/python3

import websocket
import requests
from signal import signal,alarm,SIGALRM
import json
import sys


##############################
#
#  options, parameters
#
##############################

SHOWSEP=False
SHOWALL=False
SUBALL=False
SHOWG=True
SHOWEV=True
SHOWTEMP=False
VERB=0

OCTOCMDCONF='/etc/octocmd.conf'

SENDCMD=''
WAITCMD=''
TIMEOUT=0



##############################
#
#  timeout handler
#
##############################

def alrmhandler(signum,frame):
    ws.close()

def settimeout(to):
    if VERB>0: print('Setting timeout to:',to)
    signal(SIGALRM, alrmhandler)
    alarm(to)



##############################
#
#  websocket handling
#
##############################

# receive message
def on_message(ws, message):
    if SHOWSEP: print('====')
    j=json.loads(message)
    if SHOWALL or VERB>1:
      print(message)
      if SHOWALL: return
    # show gcode
    if SHOWG:
      if 'current' in j:
        if 'logs' in j['current']:
          a=j['current']['logs']
          for x in a: printglog(x)
    # show events
    if SHOWEV:
      if 'event' in j:
        print(j)


def on_error(ws, error):
    if VERB>=0 or error>0: print('### ERROR:',str(error),type(error))

def on_close(ws, close_status_code, close_msg):
    if VERB>=0: print("### closed ###")


def on_open(ws):
    if VERB>=0: print("### Opened connection")
    if not SUBALL:
      #ws.send('{"subscribe":{"events":true,"plugins":false}}')
      ws.send('{"subscribe":{"state":{"logs":true,"messages":false},"events":true,"plugins":false}}')

    # if we wait for command, make sure we don't wait too long
    if TIMEOUT>0: settimeout(TIMEOUT)

    # authorize to receive messages, send command if set
    ws.send(wsauthcmd)
    if SENDCMD!='': apigcode(SENDCMD)



##############################
#
#  octoprint command HTTP API
#
##############################

def apireq(url,json):
  if VERB>0:
     print('HTTPREQ:',loginurl+url)
     print('   JSON:',json)
     print('    HDR:',loginhdr)
  r=requests.post(loginurl+url,timeout=6,verify=False,json=json,headers=loginhdr)
  if VERB>0: print('  =>',r.content)
  return r.content


def apilogin():
  return apireq('/api/login?passive=true',{})

def apigcode(gcmd):
  return apireq('/api/printer/command',{'command':gcmd})



##############################
#
#  data output, full or waitcmd
#
##############################

gstate=0
def printglog_wait(s):
  global gstate
  if s[:9]=='Recv:  T:': return
  if gstate==0:
    if s.upper()=='SEND: '+WAITCMD.upper():
      if VERB>0: print('GWAIT:',s)
      gstate=1
    else: return
  if gstate==1:
    print(s)
    if s=='Recv: ok':
      gstate=2
      ws.close()

def printglog(s):
  if WAITCMD!='':
    printglog_wait(s)
    return
  if not SHOWTEMP:
    if s[:9]=='Recv:  T:': return
  print(s)




##############################
#
#  commandline arguments, help
#
##############################

def help():
  print('Usage: {} [-a] [-s] [-v] [-v] [-v] [-tTIMEOUT] [-C/config/file] [command]'.format(sys.argv[0]))
  print('Parameters:')
  print('  -a        show all messages')
  print('  -s        show separators between messages')
  print('  -v        increase verbosity, up to 2 times')
  print('  -t<num>   timeout in seconds')
  print('  -C/file   config file location, default '+OCTOCMDCONF)
  print('  -h        this help')
  print('  --help    this help')
  print('  command   gcode command to get the response')
  print('')
  sys.exit(0)


#if len(sys.argv)>1:
for t in range(1,len(sys.argv)):
  #print('arg:',sys.argv[t])
  if sys.argv[t]=='-a': SHOWALL=True
  if sys.argv[t]=='-s': SHOWSEP=True
  if sys.argv[t]=='-v': VERB=VERB+1
  if sys.argv[t]=='-h': help()
  if sys.argv[t]=='--help': help()
  if sys.argv[t][:2]=='-t': TIMEOUT=int(sys.argv[t][2:])
  if sys.argv[t][:2]=='-C' and len(sys.argv[t])>2: OCTOCMDCONF=sys.argv[t][2:]
  if sys.argv[t][0]!='-':
    if len(SENDCMD)>0: SENDCMD=SENDCMD+' '
    SENDCMD=SENDCMD+sys.argv[t]

SENDCMD=SENDCMD.upper()
WAITCMD=SENDCMD
if SENDCMD!='':
  if VERB==0: VERB=-1
  if TIMEOUT==0: TIMEOUT=20



##############################
#
#  main process
#
##############################

# read config file
octoconfstr=open(OCTOCMDCONF).read()
octoconf=json.loads(octoconfstr)
if VERB>1:print('#### octoconf:',octoconf)

# prepare URL and API key header into global vars
loginurl=octoconf['OctoPrint_URL']
loginhdr={"X-Api-Key":octoconf['OctoAPI_KEY']}

# run API login
r=apireq('/api/login?passive=true',{})

# parse login response
loginresp=json.loads(r)
if VERB>1:
  print(loginresp)
  print('Name:',loginresp['name'])
  print('Session:',loginresp['session'])
wsauthcmd=json.dumps({'auth':loginresp['name']+':'+loginresp['session']})
if VERB>1: print('### auth cmd:',wsauthcmd)

# form the websocket address
if loginurl[:4]=='http': wsurl=loginurl[4:]
else: wsurl=loginurl
wsurl='ws'+wsurl+'/sockjs/websocket'

# open websocket
if VERB>=0: print('### Opening websocket to:',wsurl)
ws = websocket.WebSocketApp(wsurl,
                              on_open=on_open,
                              on_message=on_message,
                              on_error=on_error,
                              on_close=on_close  )

# show what we are waiting for
if VERB>=0:
  wfor=''
  if SHOWEV:
    wfor='events'
  if SHOWG:
    if wfor!='': wfor=wfor+', '
    wfor=wfor+'gcode'
  print('### waiting for',wfor)

# run websocket receive loop
ws.run_forever()

