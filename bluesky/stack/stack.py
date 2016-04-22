from math import *
import numpy as np
from random import random, randint, seed
import os
import sys

from ..tools.aero import kts, ft, fpm, nm, lbs,\
                         qdrdist, cas2tas, mach2tas, tas2cas, tas2eas, tas2mach,\
                         eas2tas, cas2mach, density
from ..tools.misc import txt2alt, txt2spd, col2rgb, cmdsplit,  txt2lat, txt2lon
from .. import settings

# import pdb


class Commandstack:
    """
    Commandstack class definition : command stack & processing class

    Methods:
        Commandstack()          :  constructor
        stack(cmdline)          : add a command to the command stack
        openfile(scenname)      : start playing a scenario file scenname.SCN
                                  from scenario folder
        savefile(scenname,traf) : save current traffic situation as
                                  scenario file scenname.SCN
        checkfile(t)            : check whether commands need to be
                                  processed from scenario file

        process(sim, traf, scr) : central command processing method
                                  (with long elif tree with all commands)

    Created by  : Jacco M. Hoekstra (TU Delft)
    """
    def __init__(self, sim, traf, scr):

        #Command dictionary: command, helptext, arglist, function to call
        # Enclose optional arguments with []
        #--------------------------------------------------------------------
        self.cmddict = {
            "ADDNODES": [
                "ADDNODES number",
                "int",
                sim.addNodes],
            "ALT": [
                "ALT acid, alt, [vspd]",
                "acid,alt,[vspd]",
                traf.selalt
            ],
            "BATCH": [
                "BATCH filename",
                "txt",
                sim.batch],
            "CRE": [
                "CRE acid,type,lat,lon,hdg,alt,spd",
                "txt,txt,lat,lon,hdg,alt,spd",
                traf.create
            ],
            "DATAFEED":  [
                "DATAFEED [ON/OFF]",
                "[onoff]",
                sim.datafeed
            ],
            "DT": [
                "DT dt",
                "float",
                sim.setDt
            ],
            "DTMULT": [
                "DTMULT multiplier",
                "float",
                sim.setDtMultiplier
            ],
            "ECHO": [
                "ECHO txt",
                "txt",
                scr.echo
            ],
            "ENG": [
                "ENG acid,[engine_id]",
                "acid,[txt]",
                traf.perf.engchange
            ],
            "FF":  [
                "FF [tend]",
                "[time]",
                sim.fastforward
            ],
            "FIXDT": [
                "FIXDT ON/OFF [tend]",
                "onoff,[time]",
                sim.setFixdt
            ],
            "HDG": [
                "HDG acid,hdg (deg,True)",
                "acid,float",
                traf.selhdg
            ],
            "HELP": [
                "HELP [command]",
                "[txt]",
                lambda *args: scr.echo(self.help(*args))
            ],
            "HOLD": [
                "HOLD",
                "",
                sim.pause
            ],
            "INSEDIT": [
                "INSEDIT txt",
                "txt",
                scr.cmdline
            ],
            "LOG": [
                "LOG acid/area/*,dt",
                "txt,float",
                sim.datalog.start
            ],
            "MCRE": [
                "MCRE n, [type/*, alt/*, spd/*, dest/*]",
                "int,[txt,alt,spd,txt]",
                lambda *args: traf.mcreate(*args, area=scr.getviewlatlon())
            ],
            "MOVE": [
                "MOVE acid,lat,lon,[alt,hdg,spd,vspd]",
                "acid,lat,lon,[alt,hdg,spd,vspd]",
                traf.move
            ],
            "ND": [
                "ND acid",
                "txt",
                lambda acid: scr.feature("ND", acid)
            ],
            "NOISE": [
                "NOISE [ON/OFF]",
                "[onoff]",
                traf.setNoise
            ],
            "NOM": [
                "NOM acid",
                "acid",
                traf.nom],
            "OP": [
                "OP",
                "",
                sim.start
            ],
            "PCALL": [
                "PCALL filename [REL/ABS]",
                "txt,[txt]",
                self.pcall
            ],
            "RESET": [
                "RESET",
                "",
                sim.reset],
            "SCEN": [
                "SCEN scenname",
                "txt",
                sim.scenarioInit
            ],
            "SEED": [
                "SEED value",
                "int",
                self.setSeed],
            "SPD": [
                "SPD acid,spd (CAS-kts/Mach)",
                "acid,spd",
                traf.selspd
            ],
            "SSD": [
                "SSD acid/ALL/OFF",
                "txt",
                scr.showssd
            ],
            "STOP": [
                "STOP",
                "",
                sim.stop
            ],
            "SYMBOL":  [
                "SYMBOL",
                "",
                scr.symbol
            ],
            "VS": [
                "VS acid,vspd (ft/min)",
                "acid,vspd",
                traf.selvspd]
        }

        #--------------------------------------------------------------------
        # Command synonym dictionary
        self.cmdsynon = {
            "CONTINUE": "OP",
            "CREATE": "CRE",
            "DTLOOK": "ASA_DTLOOK",
            "END": "STOP",
            "EXIT": "STOP",
            "FWD": "FF",
            "PAUSE": "HOLD",
            "Q": "STOP",
            "QUIT": "STOP",
            "RUN": "OP",
            "START": "OP",
            "TURN": "HDG",
            "?": "HELP"
        }
        #--------------------------------------------------------------------

        self.cmdstack  = []
        self.scentime  = []
        self.scenfile  = ""
        self.scentime = []
        self.scencmd = []

        # Display Help text on start of program
        self.stack("ECHO BlueSky Console Window: Enter HELP or ? for info.\n" +
            "Or select IC to Open a scenario file.")

        # Pan to initial location
        self.stack('PAN ' + settings.start_location)
        self.stack("ZOOM 0.4")

        # ------------------ [start] Deprecated -------------------
        # An alternative way to add your own commands: 
        # add your entry to the dictionary.
        # The dictionary should be formed as {"Key":module'}.

        # "Key" is a FOUR-symbol reference used at the start of command.
        # 'module' is the name of the .py-file in which the 
        # commands are located (without .py).

        # Make sure that the module has a function "process" with
        # arguments:
        #   command, number of args, array of args, sim, traf, scr, cmd

        self.extracmdmodules = {
            "SYN_": 'synthetic', 
            "ASA_":'asascmd', 
           # "LOG_":'log' # Old logging module
        }

        # Import modules from the list
        self.extracmdrefs={}
        sys.path.append('bluesky/stack/')
        for key in self.extracmdmodules:
            obj=__import__(self.extracmdmodules[key],globals(),locals(),[],0)
            self.extracmdrefs[key]=obj
        # ------------------ [end] Deprecated -------------------

        return

    def help(self, cmd=None):
        if cmd is None:
            text = "To get help on a command, enter it without arguments.\n" + \
                   "Some basic commands are given below:\n\n"
            text2 = ""
            for key in self.cmddict:
                text2 += (key + " ")
                if len(text2) >= 40:
                    text += (text2 + "\n")
                    text2 = ""
            text += (text2 + "\nSee Info subfolder for more info.")
            return text
        elif cmd in self.cmddict:
            return self.cmddict[cmd][0]
        else:
            return "HELP: Unknown command: " + cmd

    def setSeed(self, value):
        seed(value)
        np.random.seed(value)

    def reset(self):
        self.scentime = []
        self.scencmd  = []

    def stack(self, cmdline):
        # Stack one or more commands separated by ";"
        cmdline = cmdline.strip()
        if len(cmdline) > 0:
            for line in cmdline.split(';'):
                self.cmdstack.append(line)

    def openfile(self, scenname, t_offset=0.0, mergeWithExisting=False):
        scenlines = []

        # Add .scn extension if necessary
        if scenname.lower().find(".scn") < 0:
            scenname = scenname + ".scn"

        # If it is with a path don't touch it, else add path
        if scenname.find("/") < 0 and scenname.find( "\\") < 0:
            scenfile = settings.scenario_path
            if scenfile[-1] is not '/':
                scenfile += '/'
            scenfile += scenname.lower()
        else:
            scenfile = scenname

        print "Reading scenario file: ", scenfile
        print

        if not os.path.exists(scenfile):
            print"Error: cannot find file:", scenfile
            return

        # Read lines into buffer
        fscen = open(scenfile, 'r')
        scenlines = fscen.readlines()
        fscen.close()
        i = 0
        while i < len(scenlines):
            if len(scenlines[i].strip()) <= 12 or scenlines[i][0] == "#":
                del scenlines[i]
            else:
                i = i + 1

        # Optional?
        # scenlines.sort()

        # Set timer until what is read
        # tstamp = scenlines[0][:11]    # format - hh:mm:ss.hh
        # ihr = int(tstamp[:2])
        # imin = int(tstamp[3:5])
        # isec = float(tstamp[6:8]+"."+tstamp[9:11])

        # Split scenario file line in times and commands
        if not mergeWithExisting:
            # When a scenario file is read with PCALL the resulting commands
            # need to be merged with the existing commands. Otherwise the
            # old scenario commands are cleared.
            self.scentime = []
            self.scencmd  = []

        for line in scenlines:
            if line.strip()[0] != "#":
                # Try reading timestamp and command
                try:
                    icmdline = line.index('>')
                    tstamp = line[:icmdline]
                    ttxt = tstamp.strip().split(':')
                    ihr = int(ttxt[0])
                    imin = int(ttxt[1])
                    xsec = float(ttxt[2])
                    self.scentime.append(ihr * 3600. + imin * 60. + xsec + t_offset)
                    self.scencmd.append(line[icmdline + 1:-1])
                except:
                    print "except this:", line
                    pass  # nice try, we will just ignore this syntax error

        if mergeWithExisting:
            # If we are merging we need to sort the resulting command list
            self.scentime, self.scencmd = [list(x) for x in zip(*sorted(
                zip(self.scentime, self.scencmd), key=lambda pair: pair[0]))]

    def pcall(self, filename, absrel='ABS'):
        # If timestamps in file should be interpreted as relative we need to add
        # the current simtime to every timestamp
        t_offset = self.sim.simt if absrel == 'REL' else 0.0

        # Load the scenario file, and merge with existing command list
        self.openfile(filename, t_offset, True)

    def checkfile(self, simt):
        # Empty command buffer when it's time
        while len(self.scencmd) > 0 and simt >= self.scentime[0]:
            self.stack(self.scencmd[0])
            del self.scencmd[0]
            del self.scentime[0]

        return

    def saveic(self, fname, sim, traf):

        # Add extension .scn if not already present
        if fname.find(".scn") < 0 and fname.find(".SCN"):
            fname = fname + ".scn"

        # If it is with path don't touch it, else add path
        if fname.find("/") < 0:
            scenfile = "./scenario/" + fname.lower()

        try:
            f = open(scenfile, "w")
        except:
            return -1

        # Write files
        timtxt = "00:00:00.00>"

        for i in range(traf.ntraf):
            # CRE acid,type,lat,lon,hdg,alt,spd
            cmdline = "CRE " + traf.id[i] + "," + traf.type[i] + "," + \
                      repr(traf.lat[i]) + "," + repr(traf.lon[i]) + "," + \
                      repr(traf.trk[i]) + "," + repr(traf.alt[i] / ft) + "," + \
                      repr(tas2cas(traf.tas[i], traf.alt[i]) / kts)

            f.write(timtxt + cmdline + chr(13) + chr(10))

            # VS acid,vs
            if abs(traf.vs[i]) > 0.05:  # 10 fpm dead band
                if abs(traf.avs[i]) > 0.05:
                    vs_ = traf.avs[i] / fpm
                else:
                    vs_ = traf.vs[i] / fpm

                cmdline = "VS " + traf.id[i] + "," + repr(vs_)
                f.write(timtxt + cmdline + chr(13) + chr(10))

            # Autopilot commands
            # Altitude
            if abs(traf.alt[i] - traf.aalt[i]) > 10.:
                cmdline = "ALT " + traf.id[i] + "," + repr(traf.aalt[i] / ft)
                f.write(timtxt + cmdline + chr(13) + chr(10))

            # Heading as well when heading select
            delhdg = (traf.trk[i] - traf.ahdg[i] + 180.) % 360. - 180.
            if abs(delhdg) > 0.5:
                cmdline = "HDG " + traf.id[i] + "," + repr(traf.ahdg[i])
                f.write(timtxt + cmdline + chr(13) + chr(10))

            # Speed select? => Record
            rho = density(traf.alt[i])  # alt in m!
            aptas = sqrt(1.225 / rho) * traf.aspd[i]
            delspd = aptas - traf.tas[i]

            if abs(delspd) > 0.4:
                cmdline = "SPD " + traf.id[i] + "," + repr(traf.aspd[i] / kts)
                f.write(timtxt + cmdline + chr(13) + chr(10))

            # DEST acid,dest-apt
            if traf.dest[i] != "":
                cmdline = "DEST " + traf.id[i] + "," + traf.dest[i]
                f.write(timtxt + cmdline + chr(13) + chr(10))

            # ORIG acid,orig-apt
            if traf.orig[i] != "":
                cmdline = "ORIG " + traf.id[i] + "," + \
                          traf.orig[i]
                f.write(timtxt + cmdline + chr(13) + chr(10))

        # Saveic: should close
        f.close()
        return 0

    def process(self, sim, traf, scr):
        """process and empty command stack"""
        # Process stack of commands
        for line in self.cmdstack:
            # Empty line: next command
            line = line.strip()
            if len(line) == 0:
                continue

            # Split command line into command and arguments, pass traf ids to check for
            # switched acid and command
            cmd, args = cmdsplit(line.upper(), traf.id)
            numargs   = len(args)

            # Check if this is a POS command with only an aircraft id
            if numargs == 0 and traf.id.count(cmd) > 0:
                args    = [cmd]
                cmd     = 'POS'
                numargs = 1

            # Assume syntax is ok (default)
            synerr = False

            # Catch general errors
#            try:
            if True:  # optional to switch error protection off

                #**********************************************************************
                #=====================  Start of command branches =====================
                #**********************************************************************

                #----------------------------------------------------------------------
                # First check command synonymes list, then in dictionary
                #----------------------------------------------------------------------
                if cmd in self.cmdsynon.keys():
                    cmd = self.cmdsynon[cmd]

                if cmd in self.cmddict.keys():
                    helptext, argtypelist, function = self.cmddict[cmd]
                    argvsopt = argtypelist.split('[')
                    argtypes = argvsopt[0].strip(',').split(",")
                    if argtypes == ['']:
                        argtypes = []

                    # Check if at least the number of mandatory arguments is given.
                    if numargs < len(argtypes):
                        print numargs, len(argtypes)
                        scr.echo("Syntax error: Too few arguments")
                        scr.echo(line)
                        scr.echo(helptext)
                        continue

                    # Add optional argument types if they are given
                    if len(argvsopt) == 2:
                        argtypes += argvsopt[1].strip(']').split(',')
                    numtypes = len(argtypes)

                    # Process arg list
                    # Special case: single text argument: this can also be a string, so pass the original
                    if argtypes == ['txt']:
                        arglist = [line[len(cmd) + 1:]]
                    else:
                        arglist = []
                        idx     = -1          # Reference aircraft
                        refalt  = 0.          # Reference altitude
                        reflat  = scr.ctrlat  # Reference latitude
                        reflon  = scr.ctrlon  # Reference longitude
                        try:
                            for i in range(min(numtypes, numargs)):
                                argtype = argtypes[i].strip()

                                if args[i] == "" or args[i] == "*":  # Empty arg or wildcard => parse None
                                    arglist.append(None)

                                elif argtype == "acid":  # aircraft id => parse index

                                    idx = traf.id2idx(args[i])
                                    if idx < 0:
                                        scr.echo(cmd + ":" + args[i] + " not found")
                                        synerr = True
                                        break
                                    else:
                                        arglist.append(idx)

                                elif argtype == "txt":  # simple text
                                    arglist.append(args[i])

                                elif argtype == "float":  # float number
                                    arglist.append(float(args[i]))

                                elif argtype == "int":   # integer
                                    arglist.append(int(args[i]))  # switch

                                elif argtype == "onoff" or argtype == "bool":
                                    sw = (args[i] == "ON" or
                                          args[i] == "1" or args[i] == "TRUE")
                                    arglist.append(sw)

                                elif argtype == "lat":
                                    try:
                                        reflat = txt2lat(args[i])
                                        arglist.append(float(reflat))
                                    except:
                                        synerr = True

                                elif argtype == "lon":
                                    try:
                                        reflon = txt2lon(args[i])
                                        arglist.append(float(reflon))
                                    except:
                                        synerr = True

                                elif argtype == "spd":  # CAS[kts] Mach
                                    spd = float(args[i].upper().replace("M", ".").replace("..", "."))
                                    if not 0.1 < spd < 1.0:
                                        spd *= kts
                                    arglist.append(spd)  # speed CAS[m/s] or Mach (float)

                                elif argtype == "vspd":
                                    arglist.append(fpm * float(args[i]))

                                elif argtype == "alt":  # alt: FL250 or 25000 [ft]
                                    arglist.append(ft * txt2alt(args[i]))  # alt in m

                                elif argtype == "hdg":
                                    # TODO: for now no difference between magnetic/true heading
                                    hdg = float(args[i].upper().replace('T', '').replace('M', ''))
                                    arglist.append(hdg)

                                elif argtype == "time":
                                    ttxt = args[i].strip().split(':')
                                    if len(ttxt) >= 3:
                                        ihr  = int(ttxt[0])
                                        imin = int(ttxt[1])
                                        xsec = float(ttxt[2])
                                        arglist.append(ihr * 3600. + imin * 60. + xsec)
                                    else:
                                        arglist.append(float(args[i]))

                        except:
                            synerr = False
                            scr.echo("Syntax error in processing arguments")
                            scr.echo(line)
                            scr.echo(helptext)

                    # Call function return flag,text
                    # flag: indicates sucess
                    # text: optional error message
#                    try:
                    results = function(*arglist)  # * = unpack list to call arguments
#                    except:
#                        synerr = True
                    txt = helptext
                    if not synerr:

                        if type(results) == bool:  # Only flag is returned
                            synerr = not results
                            if synerr:
                                if numargs <= 0 or args[i] == "?":
                                    scr.echo(helptext)
                                else:
                                    scr.echo("Syntax error: " + helptext)
                                synerr =  False  # Prevent further nagging

                        elif type(results) == list or type(results) == tuple:
                            # Maybe there is also an error message returned?
                            if len(results) >= 1:
                                synerr = not results[0]

                            if len(results) >= 2:
                                scr.echo(cmd+":"+results[1])
                                synerr = False

                    else:  # synerr:
                        scr.echo("Syntax error: " + helptext)

                #----------------------------------------------------------------------
                # POS command: traffic info; ("KL204", "POS KL204" or "KL204 ?")
                #----------------------------------------------------------------------
                elif cmd == "POS" or cmd == "?":
                    if numargs >= 1:
                        acid = args[0]

                        # Does aircraft exist?
                        idx = traf.id2idx(acid)
                        if idx < 0:
                            scr.echo("POS: " + acid + " not found.")

                        # print info on aircraft if found
                        else:
                            scr.echo("Info on " + acid + " " + traf.type[idx]+\
                                                          "   index = " + str(idx))
                            taskts = int(round(traf.tas[idx]/kts))                              
                            caskts = int(round(tas2cas(traf.tas[idx],traf.alt[idx])/kts))                              
                            scr.echo("Pos = " + str(traf.lat[idx])+" , "+str(traf.lon[idx]))
                            scr.echo(str(caskts)+" kts (TAS: "+str(taskts)+" kts) at " \
                                     + str(int(traf.alt[idx] / ft)) + " ft")
                            scr.echo("Hdg = " + str(int(traf.trk[idx])))
                            if traf.swvnav[idx]:
                                vnavtxt = "VNAV "
                            else:
                                vnavtxt = ""
                            if traf.swlnav[idx] and traf.route[idx].nwp>0 and  \
                               traf.route[idx].iactwp>=0:
                                 scr.echo(vnavtxt + "LNAV to "+   \
                                  traf.route[idx].wpname[traf.route[idx].iactwp])
                            
                            txt = "Flying"
                            if traf.orig[idx]!="":
                                txt = txt + " from "+traf.orig[idx]
                            if traf.dest[idx]!="":
                                txt = txt + " to "+traf.dest[idx]
                            if len(txt)>0:
                                scr.echo(txt)

                        # Show route for this aircraft (toggle switch)
                        scr.showroute(acid)

                    else:
                         synerr = True

                #----------------------------------------------------------------------
                # DEL: Delete command: delete an aircraft
                #----------------------------------------------------------------------
                elif cmd == "DEL":
                    if numargs == 1:
                        if args[0] == "LINE" or args[0] == "LINES":
                            scr.objdel()  # delete raw objects
                        else:
                            success = traf.delete(args[0].upper())
                            if not success:
                                scr.echo("DEL: " + args[0] + " not found.")

                #----------------------------------------------------------------------
                # DEST/ORIG: Destination/Origin command: set destination/origin airport
                #----------------------------------------------------------------------
                elif cmd == "DEST" or cmd == "ORIG":
                    if numargs==0:
                        scr.echo(cmd+" acid, airport")
                    elif numargs >=1:
                        acid = args[0]
                        idx = traf.id2idx(acid)
                        if idx>=0 and numargs==1:
                            if cmd=="DEST":
                                scr.echo("DEST "+acid+": "+traf.dest[idx])                            
                            else:
                                scr.echo("ORIG "+acid+": "+traf.orig[idx])                            
                            
                        elif idx >= 0 and numargs>=2:
                            name = args[1]
 
                           # Check for lat/lon type
                            if numargs>=3:
                                chkdig = args[1].replace("-","")     \
                                       .replace("+","").replace(".","") \
                                       .replace("N","").replace("S","") \
                                       .replace("E","").replace("W","") \
                                       .replace("'","").replace('"',"") 

                                if chkdig.isdigit():
          
                                        name    = traf.id[idx]+cmd # use for wptname
                                        if cmd=="DEST":
                                            wptype  = traf.route[idx].dest
                                        else:
                                            wptype  = traf.route[idx].orig
                                           
                                        lat     = txt2lat(args[1])
                                        lon     = txt2lon(args[2])
 
                              
                            # Destination is default waypoint
                            if cmd == "DEST":
                                traf.dest[idx] = name.upper().strip()
                                iwp = traf.route[idx].addwpt(traf,idx,traf.dest[idx],
                                                             traf.route[idx].dest,
                                                             traf.lat[idx], traf.lon[idx],
                                                             0.0, traf.cas[idx])
                                # If only waypoint: activate
                                if (iwp == 0) or (traf.orig[idx]!="" and traf.route[idx].nwp==2):
                                     traf.actwplat[idx] = traf.route[idx].wplat[iwp]
                                     traf.actwplon[idx] = traf.route[idx].wplon[iwp]
                                     traf.actwpalt[idx] = traf.route[idx].wpalt[iwp]
                                     traf.actwpspd[idx] = traf.route[idx].wpspd[iwp]

                                     traf.swlnav[idx] = True
                                     traf.route[idx].iactwp = iwp

                                # If not found, say so
                                elif iwp < 0:
                                     scr.echo(traf.dest[idx] + " not found.")

                            # Origin: bookkeeping only for now
                            else:
                                traf.orig[idx] = name.upper().strip()
                                iwp = traf.route[idx].addwpt(traf,idx,traf.orig[idx],traf.route[idx].orig,
                                                 traf.lat[idx], traf.lon[idx],
                                                          0.0, traf.cas[idx])
                                if iwp < 0:
                                     scr.echo(traf.orig[idx] + " not found.")
                        # Give destination and origin
                        elif idx >=0 and numargs==1:
                            txt = ""
                            if traf.orig[idx]!="":
                                txt = txt + " from "+traf.orig[idx]
                            if traf.dest[idx]!="":
                                txt = txt + " to "+traf.dest[idx]
                            if len(txt)>0:
                                scr.echo(traf.id[idx]+txt)
                            else:
                                scr.echo(traf.id[idx]+": orig and dest not defined.")

                        else:
                            scr.echo(cmd + ": aircraft " + acid + " not found.")
                    else:
                        synerr = True

                #----------------------------------------------------------------------
                # ZOOM command (or use ++++  or --  to zoom in or out)
                #----------------------------------------------------------------------
                elif cmd[:4] == "ZOOM" or cmd[0] == "+" or cmd[0] == "=" or cmd[0] == "-":
                    if cmd[0] != "Z":
                        nplus = cmd.count("+") + cmd.count("=")  #= equals + (same key)
                        nmin = cmd.count("-")
                        zoomfac = sqrt(2) ** nplus / (sqrt(2) ** nmin)
                        scr.zoom(zoomfac)
                    else:
                        synerr = not(len(args) == 1)
                        if not synerr:
                            if args[0] == "IN":
                                scr.zoom(1.4142135623730951)  # sqrt(2.)

                            elif args[0] == "OUT":
                                scr.zoom(0.70710678118654746)  #1./sqrt(2.)
                            else:
                                try:
                                    zoomfac = float(args[0])
                                    scr.zoom(zoomfac, True)
                                except:
                                    synerr = True

                        if synerr:
                            print "Syntax error in command"
                            scr.echo("Syntax error in command")
                            scr.echo("ZOOM IN/OUT")
                            continue  # Skip default syntyax message

                #----------------------------------------------------------------------
                # PAN command
                #----------------------------------------------------------------------
                elif cmd[:4] == "PAN":

                    if not (numargs == 1 or numargs == 2):
                        if numargs>0:
                            scr.echo("Syntax error in command")
                        scr.echo("PAN LEFT/RIGHT/UP/DOWN/acid/airport/navid")
                        continue

                    # LEFT/RIGHT/UP/DOWN
                    elif numargs == 1:
                        if args[0] == "LEFT":
                            scr.pan((0.0, -0.5)) # move half screen left
                            continue
                        elif args[0] == "RIGHT":
                            scr.pan((0.0, 0.5)) # move half screen right
                            continue

                        elif args[0] == "UP":
                            scr.pan((0.5, 0.0))  # move half screen up
                            continue

                        elif args[0] == "DOWN":
                            scr.pan((-0.5, 0.0)) # move half screen down
                            continue
                        else:
                            # Try aicraft id, waypoint of airport
                            i = traf.id2idx(args[0])
                            if i >= 0:
                                lat = traf.lat[i]
                                lon = traf.lon[i]
                                if (np.isnan(lat) or np.isnan(lon)):
                                    continue
                            else:
                                i = traf.navdb.getwpidx(args[0], 0.0, 0.0)  # TODO: get current pan from display?
                                if i >= 0:
                                    lat = traf.navdb.wplat[i]
                                    lon = traf.navdb.wplon[i]
                                    if (np.isnan(lat) or np.isnan(lon)):
                                        continue
                                else:
                                    i = traf.navdb.getapidx(args[0])
                                    if i >= 0:
                                        lat = traf.navdb.aplat[i]
                                        lon = traf.navdb.aplon[i]
                                        if (np.isnan(lat) or np.isnan(lon)):
                                            continue
                                    else:
                                        synerr= True
                                        scr.echo(args[0] + " not found.")
                            if not synerr and (not (np.isnan(lat) or np.isnan(lon))):
                                scr.pan((lat, lon), absolute=True)

                    # PAN to lat,lon position
                    elif numargs == 2:
                        lat = float(args[0])
                        lon = float(args[1])

                        if not (np.isnan(lat) or np.isnan(lon)):
                            scr.pan((lat, lon), absolute=True)

#

                #----------------------------------------------------------------------
                # IC scenfile: command: restart with new filename (.scn will be added if necessary)
                # IC IC: same file
                #----------------------------------------------------------------------
                elif cmd == "IC":
                    sim.reset()
                    # If no arg is given: check
                    if numargs >= 1:
                        # Use lower case line for filename and allow space in path
                        filename = line.strip()[3:].strip()
                        if filename.upper() == "IC":  # same file
                            filename = self.scenfile

                        if filename.strip() != "":
                            scr.echo("Opening " + filename + " ...")

                        # Open file in ./scenario subfolder

                        self.scenfile = filename
                        self.openfile(self.scenfile)

                    else:

                        filename = scr.show_file_dialog()
                        if len(filename) > 0:
                            self.scenfile = filename
                            self.openfile(self.scenfile)

                #----------------------------------------------------------------------
                # SAVE/SAVEIC Save current traffic situation as IC scn file
                #----------------------------------------------------------------------
                elif cmd == "SAVEIC":
                    if numargs <= 0:
                        scr.echo("SAVEIC needs filename")
                    else:
                        errcode = self.saveic(args[0], sim, traf)
                        if errcode == -1:
                            scr.echo("SAVEIC: Error writing file")

                #----------------------------------------------------------------------
                # METRICS command: METRICS/METRICS OFF/0/1/2 [dt]  analyze traffic complexity metrics
                #----------------------------------------------------------------------
                elif cmd[:6] == "METRIC":
                    if sim.metric is None:
                        scr.echo("METRICS module disabled")

                    elif numargs < 1:
                        if sim.metric.metric_number < 0:
                            scr.echo("No metric active, to configure run:")
                            scr.echo("METRICS OFF/0/1/2 [dt]")
                        else:
                            scr.echo("")
                            scr.echo("Active: " + "(" + str(sim.metric.metric_number + 1) + ") " + sim.metric.name[
                                sim.metric.metric_number])
                            scr.echo("Current dt: " + str(sim.metric.dt) + " s")

                    elif args[0] == "OFF":  # arguments are strings
                        sim.metric.metric_number = -1
                        scr.echo("Metric is off")

                    else:
                        if not args[0][1:].isdigit():
                            # print args[0][1:].isdigit()
                            scr.echo("Command argument invalid")
                            return
                        sim.metric.metric_number = int(args[0]) - 1
                        if sim.metric.metric_number < 0:
                            scr.echo("Metric is off")
                        elif sim.metric.metric_number <= len(sim.metric.name):
                            if traf.area == "Circle":
                                scr.echo("(" + str(sim.metric.metric_number + 1) + ") " + sim.metric.name[
                                    sim.metric.metric_number] + " activated")
                                try:
                                    metric_dt = float(args[1])
                                    if metric_dt > 0:
                                        sim.metric.dt = metric_dt
                                        scr.echo("with dt = " + str(metric_dt))
                                    else:
                                        scr.echo("No valid dt")
                                except:
                                    scr.echo("with dt = " + str(sim.metric.dt))
                            else:
                                scr.echo("First define AREA FIR")
                        else:
                            scr.echo("No such metric")

                #----------------------------------------------------------------------
                # AREA command: AREA lat0,lon0,lat1,lon1[,lowalt]
                #               AREA FIR fir radius [lowalt]
                #----------------------------------------------------------------------
                elif cmd == "AREA":
                    
                    # debugger
#                    pdb.set_trace()                    
                    
                    if numargs == 0:
                        scr.echo("AREA lat0,lon0,lat1,lon1[,lowalt]")
                        scr.echo("or")
                        scr.echo("AREA fir,radius[,lowalt]")
                        scr.echo("or")
                        scr.echo("AREA circle,lat0,lon0,radius[,lowalt] ")
                    elif numargs == 1 and args[0] != "OFF" and args[0] != "FIR":
                        scr.echo("AREA lat0,lon0,lat1,lon1[,lowalt]")
                        scr.echo("or")
                        scr.echo("AREA fir,radius[,lowalt]")
                        scr.echo("or")
                        scr.echo("AREA circle,lat0,lon0,radius[,lowalt] ")
                        
                    elif numargs == 1:
                        if args[0] == "OFF":
                            if traf.swarea:
                                traf.swarea = False
                                scr.redrawradbg = True
                                traf.area = ""
                                scr.objappend(2, "AREA", None) # delete square areas
                                scr.objappend(3, "AREA", None) # delete circle areas
                        if args[0] == "FIR":
                            scr.echo("Specify FIR")

                    elif numargs > 1 and args[0][0].isdigit():

                        lat0 = float(args[0])  # [deg]
                        lon0 = float(args[1])  # [deg]
                        lat1 = float(args[2])  # [deg]
                        lon1 = float(args[3])  # [deg]

                        traf.arealat0 = min(lat0, lat1)
                        traf.arealat1 = max(lat0, lat1)
                        traf.arealon0 = min(lon0, lon1)
                        traf.arealon1 = max(lon0, lon1)

                        if numargs == 5:
                            traf.areafloor = float(args[4]) * ft
                        else:
                            traf.areafloor = -9999999.

                        traf.area = "Square"
                        traf.swarea = True
                        scr.redrawradbg = True
                        scr.objappend(2, "AREA", [lat0, lon0, lat1, lon1])

                        # Avoid mass delete due to redefinition of area
                        traf.inside = traf.ntraf * [False]

                    elif numargs > 2 and args[0] == "FIR":

                        for i in range(0, len(traf.navdb.fir)):
                            if args[1] == traf.navdb.fir[i][0]:
                                break
                        if args[1] != traf.navdb.fir[i][0]:
                            scr.echo("Unknown FIR, try again")
                        if sim.metric is not None:
                            sim.metric.fir_number = i
                            sim.metric.fir_circle_point = sim.metric.metric_Area.FIR_circle(traf.navdb, sim.metric.fir_number)
                            sim.metric.fir_circle_radius = float(args[2])
                        else:
                            scr.echo("warning: FIR not loaded into METRICS module because not active")

                        if numargs == 4:
                            traf.areafloor = float(args[3]) * ft
                        else:
                            traf.areafloor = -9999999.
                        if numargs > 4:
                            scr.echo("AREA command unknown")

                        traf.area = "Circle"
                        traf.swarea = True
                        scr.drawradbg()
                        traf.inside = traf.ntraf * [False]
                    
                    # circle code
                    elif (numargs > 2 and args[0] == "CIRCLE"):
                        
                        # draw circular experiment area
                        lat0 = np.float(args[1])   # Latitude of circle center [deg]
                        lon0 = np.float(args[2])   # Longitude of circle center [deg]
                        radius = np.float(args[3]) # Radius of circle Center [NM]                      
                                               
                        # Deleting traffic flying out of experiment area
                        traf.area = "Circle"
                        traf.swarea = True
                        traf.arearadius = radius
                        traf.arealat0 = lat0 # center of circle sent to traf
                        traf.arealon0 = lon0
                        
                        if numargs == 5:
                            traf.areafloor = float(args[4]) * ft # [m]
                        else:
                            traf.areafloor = -9999999. # [m]
                            
                        # draw the circular experiment area on the radar gui  
                        scr.redrawradbg = True                        
                        scr.objappend(3, "AREA", [lat0,lon0,radius])
                        
                        # Avoid mass delete due to redefinition of area
                        traf.inside = traf.ntraf * [False]
                        
                     
                    else:
                        scr.echo("AREA command unknown")
                        scr.echo("AREA lat0,lon0,lat1,lon1[,lowalt]")
                        scr.echo("or")
                        scr.echo("AREA fir,radius[,lowalt]")
                        scr.echo("or")
                        scr.echo("AREA circle,lat0,lon0,radius[,lowalt] ")

                #----------------------------------------------------------------------
                # TAXI command: TAXI ON/OFF : if off, 
                #   autodelete descending aircraft below 1500 ft
                #----------------------------------------------------------------------
                elif cmd == "TAXI":
                    if numargs == 0:
                        scr.echo("TAXI ON/OFF : OFF auto deletes traffic below 1500 ft")
                    else:
                        arg1 = args[0].upper()  # arguments are strings
                        traf.swtaxi = (arg1[:2] == "ON")

                #----------------------------------------------------------------------
                # SWRAD command: display switches of radar display
                # SWRAD GEO / GRID / APT / VOR / WPT / LABEL (toggle on/off or cycle)
                # (for WPT,APT,LABEL value is optional)
                #----------------------------------------------------------------------
                elif cmd == "SWRAD" or cmd[:4] == "DISP":
                    if numargs == 0:
                        scr.echo("SWRAD GEO / GRID / APT / VOR / " + \
                                 "WPT / LABEL / TRAIL [dt] / [value]")
                    else:
                        sw = args[0] # Which switch

                        if numargs==2:
                            arg = args[1] # optional argument
                        else:
                            arg = ""

                        # FIR boundaries
                        if sw == "TRAIL" or sw == "TRAILS":

                            traf.swtrails = not traf.swtrails
                            if numargs == 2:
                                try:
                                    trdt = float(args[1])
                                    traf.trails.dt = trdt
                                except:
                                    scr.echo("TRAIL ON dt")

                        elif scr.feature(sw,arg): # Toggle screen feature                        
                              scr.drawradbg() # When success: Force redraw radar background

                        else:
                            scr.redrawradbg = False # Switch not found

                #----------------------------------------------------------------------
                # TRAILS ON/OFF
                #----------------------------------------------------------------------
                elif cmd[:5] == "TRAIL":
                    if numargs == 0:
                        scr.echo("TRAIL ON/OFF [dt]/TRAIL acid color")
                        if traf.swtrails:
                            scr.echo("Trails are currently ON")
                            scr.echo("Trails dt=" + str(traf.trails.dt))
                        else:
                            scr.echo("Trails are currently OFF")
                    else:
                        if args[0] == "ON":
                            traf.swtrails = True
                            if numargs == 2:
                                try:
                                    trdt = float(args[1])
                                    traf.trails.dt = trdt
                                except:
                                    scr.echo("TRAIL ON dt")

                        elif args[0] == "OFF" or args[0] == "OF":
                            traf.swtrails = False
                            traf.trails.clear()

                        elif len(args[0]) != 0:
                            correctCommand = True
                            # Check if a color was selected
                            if len(args) == 1:
                                scr.echo('Syntax error')
                                scr.echo("TRAIL acid color")
                                correctCommand = False

                            if correctCommand:
                                acid = args[0]
                                color = args[1]

                                # Does aircraft exist?
                                idx = traf.id2idx(acid)
                                if idx < 0:
                                    scr.echo("TRAILS: " + acid + " not found.")
                                    idx = -1
                                
                                # Does the color exist?
                                if color not in ("BLUE", "RED", "YELLOW"):
                                    scr.echo("Color not found, use BLUE, RED or YELLOW")
                                    idx = -1

                                # Change trail color of aircraft for which there are data
                                if idx >= 0:
                                    traf.changeTrailColor(color, idx)
                                    # scr.echo("TRAIL color of " + acid + " switched to: " + color)
                        else:
                            scr.echo('Syntax error')
                            scr.echo("TRAILS ON/OFF")

                #----------------------------------------------------------------------
                # DIST lat1,lon1,lat2,lon2 : 
                #   calculate distance and direction from one pos to 2nd
                #----------------------------------------------------------------------
                elif cmd[:4] == "DIST":
                    if numargs == 0:
                        scr.echo("DIST lat1,lon1,lat2,lon2")
                    else:
                        try:
                            lat0 = float(args[0])  # lat 1st pos
                            lon0 = float(args[1])  # lon 1st pos
                            lat1 = float(args[2])  # lat 2nd pos
                            lon1 = float(args[3])  # lon 2nd pos
                            qdr, d = qdrdist(lat0, lon0, lat1, lon1)
                            scr.echo("Dist = " + str(round(d,3)) + \
                                 " nm   QDR = " + str(round(qdr,2)) + " deg")
                        except:
                            scr.echo("DIST: Syntax error")
                
                #----------------------------------------------------------------------
                # CALC  expression
                #----------------------------------------------------------------------
                elif cmd[:4] == "CALC":
                    if numargs == 0:
                        scr.echo("CALC expression")
                    else:
                        try:
                            x = eval(line[5:])  # lower for units!
                            scr.echo("Ans = " + str(x))
                        except:
                            scr.echo("CALC: Syntax error")

                #----------------------------------------------------------------------
                # LNAV acid ON/OFF   Switch LNAV (HDG FMS navigation) on/off
                #----------------------------------------------------------------------
                elif cmd == "LNAV":
                    if numargs == 0:
                        scr.echo("LNAV acid, ON/OFF")
                    else:
                        idx = traf.id2idx(args[0])

                        if idx<0:
                            if args[0]=="*":  # all aircraft
                               if args[1].upper() == "ON":
                                   traf.swlnav = np.array(traf.ntraf*[True])
                               elif args[1].upper() == "OFF":
                                   traf.swlnav = np.array(traf.ntraf*[False])
                               else:
                                   synerr = True
                            else:
                                scr.echo(args[0]+"not found")
                        else:
                            acid = traf.id[idx]
                            if numargs ==1:
                                if traf.swlnav[idx] == "ON":
                                    scr.echo(acid+": LNAV ON")
                                else:
                                    scr.echo(acid+": LNAV OFF")

                            else:
                                if args[1] == "ON":
                                    if traf.route[idx].nwp > 0: # If there are any waypoints defined
                                        traf.swlnav[idx] = True
        
                                        iwp = traf.route[idx].findact(traf,idx)
                                        traf.route[idx].direct(traf, idx, traf.route[idx].wpname[iwp])
                                    else:
                                        scr.echo("LNAV "+acid+": no waypoints or destination specified")
    
                                elif args[1] == "OFF":
                                    traf.swlnav[idx] = False

                #----------------------------------------------------------------------
                # VNAV acid ON/OFF  Switch VNAV (SPD+ALT FMS navigation)  on/off
                #----------------------------------------------------------------------
                elif cmd == "VNAV":
                    if numargs == 0:
                        scr.echo("VNAV acid, ON/OFF")
                    else:
                        idx = traf.id2idx(args[0])
                        if idx<0:
                            if args[0]=="*":  # all aircraft
                               if args[1] == "ON": # Only when LNAV is on!
                                   traf.swvnav = np.array(traf.ntraf*[True])*traf.swlnav
                               elif args[1] == "OFF":
                                   traf.swvnav = np.array(traf.ntraf*[False])
                               else:
                                   synerr = True
                            else:
                                scr.echo(args[0]+"not found")

                        elif numargs ==1:

                            acid = traf.id[idx]
                            if traf.swvnav[idx] == "ON":
                               scr.echo(acid+": VNAV ON")
                            else:
                                scr.echo(acid+": VNAV OFF")

                        else:
                            acid = traf.id[idx]
                            if args[1] == "ON":
                                if not traf.swlnav[idx]:   
                                    scr.echo(acid+": VNAV ON requires LNAV to be ON")
                                else:
                                    traf.swvnav[idx] = True
                                    # Activate AP setting by pressing Direct again
                                    if traf.route[idx].nwp>0: 
                                        traf.route[idx].direct( traf , idx,  \
                                           traf.route[idx].wpname[traf.route[idx].iactwp])

                            elif args[1] == "OFF":
                                traf.swvnav[idx] = False
                            else:
                                synerr = True

                #----------------------------------------------------------------------
                # ASAS ON/OFF  : switch ASAS on/off
                #----------------------------------------------------------------------
                elif cmd == "ASAS":
                    if numargs == 0:
                        scr.echo("ASAS ON/OFF")
                        if traf.dbconf.swasas:
                            scr.echo("ASAS is currently ON")
                        else:
                            scr.echo("ASAS is currently OFF")
                    else:
                        arg1 = args[0]  # arguments are strings
                        traf.dbconf.swasas = (arg1.upper() =="ON")
                            
                #----------------------------------------------------------------------
                # ADDWPT   : ADDWPT acid,(WPname / lat,lon),[alt],[spd],[afterwp]
                #----------------------------------------------------------------------
                elif cmd == "ADDWPT":
             
                    if numargs <= 1:
                        scr.echo( \
                        "ADDWPT acid, (wpname/lat,lon),[alt],[spd],[afterwp]")
                    
                    else:
                        acid = args[0]     # call sign
                           
                        i = traf.id2idx(acid) # Get index of this a/c
                        if i < 0:
                            scr.echo("ADDWPT: Aircraft "+ acid +" not found.")
                        else:
                            rte = traf.route[i]   # Get pointer to route object

                            # Default values
                            wpok =  False
                            alt = -999
                            spd = -999
                            afterwp = ""
                            
                            # Check for fly-by/fly-over switch per aircraft route
                            wpid = args[1]                            
                            if wpid=="FLYBY" or wpid=="FLY-BY":
                                traf.route[i].swflyby = True
                            elif wpid=="FLYOVER" or wpid=="FLY-OVER":
                                traf.route[i].swflyby = False
                            else:

                                if True: #try:
    
                                    # Get waypoint data
                                    # Is arg 2 a number? => lat,lon else waypoint name
                                    chkdig = args[1].replace("-","")  \
                                       .replace("+","").replace(".","")\
                                       .replace("N","").replace("S","")\
                                       .replace("E","").replace("W","")\
                                       .replace("'","").replace('"',"")

                                    if numargs>=3 and chkdig.isdigit():
          
                                        name    = traf.id[i] # use for wptname
                                        wptype  = rte.wplatlon
                                        lat     = txt2lat(args[1])
                                        lon     = txt2lon(args[2])
                                        if numargs>=4 and args[3]!="":
                                            alt = txt2alt(args[3])*ft
                                        if numargs>=5 and args[4]!="":
                                            spd = txt2spd(args[4],max(alt,traf.alt[i]))
                                        if numargs>=6:
                                            afterwp = args[5]
                                            if rte.wpname.count(afterwp)==0:
                                                scr.echo("Waypoint "+afterwp+" not found. "+
                                                "Waypoint added at end of route.")
                                                afterwp = ""
                                        
                                        wpok    = True

                                    # Is arg navaid/airport/waypoint name?
                                    elif numargs>=2:
                                        name    = args[1]  # search this wpname closest to
                                        wptype  = rte.wpnav
                                        lat     = traf.lat[i]  # a/c position as reference lat,lon 
                                        lon     = traf.lon[i]
                                        if numargs>=3 and args[2]!="":
                                            alt = txt2alt(args[2])*ft
                                        if numargs>=4 and args[3]!="":
                                            spd = txt2spd(args[3],max(alt,traf.alt[i]))
                                        if numargs>=5:
                                            afterwp = args[4]
                                            if rte.wpname.count(afterwp)==0:
                                                scr.echo("Waypoint ",afterwp," not found."+
                                                "waypoint added at end of route.")
                                                afterwp =""

                                        wpok    = True
    
                                    # Add the wpt to route
                                    if wpok: 
                                        wpidx = rte.addwpt(traf,i,name,wptype,lat,lon,alt,spd,afterwp)
                                        norig = int(traf.orig[i]!="")
                                        ndest = int(traf.dest[i]!="")
    
                                        if rte.nwp-norig-ndest==1: # first waypoint: make active
                                           rte.direct(traf,i,rte.wpname[norig]) #0 if no rig
                                           traf.swlnav[i] = True
    
                                    else:
                                        scr.echo(traf.id[i]+": waypoint not added")
                                        synerr = True
                                #except:
                                 #   scr.echo(traf.id[i]+": waypoint not added")
                                 #   synerr = True
                                
                #----------------------------------------------------------------------
                # DELWPT   : DELWPT acid,WPname
                #----------------------------------------------------------------------
                elif cmd == "DELWPT":

                    # Help text             
                    if numargs <= 1:
                        scr.echo( \
                        "DELWPT acid, wpname")

                    # Delete waypoint
                    else:
                        acid = args[0]     # call sign
                        i = traf.id2idx(acid) # Get index of this a/c
                        if i < 0:
                            scr.echo("DELWPT: Aircraft "+ acid +" not found.")
                        else:
                            rte = traf.route[i]   # Get pointer to route object
                        idx = rte.delwpt(args[1])
                        if idx==-1:
                            scr.echo("DELWPT: Waypoint "+args[1]+ \
                                           " not found in route of "+acid+".")

                #----------------------------------------------------------------------
                # DIRECT [TO] wpname: set active waypoint
                #----------------------------------------------------------------------
                elif cmd == "DIRECT":

                    # remove optional 'TO'                   
                    if numargs>=1 and args[0] == "TO":
                        del args[0]
                        numargs= numargs-1

                    # Check aircraft id, call route.direct function           
                    if numargs <= 1:
                        scr.echo("DIRECT acid, wpname")
                    else:
                        acid = args[0]           # call sign
                        i = traf.id2idx(args[0])    # Get index of this a/c
                        if i<0:
                            scr.echo("DIRECT: Aircraft "+args[0]+" not found.")

                        else:
                            # Go direct, check success
                           swok,vnavok = traf.route[i].direct(traf,i,args[1])
                           if swok:
                               traf.swlnav[i] = True
                               traf.swvnav[i] = vnavok
                           else:
                               scr.echo(acid+": DIRECT waypoint"+args[1] \
                                                 +" not found.")

                #----------------------------------------------------------------------
                #  LISTRTE acid, [pagenr]v   (7 wpts per page)
                #----------------------------------------------------------------------
                elif cmd == "LISTRTE":
                    if numargs < 1:
                        scr.echo("LISTRTE acid [pagenr]")
                    else:
                        acid = args[0]           # call sign
                        i = traf.id2idx(args[0])    # Get index of this a/c
                        if i<0:
                            scr.echo("LISTRTE: Aircraft "+args[0]+" not found.")

                        elif traf.route[i].nwp<=0 :
                            scr.echo("LISTRTE: Aircraft "+args[0]+" has no route.")
                        else:
                            nwp    = traf.route[i].nwp
                            npages = int((nwp+6)/7)
                            if numargs==1:
                                ipage = 0
                            else:
                                try:
                                    ipage = int(args[1])
                                except:
                                    synerr = True
                            
                            if not synerr:
                                traf.route[i].listrte(scr,ipage)
                                if ipage+1<npages:
                                    scr.cmdline("LISTRTE "+acid+","+str(ipage+1))

                #----------------------------------------------------------------------
                # ADSBCOVERAGE: Draw the coverage area of the To70 ADS-B antennas
                #----------------------------------------------------------------------
                elif cmd == "ADSBCOVERAGE":
                    if numargs == 0:
                        scr.echo("ADSBCOVERAGE ON/OFF")
                        if traf.swAdsbCoverage:
                            scr.echo("ADSB Coverage Area is currently ON")
                        else:
                            scr.echo("ADSB Coverage Area is currently OFF")
                    else:
                        if args[0] == "ON":
                            traf.swAdsbCoverage = True


                        elif args[0] == "OFF" or args[0] == "OF":
                            traf.swAdsbCoverage = False

                        else:
                            scr.echo('Syntax error')
                            scr.echo("ADSBCOVERAGE ON/OFF")

                elif cmd == "BOX":
                    if numargs == 0:
                        scr.echo(cmd + " name,lat1,lon1,lat2,lon2")
                    data = []
                    for i in args[1:]:
                        data.append(float(i))
                    scr.objappend(2, args[0], data)
                elif cmd[:4] == "POLY":
                    if numargs == 0:
                        scr.echo(cmd + " name,lat1,lon1,lat2,lon2,...")
                    data = []
                    for i in args[1:]:
                        data.append(float(i))
                    scr.objappend(4, args[0], data)
                elif cmd == "CIRCLE":
                    pass
                #------------------------------------------------------------------
                # LINE color,lat1,lon1,lat2,lon2 command: draw a line
                #------------------------------------------------------------------
                elif cmd[:4] == "LINE":

                    if numargs == 0:
                        scr.echo("LINE name,lat1,lon1,lat2,lon2")
                        scr.echo("color=red,green,cyan.. (8 basic colours)")
                    else:
                        if numargs == 5:
                                data = [float(args[1]), float(args[2]), float(args[3]), float(args[4])]
                                scr.objappend(1, args[0], data)

                #------------------------------------------------------------------
                # DUMPRTE acid: Dump the route to the route-file for debugging
                # 
                #------------------------------------------------------------------
                elif cmd[:7] == "DUMPRTE":
                    if numargs == 0:
                        scr.echo("DUMPRTE acid")
                    else:
                        acid = args[0]
                        i = traf.id2idx(acid)
                        
                        # Open file in append mode, write header
                        f = open("./data/output/routelog.txt","a")
                        f.write("\nRoute "+acid+":\n")
                        f.write("(name,type,lat,lon,alt,spd,toalt,xtoalt)  ")
                        f.write("type: 0=latlon 1=navdb  2=orig  3=dest  4=calwp\n")

                        # write flight plan VNAV data (Lateral is visible on screen)
                        for j in range(traf.route[i].nwp):
                            f.write( str(( j, \
                                  traf.route[i].wpname[j],  \
                                  traf.route[i].wptype[j],  \
                                  round(traf.route[i].wplat[j],4),   \
                                  round(traf.route[i].wplon[j],4),   \
                                  int(0.5+traf.route[i].wpalt[j]/ft),   \
                                  int(0.5+traf.route[i].wpspd[j]/kts),   \
                                  int(0.5+traf.route[i].wptoalt[j]/ft),   \
                                  round(traf.route[i].wpxtoalt[j]/nm,3) \
                                  )) + "\n")

                        # End of data
                        f.write("----\n")
                        f.close()

                #------------------------------------------------------------------
                # !!! This is a template, please make a copy and keep it !!!
                # Insert new command here: first three chars should be unique
                #------------------------------------------------------------------
                elif cmd[:3] == "XXX":
                    if numargs == 0:
                        scr.echo("cmd arg1, arg2")
                    else:
                        arg1 = args[0]  # arguments are strings
                        arg2 = args[1]  # arguments are strings

                #-------------------------------------------------------------------
                # Reference to other command files
                # Check external references
                #-------------------------------------------------------------------
                elif cmd[:4] in self.extracmdrefs:
                    self.extracmdrefs[cmd[:4]].process(cmd[4:], numargs, [cmd] + args, sim, traf, scr, self)

                #-------------------------------------------------------------------
                # Command not found
                #-------------------------------------------------------------------
                else:
                    if numargs==0:
                        scr.echo("Unknown command or aircraft: " + cmd)
                    else:
                        scr.echo("Unknown command: " + cmd)

                #**********************************************************************
                #======================  End of command branches ======================
                #**********************************************************************

                # Syntax not ok, => Default syntax error message:
                if synerr:
                    scr.echo("Syntax error in command:" + cmd)
                    scr.echo(line)


        # End of for-loop of cmdstack
        self.cmdstack = []
        return
