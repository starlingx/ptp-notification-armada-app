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
            if line.strip() == '' or line.startswith('#'):
                Lines.append(line)
            else:
                h_name = line.strip().split()[1]
                if h_name == hostname:
                    lin = "{0}    {1}\n".format(ip, hostname)
                    Lines.append(lin)
                    replaced = True
                else:
                    Lines.append(line)

    if replaced == False:
        Lines.append("\n{0}    {1}\n".format(ip, hostname))

    with open(hostsfile, 'w')  as fc:
	    fc.writelines(Lines)
