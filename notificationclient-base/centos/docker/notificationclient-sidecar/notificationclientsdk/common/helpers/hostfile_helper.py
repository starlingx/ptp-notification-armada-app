#coding:utf8

import os
import sys
import re

def update_host(hostname, ip):
    hostsfile="/etc/hosts"
    Lines=[]
    replaced = False

    with open(hostsfile) as fd:
        for line in fd.readlines():
            if line.strip() == '':
                Lines.append(line)
            else:
                h_name = line.strip().split()[1]
                if h_name == hostname:
                    lin = "{0}    {1}".format(ip, hostname)
                    Lines.append(lin)
                    replaced = True
                else:
                    Lines.append(line)

    if replaced == False:
        Lines.append("{0}    {1}".format(ip, hostname))

    with open(hostsfile, 'w')  as fc:
	    fc.writelines(Lines)
