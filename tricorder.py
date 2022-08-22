import os
import subprocess
from serial import Serial
from pyubx2 import UBXReader
import time

import pytz
import datetime
import subprocess
import json

def setSystemTime(timestamp):
    subprocess.run(["date", "+%s", "-s", "@"+str(timestamp)])
    subprocess.run(["hwclock", "--hctosys"])


intervalCheckDevicesNoGPS = 10
intervalCheckDevicesGPS = 300
lastCheckDevices = 0
lastGoodGPS = 0
devices = dict()
noDevices = -1


def saveData( data ):
    t = datetime.datetime.fromtimestamp( data["timestamp"], datetime.timezone.utc)
    print("Writing "+ t.isoformat() )                    
    fileName = "{:04}-{:02}-{:02}_rasberrypi.txt".format( t.year, t.month, t.day)
                                                           
    outputFile = open("data_files_rasberry/" + fileName,"a")
    outputFile.write(json.dumps(data,indent=3,sort_keys=True))
    outputFile.write("\n" + "*"*32 + "\n")               
    outputFile.close()         



def checkForShutdown():
        global noDevices
        global devices
        if devices == dict() and noDevices == -1:
            print("noDevices set")
            noDevices = time.time()
        if devices != dict():
            noDevices = -1
        if noDevices != -1 and time.time() - noDevices > 60:
            print("Shutdown")
            exit()


def checkDeviceChanges():
    global devices
    devicesNow = set()
    try:
        pathList = os.listdir("/dev/serial/by-path")
    except:
        print("No serial devices")
        pathList = []
    for dev in pathList:
        devicesNow.add(dev)
    checkForShutdown()
    if set(devices.keys()) == devicesNow:
        return False
    else:
        return True

def saveDeviceChanges():
    global devices
    global noDevices

    for dev in devices.keys():
        if "stream" in devices[dev]:
            devices[dev]["stream"].close()

    devices = dict()

    try:
        pathList = os.listdir("/dev/serial/by-path")
    except:
        print("No serial devices")
        pathList = []

    for dev in pathList:
        devices[dev] = dict()
        for x in range(3):
            if "model" not in devices[dev].keys():
                result = subprocess.run( "ubxtool -f /dev/serial/by-path/" + dev + " -p MON-VER", stdout=subprocess.PIPE, shell=True)
                #result = subprocess.run("ls", stdout=subprocess.PIPE)
                for line in result.stdout.decode("utf-8").split("\n"):
                    if "extension MOD=" in line:
                        print(line[16:])
                        devices[dev]["model"] = line[16:]

            if "serial" not in devices[dev].keys():
                result = subprocess.run( "ubxtool -f /dev/serial/by-path/" + dev + " -p SEC-UNIQID", stdout=subprocess.PIPE, shell=True)
                #result = subprocess.run("ls", stdout=subprocess.PIPE)
                for line in result.stdout.decode("utf-8").split("\n"):
                    if "uniqueId" in line:
                        print(line.split(" ")[8])
                        devices[dev]["serial"] = line.split(" ")[8]

        if "model" not in devices[dev].keys() or "serial" not in devices[dev].keys():
            devices.pop(dev) 
        checkForShutdown()

def recordData():
    global devices
    for dev in devices.keys():
        if devices[dev]["model"] == "ZED-F9P" or devices[dev]["model"] == "NEO-M9N":
            if "stream" not in devices[dev].keys():
                devices[dev]["stream"] = Serial('/dev/serial/by-path/'+dev, 9600, timeout=3)
                devices[dev]["ubxreader"] = UBXReader( devices[dev]["stream"] )
            try:
                ubx = devices[dev]["ubxreader"].read()
            except:
                if "error count" not in devices[dev].keys():
                    devices[dev]["error count"] = 1
                else:
                    devices[dev]["error count"] = devices[dev]["error count"] + 1
                print( "Error reading from " + dev + " count: " + str(devices[dev]["error count"]) )
                if( devices[dev]["error count"] > 10): 
                    if "stream" in devices[dev]:
                        devices[dev]["stream"].close()
                    devices.pop ( dev )
                break;

            UBX_PVT = ubx[1]

            print(UBX_PVT)
            if (UBX_PVT.validDate == True and UBX_PVT.fullyResolved == True and UBX_PVT.gnssFixOk == True and UBX_PVT.confirmedDate == True and
                UBX_PVT.confirmedTime == True and (UBX_PVT.fixType == 3 or UBX_PVT.fixType == 4) and UBX_PVT.invalidLlh == False):
                lastGoodGPS = time.time()
                
                year             = UBX_PVT.year
                month            = UBX_PVT.month
                day              = UBX_PVT.day
                hour             = UBX_PVT.hour
                minute           = UBX_PVT.min
                second           = UBX_PVT.second
                microsecondDelta = (UBX_PVT.nano // 1000)

                tzUnaware = datetime.datetime( year, month, day, hour, minute, second ) + datetime.timedelta( microseconds = microsecondDelta)
                tzAware   = pytz.utc.localize( tzUnaware )
                print( tzAware.timestamp() )
                if( abs( tzAware.timestamp()  - time.time()) > 2):
                    setSystemTime( tzAware.timestamp() )

                timestamp = tzAware.timestamp() + 100

                #<UBX(NAV-PVT, iTOW=00:00:01, year=2020, month=3, day=22, hour=0, min=0, second=19, validDate=0, validTime=0, fullyResolved=0, validMag=0, tAcc=4294967295, nano=0, fixType=0, gnssFixOk=0, difSoln=0, psmState=0, headVehValid=0, carrSoln=0, confirmedAvai=1, confirmedDate=0, confirmedTime=0, numSV=0, lon=0.0, lat=0.0, height=0, hMSL=-17000, hAcc=4294967295, vAcc=3750000128, velN=0, velE=0, velD=0, gSpeed=0, headMot=0.0, sAcc=20000, headAcc=180.0, pDOP=99.99, invalidLlh=0, lastCorrectionAge=0, reserved0=1044519020, headVeh=0.0, magDec=0.0, magAcc=0.0)>
                data = { "measurement type" : "location - gps",
                         "source"           : devices[dev]["model"],
                         "serial"           : devices[dev]["serial"],
                         "timestamp"        : timestamp,
                         "accuracy, time"   : UBX_PVT.tAcc,
                         "data"             : [ {
                            "latitude"                  : UBX_PVT.lat,
                            "longitude"                 : UBX_PVT.lon,
                            "accuracy, horizontal"      : UBX_PVT.hAcc / 1000,
                            "altitude"                  : UBX_PVT.height / 1000,
                            "accuracy, vertical"        : UBX_PVT.vAcc / 1000,
                            "fix type"                  : {3 : "GNSS 3D", 
                                                           4 : "GNSS + dead reckoning" }[ UBX_PVT.fixType],
                            "satellites, used"          : UBX_PVT.numSV,
                            "velocity, north"           : UBX_PVT.velN / 1000,
                            "velocity, east"            : UBX_PVT.velE / 1000,
                            "velocity, down"            : UBX_PVT.velD / 1000,
                            "speed"                     : UBX_PVT.gSpeed / 1000,
                            "speed, accuracy"           : UBX_PVT.sAcc / 1000,
                            "heading, motion"           : UBX_PVT.headMot,
                            "heading, motion, accuracy" : UBX_PVT.headAcc




                         }]

                }

                saveData(data)


while True:
    if ((time.time() - lastGoodGPS < 10 and  time.time() > lastCheckDevices + intervalCheckDevicesGPS) or
        (time.time() - lastGoodGPS > 10 and time.time() > lastCheckDevices + intervalCheckDevicesNoGPS)):
        if checkDeviceChanges():
            saveDeviceChanges()
        lastCheckDevices = time.time() 
    recordData()
