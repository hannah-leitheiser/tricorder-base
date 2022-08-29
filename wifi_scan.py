import subprocess
import dateutil.parser as parser
import datetime
import time
import json

acceptableAge = 3
interval = 30

def saveData( data ):
    t = datetime.datetime.fromtimestamp( data["timestamp"], datetime.timezone.utc)
    print("Writing "+ t.isoformat() )                    
    fileName = "rasberry_wifi_{:04}-{:02}-{:02}.txt".format( t.year, t.month, t.day)
                                                           
    outputFile = open("/home/pi/data_files_rasberry/" + fileName,"a")
    outputFile.write(json.dumps(data,indent=3,sort_keys=True))
    outputFile.write("\n" + "*"*32 + "\n")               
    outputFile.close()   

time.sleep(interval)

bootTime = subprocess.getoutput("uptime -s")
bT= parser.parse(bootTime)

while True:

    scan = subprocess.getoutput("sudo iw wlan0 scan").split("\n")


    data = { "measurement type" : "wifi scan",
             "source"           : "Rasberry Pi 3 B+",
             "data"             : [] }

    wifiData = dict()
    for line in scan:
        line = line + "\n"
        if "BSS" in line[:3]:
            if wifiData != dict():
                data["data"].append(wifiData)
                
            wifiData = dict()
            wifiData["BSSID"] = line[4:4+3*6-1]
        if "\tlast seen: " in line[:12] and "s [boottime]" in line:
            secondsSinceBoot = float(line[12:].split("s [boottime]\n")[0])
            timeStamp =  (bT + datetime.timedelta( seconds = secondsSinceBoot)).timestamp()
            wifiData["timestamp"] = timeStamp

        if "\tfreq: " in line[:7]:
            freq = line[7:].split("\n")[0]
            wifiData["frequency"] = freq
        
        if "\tSSID: " in line[:7]:
            ssid = line[7:].split("\n")[0]
            wifiData["SSID"] = ssid

        if "\tsignal: " in line[:9]:
            ssid = line[9:].split("dBm\n")[0]
            wifiData["level"] = float(ssid)

        if "\tPower constraint: " in line[:19]:
            p = line[19:].split(" dB\n")[0]
            wifiData["transmit power, constraint"] = float(p)

        if "\tTPC report: TX power: " in line[:23]:
            p = line[23:].split(" dBm\n")[0]
            wifiData["transmit power"] = float(p)


        if "\t\t * channel width: 1 (" in line[:23]:
            w=line[23:].split(")\n")[0]
            wifiData["bandwidth"] = w.replace(" ","")

    timestamps = list()
    for d in data["data"]:
        timestamps.append(d["timestamp"])
    if len(timestamps) > 0:
        print("age: {}".format( time.time() - min(timestamps)) )
        if( time.time() - min(timestamps) < acceptableAge ):
            data["timestamp"] = max(timestamps)
            saveData(data)
    else:
        data["timestamp"] = time.time()
        saveData(data)

    time.sleep(interval)
