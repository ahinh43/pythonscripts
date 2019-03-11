from requests import session
from operator import itemgetter
import string
import os
import re
import argparse
import xml.etree.ElementTree as ET
import json
import sys

# Configurable metrics grabber via json file
# Modified to allow multiple metrics to be grabbed at once using a json config file

global args

WEBLOGIC_HOST="Host"
WEBLOGIC_PORT="Port"
WEBLOGIC_USERNAME="weblogic_username"
WEBLOGIC_PASSWORD = open("/path/to/passwordfile")
WEBLOGIC_PASSWORD = WEBLOGIC_PASSWORD.read()
WEBLOGIC_PASSWORD = WEBLOGIC_PASSWORD.strip('\n')

def get_xpath_nodes_from_tree(element,xpath):
    return element.findall(xpath)

def print_et(et):
    print ET.tostring(et, encoding='utf8')

def get_et_from_string(res):
    return ET.fromstring(res)

def get_rows_from_tbml(tbml_et):
    return get_xpath_nodes_from_tree(tbml_et,'./table/row')

def get_columns_from_row(row_et):
    return get_xpath_nodes_from_tree(row_et,'./column')

def get_name_value_from_column(column_et):
    return column_et.get('name'),column_et.text

def exceldecimal(s):                   # voor de excel gebruikers
  return(re.sub('\.',',',s))          # decimale . naar ,

payload = {
     'j_username': WEBLOGIC_USERNAME,
     'j_password': WEBLOGIC_PASSWORD
}

s = session()
baseurl = 'http://'+WEBLOGIC_HOST+':'+WEBLOGIC_PORT
s.post(baseurl+'/dms/j_security_check', data=payload)
# Opens the dms config file to read whuch metrics to take
try:
   dmsConfigFile = open('/path/to/dmsConfig.json')
   y = dmsConfigFile.read()
   dmsConfig = json.loads(y)
# If we get an error, prints out an error text in a non-influx line protocol. Telegraf will not be able to parse these lines and will keep throwing errors in the logs until it is fixed.
except ValueError:
   print ('Error parsing config')
   sys.exit()
tagString = {}
fieldString = {}
for metric in dmsConfig:
   response = s.get(baseurl+'/dms/index.html?format=xml&cache=false&prefetch=false&table={metricName}&orderby=Name'.format(metricName=metric))
   nonamespacexml = re.sub(' xmlns="[^"]+"', '', response.text, count=1)
   tbml_et = get_et_from_string(nonamespacexml)
   rows = get_rows_from_tbml(tbml_et)
   resultDict = {}
   tagString[metric] = '{},'.format(metric)
   fieldString[metric] = {}
   appName = ''
   for index, row in enumerate(rows):
     resultDict[index]={}
     columns = get_columns_from_row(row)
     for column in columns:
       k,v = get_name_value_from_column(column)
       # Almost every DMS metric has a Name field in there, so we will use that to sort out metrics based on application name.
       if k == 'Name':
         if ' ' in v:
            v = v.replace(' ', '\\ ')
         appName = v
       for label in dmsConfig[metric]:
           if label == 'Fields':
               # This try block will test to see if the dictionary object already exists. If there is no dictionary, Python should be throwing a TypeError which is caught in the exception. Otherwise, it should pass.
               # Instead, if it DOES pass, is it a dict type? If not, then something went wrong by design.
               try:
                   if (type(dmsConfig[metric][label][appName]) is not dict):
                      print ('The type for label is not dict')
               except KeyError:
                   dmsConfig[metric][label][appName] = {}
               for key in dmsConfig[metric][label]['Variables']:
                  if k == key:
                     dmsConfig[metric][label][appName][key] = ""
                     dmsConfig[metric][label][appName][key] = v
           elif label == 'Tags':
               for key in dmsConfig[metric][label]:
                  if k == key:
                     dmsConfig[metric][label][key] = v
#  Builds the tags and field lines separately, then bring them together in one last string.
   for key in dmsConfig[metric]['Tags']:
      tagString[metric] += ('{key}={keyvalue},'.format(key=key, keyvalue=dmsConfig[metric]['Tags'][key]))
# Build the field string
   for item in dmsConfig[metric]['Fields']:
      if item == 'Variables':
         continue
      fieldString[metric][item] = 'AppName={item} '.format(item=item)
      # Ignore the variables field, as that is supposed to be just a template.
      for key in dmsConfig[metric]['Fields'][item]:
         fieldString[metric][item] += ('{key}={keyvalue},'.format(key=key, keyvalue=dmsConfig[metric]['Fields'][item][key]))
      fieldString[metric][item] = fieldString[metric][item][:-1]
      if fieldString[metric][item] != 'AppName={item}'.format(item=item):
         print (tagString[metric] + fieldString[metric][item])



