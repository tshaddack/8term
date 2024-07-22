#!/usr/bin/python3

import websocket
import requests
import json
import sys

from threading import Thread

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.styles import Style as ptStyle
from prompt_toolkit.widgets import SearchToolbar, TextArea


# max bytes in the output buffer
TERMLIMIT=50000



help_text = """
Type gcode statements followed by enter to execute.
Press Control-C to exit.


"""



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
#  syntax colors, gcode lexer
#
##############################

from prompt_toolkit.lexers import PygmentsLexer
import pygments.token as p
from pygments.lexer import RegexLexer, bygroups
from pygments.style import Style as pgStyle

class xgstyle(pgStyle):
    styles = {
        p.Token:                     "#808080",       # gray
        p.Whitespace:                "",
        p.Comment:                   "#0000ff",       # dkblue
        p.Comment.Preproc:           "",
        p.Comment.Special:           "bold #cd0000",  # red

        p.Keyword:                   "#cdcd00",       # yellow
        p.Keyword.Declaration:       "#00cd00",       # green
        p.Keyword.Namespace:         "#cd00cd",       # purple
        p.Keyword.Pseudo:            "",
        p.Keyword.Type:              "#00cd00",       # green

        p.Operator:                  "#3399cc",       # cyan?
        p.Operator.Word:             "#cdcd00",       # yellow

        p.Name:                      "",
        p.Name.Class:                "#00cdcd",       # cyan
        p.Name.Builtin:              "#cd00cd",       # purple
        p.Name.Exception:            "bold #666699",  # lightblue
        p.Name.Variable:             "#00cdcd",       # cyan

        p.String:                    "#cd0000",       # red
        p.Number:                    "#008080",       # purple

        p.Generic.Heading:           "bold #000080",
        p.Generic.Subheading:        "bold #800080",
        p.Generic.Deleted:           "#cd0000",
        p.Generic.Inserted:          "#00cd00",
        p.Generic.Error:             "#FF0000",
        p.Generic.Emph:              "italic",
        p.Generic.Strong:            "bold",
        p.Generic.Prompt:            "bold #000080",
        p.Generic.Output:            "#888",
        p.Generic.Traceback:         "#04D",

        p.Error:                     "border:#FF0000"
    }


class GtermLexer(RegexLexer):
    """
    For gcode source code.
    .. versionadded:: 2.9
    """
    name = 'g-code'
    aliases = ['gcode']
    filenames = ['*.gcode']

    tokens = {
        'root': [
            (r';.*\n', p.Comment),
            (r'^Recv: ok\n', p.Generic.Traceback),
            (r'^(Recv: echo:)(.*\n)', bygroups(p.Generic.Deleted, p.Keyword)),
            (r'^(Recv:)(.*\n)', bygroups(p.Generic.Deleted, p.Number)),
            (r'^Send:', p.Generic.Inserted),
#            (r'^Send: [gmGMN]\d{1,5}\s', p.Name.Builtin),  # M or G commands
            (r'([a-zA-Z])([+-]?\d*[.]?\d+)', bygroups(p.Keyword, p.Number)),
            (r'^Send: (N[0-9]{1,6})', p.Operator ),
            (r'(\*.*\n)', p.Generic.Heading),
#            (r'(\*)([0-9][0-9]\n)', bygroups(p.Comment, p.Number)),
#            (r'^Send:', p.Name.Builtin),  # M or G commands
            (r'\s', p.Text.Whitespace),
            (r'^Send:',p.Literal),
            (r'^>>>>>.*',p.Keyword),
            (r'^(EVENT:)(.*\n)', bygroups(p.Generic.Deleted, p.Number)),
            (r'\#.*\n', p.Keyword),
            (r'\{.*\}\n', p.Generic.Output),
            (r'.*\n', p.Token),
        ]
    }




##############################
#
#  websocket
#
##############################

def ws_on_message(ws, message):
    if SHOWSEP: addtxt('====')
    j=json.loads(message)
    if SHOWALL or VERB>1:
      addtxt(message)
      if SHOWALL: return
    if SHOWG:
      if 'current' in j:
        if 'logs' in j['current']:
          a=j['current']['logs']
          for x in a: printglog(x)
    if SHOWEV:
      if 'event' in j:
        addtxt('EVENT:'+message)


def ws_on_error(ws, error):
    if VERB>=0 or error>0: addtxt('### ERROR: '+str(error))

def ws_on_close(ws, close_status_code, close_msg):
    if VERB>=0: print("### closed ###")




def ws_on_open(ws):
    if VERB>=0: addtxt("### Opened connection")
    #application._invalidated=True # force screen refresh
    if not SUBALL:
      #ws.send('{"subscribe":{"events":true,"plugins":false}}')
      ws.send('{"subscribe":{"state":{"logs":true,"messages":false},"events":true,"plugins":false}}')

    ws.send(wsauthcmd)
    if SENDCMD!='': apigcode(SENDCMD)



def run_ws_task():
  ws.run_forever()



##############################
#
#  Octoprint API HTTP request
#
##############################

def apireq(url,json):
  if VERB>0:
     addtxt('HTTPREQ: '+loginurl+url)
     addtxt('   JSON: '+str(json))
     addtxt('    HDR: '+str(loginhdr))
  r=requests.post(loginurl+url,timeout=6,verify=False,json=json,headers=loginhdr)
  if VERB>0:
     addtxt('      => '+str(r.content))
  return r.content

def apilogin():
  return apireq('/api/login?passive=true',{})

def apigcode(gcmd):
  return apireq('/api/printer/command',{'command':gcmd})

def apijob(cmd,act):
  if act=='': return apireq('/api/job',{'command':cmd})
  return apireq('/api/job',{'command':cmd,'action':act})




##############################
#
#  screen output
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
      #sys.exit(0)


def printglog(s):
#  if WAITCMD!='':
#    printglog_wait(s)
#    return
  if not SHOWTEMP:
    if s[:9]=='Recv:  T:': return
#  print('G:',s)
  addtxt(s)









##############################
#
#  help, commandline options
#
##############################

def help():
  print('Usage: {} [-a] [-s] [-v] [-v] [-v] [-tTIMEOUT] [-C/config/file] [command]'.format(sys.argv[0]))
  print('Parameters:')
#  print('  -a        show all messages')
#  print('  -s        show separators between messages')
  print('  -v        increase verbosity, up to 2 times')
#  print('  -t<num>   timeout in seconds')
  print('  -C/file   config file location, default '+OCTOCMDCONF)
  print('  -h        this help')
  print('  --help    this help')
  print('  command   gcode command to get the response')
  print('')
  sys.exit(0)


for t in range(1,len(sys.argv)):
#  if sys.argv[t]=='-a': SHOWALL=True
#  if sys.argv[t]=='-s': SHOWSEP=True
  if sys.argv[t]=='-v': VERB=VERB+1
  if sys.argv[t]=='-h': help()
  if sys.argv[t]=='--help': help()
#  if sys.argv[t][:2]=='-t': TIMEOUT=int(sys.argv[t][2:])
  if sys.argv[t][:2]=='-C' and len(sys.argv[t])>2: OCTOCMDCONF=sys.argv[t][2:]
  if sys.argv[t][0]!='-':
    if len(SENDCMD)>0: SENDCMD=SENDCMD+' '
    SENDCMD=SENDCMD+sys.argv[t]

SENDCMD=SENDCMD.upper()
#WAITCMD=SENDCMD
#if SENDCMD!='':
#  if VERB==0: VERB=-1
#  if TIMEOUT==0: TIMEOUT=20







# textarea:
#    def __init__(
#        self,
#        text: str = "",
#        multiline: FilterOrBool = True,
#        password: FilterOrBool = False,
#        lexer: Optional[Lexer] = None,
#        auto_suggest: Optional[AutoSuggest] = None,
#        completer: Optional[Completer] = None,
#        complete_while_typing: FilterOrBool = True,
#        validator: Optional[Validator] = None,
#        accept_handler: Optional[BufferAcceptHandler] = None,
#        history: Optional[History] = None,
#        focusable: FilterOrBool = True,
#        focus_on_click: FilterOrBool = False,
#        wrap_lines: FilterOrBool = True,
#        read_only: FilterOrBool = False,
#        width: AnyDimension = None,
#        height: AnyDimension = None,
#        dont_extend_height: FilterOrBool = False,
#        dont_extend_width: FilterOrBool = False,
#        line_numbers: bool = False,
#        get_line_prefix: Optional[GetLinePrefixCallable] = None,
#        scrollbar: bool = False,
#        style: str = "",
#        search_field: Optional[SearchToolbar] = None,
#        preview_search: FilterOrBool = True,
#        prompt: AnyFormattedText = "",
#        input_processors: Optional[List[Processor]] = None,
#    ) -> None:
#



##############################
#
#  colors, styles, lexer
#
##############################

#from glex import xgstyle
#style_pyg=xgstyle

from prompt_toolkit.styles.pygments import style_from_pygments_cls
from prompt_toolkit.styles import merge_styles

style_screens = ptStyle( [
        ("output-field", "bg:#000000 #999999"),
        ("input-field", "bg:#000000 #ffff00"),
        ("line", "#004400"),
     ] )


style = merge_styles([
    style_from_pygments_cls(xgstyle),
    style_screens
])







##############################
#
#  log file read, write
#
##############################

log_fn='log.txt'

def writelog():
  with open(log_fn, 'w') as f:
     f.write(output_field.text)
  addtxt('WRITTEN FILE: "'+log_fn+'"')

def readlog():
  with open(log_fn, 'r') as f:
     output_field.text=f.read()
  addtxt('READ FILE: "'+log_fn+'"')





##############################
#
#  output window, routines
#
##############################

output_field = TextArea(
    style="class:output-field", text=help_text, scrollbar=True, line_numbers=True, lexer=PygmentsLexer(GtermLexer), read_only=True)




curpos=0  # maintain position when scrolling with simultaneous output
def addtxt(s):
    global curpos
    if application.layout.has_focus(output_field):curpos=output_field.buffer.cursor_position

    if s=='Recv: ok' and '*' in output_field.text[-5:]:
      output_field.text=output_field.text[:-1]+'  [ok]\n'
    else:
      output_field.text+=str(s)+'\n'
#      output_field.text+=s+'   '+output_field.text[-3:].rstrip()+'   '+'\n'

    # limit size
    output_field.text=output_field.text[-TERMLIMIT:]

    if application.layout.has_focus(input_field):curpos=len(output_field.text)
    output_field.buffer._set_cursor_position(curpos)



# command sent from the prompt area
def handlecmd_single(s):
    s=s.strip();

    if s=='/w':
      writelog()
      return

    if len(s)<1: return

    # PROCESS
    if s[:2]=='/p' or s=='/PAUSE':  apijob('pause','pause');addtxt(s);return
    if s=='/resume': apijob('pause','resume');addtxt(s);return
    if s=='/start':  apijob('start','');addtxt(s);return
    if s=='/stop':   apijob('pause','resume');addtxt(s);return
    if s=='/cancel': apigcode('M108');apijob('cancel','');addtxt(s);return
    # MACHINE
    if s=='/on':    s='M80'
    if s=='/off':   s='M81'
    # POSITION
    if s=='/home':  s='G28'

    if len(s)>1:
      if s[0]!=s[0].upper():
        s=s.upper()

    if s[0]=='X' or s[0]=='Y' or s[0]=='Z': s='G0 '+s

    #
    addtxt('>>>>> '+s)
    apigcode(s)


# command sent from the prompt area
def handlecmd(buf):
    s=input_field.text
    if ';' in s:
      for ss in s.split(';'):
        handlecmd_single(ss);
    else:
      handlecmd_single(s);




search_field = SearchToolbar()  # For reverse search.

input_field = TextArea(
    height=1,
    prompt=">>> ",
    style="class:input-field",
    multiline=False,
    wrap_lines=False,
    search_field=search_field,
    accept_handler=handlecmd
  )

container = HSplit(
    [
      output_field,
      Window(height=1, char="-", style="class:line"),
      input_field,
      search_field,
    ]
  )




# The key bindings.
kb = KeyBindings()

@kb.add("c-c")
@kb.add("c-d")
def _(event):
    "Pressing Ctrl-C or Ctrl-D will exit the user interface.\n"
    event.app.exit()

@kb.add('c-w')
@kb.add('tab')
def _(event):
    switch_focus()

def switch_focus():
    "Change focus when Control-W is pressed.\n"
    if application.layout.has_focus(input_field):
        application.layout.focus(output_field)
    else:
        application.layout.focus(input_field)





# Run application.
application = Application(
    layout=Layout(container, focused_element=input_field),
    key_bindings=kb,
    style=style,
    mouse_support=True,
    full_screen=True,
  )





# read octoprint configuration
try:
  octoconfstr=open(OCTOCMDCONF).read()
except:
  print('ERROR: cannot open file',OCTOCMDCONF)
  sys.exit(1)

try:
  octoconf=json.loads(octoconfstr)
except:
  print('ERROR: cannot parse file',OCTOCMDCONF,'as JSON.')
  sys.exit(1)

if VERB>1:addtxt('octoconf: '+str(octoconf))

loginurl=octoconf['OctoPrint_URL']
loginhdr={"X-Api-Key":octoconf['OctoAPI_KEY']}


# do login, request session key for websocket
r=apireq('/api/login?passive=true',{})


loginresp=json.loads(r)
if VERB>1:
  print(loginresp)
  print('Name: '+loginresp['name'])
  print('Session: '+loginresp['session'])
  addtxt(loginresp)
  addtxt('### Name: '+loginresp['name'])
  addtxt('### Session: '+loginresp['session'])

wsauthcmd=json.dumps({'auth':loginresp['name']+':'+loginresp['session']})
if VERB>1:
  print('auth cmd: '+wsauthcmd)
  addtxt('### auth cmd: '+wsauthcmd)


# configure websocket URL
if loginurl[:4]=='http': wsurl=loginurl[4:]
else: wsurl=loginurl
wsurl='ws'+wsurl+'/sockjs/websocket'
if VERB>=0: addtxt('### Opening websocket to: '+wsurl)

# open websocket
ws = websocket.WebSocketApp(wsurl,
     on_open=ws_on_open,
     on_message=ws_on_message,
     on_error=ws_on_error,
     on_close=ws_on_close  )

if VERB>0:
  if SHOWEV: addtxt('### Waiting for events')
  if SHOWG:  addtxt('### Waiting for gcode')










# populate the window with data
#readlog()

# run websocket task
t1=Thread(target=run_ws_task)
#t1.daemon=True  # do not daemonize!
t1.start()

application.run()
ws.close() # close the t1 thread here

print()




#if __name__ == "__main__":
#    main()
