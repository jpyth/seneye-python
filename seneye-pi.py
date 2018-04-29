#!/usr/bin/env python
#
# Read Seneye SUD and publish readings to REST API
# Inspired by https://github.com/dhallgb/Seneye-MQTT and https://github.com/seneye/SUDDriver
#
import time
import usb.core, usb.util
import sys, json, pprint
from bitstring import BitArray
import urllib2
vendor=9463
product=8708
url="yoururladdresshere"

def printhex(s):
    return(type(s),len(s),":".join("{:02x}".format(c) for c in s))

def printbit(s): 
    return(type(s),len(s),":".join("{:02x}".format(c) for c in s))

def set_up():
    interface=0
    # find the device using product id strings
    dev = usb.core.find(idVendor=vendor, idProduct=product)
    dev.reset()
    if __debug__:
        print("device       >>>",dev)
    # release kernel driver if active
    if dev.is_kernel_driver_active(interface):
        dev.detach_kernel_driver(interface)

    # by passing no parameter we pick up the first configuration, then claim interface, in that order
    dev.set_configuration()
    usb.util.claim_interface(dev, interface)
    configuration = dev.get_active_configuration()
    interface = configuration[(0,0)]
    if __debug__:
        print("configuration>>>",configuration)
        print("interface    >>>",interface)

    # find the first in and out endpoints in our interface
    epIn = usb.util.find_descriptor(interface, custom_match= lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN)
    epOut = usb.util.find_descriptor(interface, custom_match = lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT)

    # were our endpoints found?
    assert epIn is not None
    assert epOut is not None
    if __debug__:
        print("endpoint in  >>>",epIn)
        print("endpoint out >>>",epOut)
    return dev, epIn, epOut, interface

def hello_sud(dev, epIn, epOut):
    msg="BYESUD"
    rc=dev.write(epOut,msg)
    # write to device with hello string
    msg="HELLOSUD"
    rc=dev.write(epOut,msg)
    if __debug__:
        print("HELO ret code>>>",rc)

    # read from device for HELLO
    attempts = 0
    while attempts < 8:
      hello_read=dev.read(epIn,epIn.wMaxPacketSize)
      if __debug__:
          print("HELO hex     >>>",printhex(hello_read))
      if hello_read[0] == 136:
        print "good response"
        break
      attempts = attempts + 1
      time.sleep(1)


def read_sud(dev,epIn,epOut):     
    msg="READING"
    write_rc=dev.write(epOut,msg)
    if __debug__:
        print("READ ret code>>>",write_rc)

    attempts =0
    while attempts < 8:
      read_read=dev.read(epIn,epIn.wMaxPacketSize)
      result_bitarray = BitArray(read_read)
      if read_read[0] == 0:
          if read_read[1] == 1:
            return(result_bitarray)
            break
      if __debug__:
          print("sensor hex   >>>",printhex(read_read))
          print("sensor bits len>",len(result_bitarray.bin))
          print("sensor bits  >>>",result_bitarray.bin)
      attempts = attempts + 1
      time.sleep(1)


def bye_sud(dev,epIn,epOut):
    msg="BYESUD"
    rc=dev.write(epOut,msg)
    if __debug__:
        print("BYE ret code >>>",rc)

def mungReadings(p, json=False):
    # see protocol.mdown for explaination of where the bitstrings start and end
    s={}
    i=36
    s['InWater']=p[i]
    s['SlideNotFitted']=p[i+1]
    s['SlideExpired']=p[i+2]
    ph=p[80:96]
    s['pH']=float(ph.uintle/100.00)   # divided by 100
    nh3=p[96:112]
    s['NH3']=float(nh3.uintle/1000.000)  # divided by 1000
    temp=p[112:144]
    s['Temp']=float(temp.intle/1000.00) # divided by 1000
    if __debug__:
        pprint.pprint(s)
    if json:
      j = json.dumps(s, ensure_ascii=False)
      return(j)
    return(s)

def clean_up(dev):
    interface=0
    # re-attach kernel driver
    usb.util.release_interface(dev, interface)
    dev.attach_kernel_driver(interface)
    # clean up
    usb.util.release_interface(dev, interface)
    usb.util.dispose_resources(dev)

def postToWeb(readings, url):
    
    for key in ["pH", "NH3", "Temp"]:
      result_dict={}
      result_dict["measurement"]=key
      result_dict["value"]=readings[key]
      req = urllib2.Request(url)
      req.add_header('Content-Type', 'application/json')
      response = urllib2.urlopen(req, json.dumps(result_dict))
      print json.dumps(result_dict)
    for key in ["InWater", "SlideNotFitted","SlideExpired"]:
      result_dict={}
      result_dict["name"]=key
      result_dict["status"]=readings[key]
      req = urllib2.Request(url)
      req.add_header('Content-Type', 'application/json')
      response = urllib2.urlopen(req, json.dumps(result_dict))
      print json.dumps(result_dict)

def main():
    # open device/find endpoints
    dev,epIn,epOut,interface = set_up()
    # send and read HELLOSUD
    hello_sud(dev,epIn,epOut)
    # send and read READING
    read_results=read_sud(dev,epIn,epOut)
    # send BYESUD
    bye_sud(dev,epIn,epOut)
    clean_up(dev)
    # parse to json
    readings=mungReadings(read_results)
    postToWeb(readings, url)

if __name__ == "__main__":
    main()
