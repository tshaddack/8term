Autogenerated from [https://www.improwis.com/projects/sw_8term/](https://www.improwis.com/projects/sw_8term/)






OctoControl Terminal








OctoControl Terminal
====================



---


[Problem](#Problem "#Problem")  
[Solution approach](#Solutionapproach "Solution approach")  
[basics](#basics "basics")  
      [config](#config "basics.config")  
      [websocket](#websocket "basics.websocket")  
      [REST API](#RESTAPI "basics.REST API")  
[8mon.py](#8mon.py "8mon.py")  
      [usage](#usage "8mon.py.usage")  
            [options](#options "8mon.py.usage.options")  
            [example](#example "8mon.py.usage.example")  
[8term.py](#8term.py "8term.py")  
      [usage](#8term.py.usage "8term.py.usage")  
            [options](#8term.py.usage.options "8term.py.usage.options")  
            [keys](#keys "8term.py.usage.keys")  
            [commands](#commands "8term.py.usage.commands")  
      [weakness](#weakness "8term.py.weakness")  
[Download](#Download "Download")  
[TODO](#TODO "TODO")  
[Screenshots](#Screenshots "Screenshots")  


---

Problem
-------



[OctoPrint](http://octoprint.org/ "remote link: http://octoprint.org/") is a neat software used as a web-operated printserver
for [3D printers](https://en.wikipedia.org/wiki/3D_printers "Wikipedia link: 3D printers").




Sometimes, however, a commandline control is desired.




For command by command noninteractive work, [8control](https://www.improwis.com/projects/8control "local project") suite was written in bash.




However, the commands do not provide the server's response. Which is occasionally needed.





---

Solution approach
-----------------



The OctoPrint server comes with a powerful [REST](https://en.wikipedia.org/wiki/Representational_state_transfer "Wikipedia link: Representational state transfer") [API](https://en.wikipedia.org/wiki/Application_programming_interface "Wikipedia link: Application programming interface") accessible
over the [HTTP](https://en.wikipedia.org/wiki/HTTP "Wikipedia link: HTTP") protocol and extensively using [JSON](https://en.wikipedia.org/wiki/JSON "Wikipedia link: JSON") format for the data.
The production version API documentation is [here](https://docs.octoprint.org/en/master/api/index.html "remote link: https://docs.octoprint.org/en/master/api/index.html").




There is also a [websocket](https://en.wikipedia.org/wiki/websocket "Wikipedia link: websocket") API. This is documented [here](https://docs.octoprint.org/en/master/api/push.html "remote link: https://docs.octoprint.org/en/master/api/push.html").




Python was chosen for this level of complexity, as the startup time penalty is not worth the necessary cost of not spending
too much time writing it all in C and bash is too weak.





---

basics
------


### config



Both 8mon and 8term use the same configuration file format as the 8control suite. The file is located at /etc/octocmd.conf
and is in JSON format. An example is here:

```
    "OctoAPI_KEY": "0C59XXXXXXXXXXXXXXXXXXXXXXXXXXXX",
    "OctoPrint_URL": "http://printer:5000"
}

```




The API key can be provided by the Octoprint UI.
The URL is the address of the machine. Can be domain name, can be a raw IP address.




The URL is converted to the websocket one by replacing http:// with ws://.



### websocket



The websocket data come in the form of JSON blocks. A fairly large amount of data flows in, with every state change
the server reports to the web browser interface.




The gcode logs, of Send and Recv streams, arrive in the  ['current']['logs']  array.




The machine events arrive in the  ['events']  array.




The data come in fixed intervals. More than one gcode line can come in the same event.




The websocket access is done via [websockets](https://websockets.readthedocs.io/ "remote link: https://websockets.readthedocs.io/") library.



### REST API



The API is needed for handling the login, and eventual other commands. The commands get submitted
to the server via a HTTP request. The command responses are retrieved via websocket.




The API access is done via [requests](https://pypi.org/project/requests/ "remote link: https://pypi.org/project/requests/") library.





---

8mon.py
-------



8mon.py is the noninteractive websocket/REST client.




The command can provide monitoring of the gcode communication, the events,
or the entire communication (which gets pretty spammy).




It can also send a command to the machine, and display its response.




CAVEAT: the code compares the command sent in with content of the Sent: line, then shows everything from that to Recv: ok.
Octoprint rewrites/substitutes some G/M codes. In these cases, the code won't return data and will be killed by a timeout.



### usage



On startup, 8mon reads the config file, connects to the websocket of the server mentioned there,
authorizes itself with the API key, subscribes to events and current streams on websocket, and
shows the incoming data.




If told, also sends a command.
The commands are converted to uppercase. (Beware, some commands like M117 and G7 have case-sensitive
data. This will break them.)



#### options



```
Usage: ./8mon.py [-a] [-s] [-v] [-v] [-v] [-tTIMEOUT] [-C/config/file] [command]
Parameters:
  -a        show all messages
  -s        show separators between messages
  -v        increase verbosity, up to 2 times
  -t<num>   timeout in seconds
  -C/file   config file location, default /etc/octocmd.conf
  -h        this help
  --help    this help
  command   gcode command to get the response


```

For easier parsing, there are no spaces between option and value.



#### example


 8mon.py m114 Send: M114 {'event': {'type': 'PositionUpdate', 'payload': {'reason': None, 'e': 0.0, 'x': 68.06, 'y': 62.24, 'f': 367.3464610996, 't': 0, 'z': 0.0}}} Recv: X:68.06 Y:62.24 Z:0.00 E:0.00 Count X: 32156 Y:21476 Z:0 Recv: ok 8mon.py ### Opening websocket to: ws://laser:5000/sockjs/websocket ### waiting for events, gcode ### Opened connection Recv: echo:busy: processing Recv: echo:busy: processing Recv: ok Recv: echo:endstops hit: Y:5.90 Send: N5 G0 X0.8954578544 Y0.0000000000 Z0.0000000000 F261.9211735748\*58 Recv: ok Send: N6 G0 X3.5309134035 Y0.0000000000 Z0.0000000000 F220.2485759381\*52 Recv: ok Send: N7 G0 X4.2839007032 Y0.0000000000 Z0.0000000000 F220.2485759381\*59 Recv: ok Send: N8 G0 X5.0816629578 Y0.0000000000 Z0.0000000000 F233.3452377916\*62 Recv: ok Send: N9 G0 X5.9771208121 Y0.0000000000 Z0.0000000000 F261.9211735748\*60 Recv: ok ^C### ERROR: <class 'KeyboardInterrupt'> ### closed ###

---

8term.py
--------



8term.py is an interactive terminal for the gcode, the console somewhat equivalent of the "Terminal" window of the web interface.
The terminal has color syntax highlighting.




The code uses the same general approach as 8mon does, with [prompt\_toolkit](https://python-prompt-toolkit.readthedocs.io/en/master/ "remote link: https://python-prompt-toolkit.readthedocs.io/en/master/") library
for general interactive screens, and [pygments](https://pygments.org/ "remote link: https://pygments.org/") as lexer and syntax highlighter.




The modified gcode lexer and the associated color style were integrated to the main file, to avoid multifile dependencies
and allow easy portability.



### usage



On startup, 8term reads the config file, connects to the websocket of the server mentioned there,
authorizes itself with the API key, subscribes to events and current streams on websocket, and
shows the incoming data on the top window.




The bottom window acts as the input console. A command entered there is sent via the REST API.




If the first command letter is lowercase, the command as a whole is converted to uppercase.
Beware, some commands like M117 and G7 have case-sensitive data. This will break them.
An uppercase G or M (or other letter) will signal to the software it should not translate case.




Command sent as parameter from the console will be uppercased regardless. (TODO: address.)



#### options



```
Usage: ./8term.py [-a] [-s] [-v] [-v] [-v] [-tTIMEOUT] [-C/config/file] [command]
Parameters:
  -v        increase verbosity, up to 2 times
  -C/file   config file location, default /etc/octocmd.conf
  -h        this help
  --help    this help
  command   gcode command to get the response


```

For easier parsing, there are no spaces between option and value.



#### keys


* Ctrl-C, Ctrl-D - quit
* Tab, Ctrl-W - switch between top and bottom window
* PgUp, PgDn - if the top window is focused, scroll through the history

#### commands


* process
+ /start - starts job
+ /pause - pauses running job
+ /resume - resumes running job
+ /cancel - cancels running job

* position
+ /home - G28, homes the machine

* machine
+ /on - M80, power-on the machine
+ /off - M81, power-off the machine

### weakness



The code gets slower at too many thousand gcode lines.





---

Download
--------


* [8mon.py](8mon.py "local file")
* [8term.py](8term.py "local file")



---

TODO
----


* more commands
* better error handling
* find out why slow, or add manual clearing of the console
* file upload/run handling
* case handling for commands
* logfile load/save with filenames



---

Screenshots
-----------




|  |  |  |  |
| --- | --- | --- | --- |






