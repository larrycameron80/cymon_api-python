#Miclain Keffeler
#6/8/2017 
import requests
import sys
import json
from sqlalchemy import create_engine
from sqlalchemy.sql.expression import literal_column
from sqlalchemy.orm import sessionmaker
from sqlalchemy import types
from sqlalchemy import Column, Text, ForeignKey, Integer, String
from optparse import OptionParser
import hashlib
import base64
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from build_database import IP_Current, IP_History
from sqlalchemy import exists
import dateutil.parser
from sqlalchemy.sql.expression import literal_column
from configparser import ConfigParser

config = ConfigParser()
config.read('config.ini')
token = config.get('DEFAULT', 'TOKEN')                          #Get API Key and Password from Config.INI file


engine = create_engine('sqlite:///pull_feeds/IP_Report.db')   #Setup the Database
DBSession = sessionmaker(bind = engine)
session = DBSession()           #Must be able to query database
output = open(sys.argv[2]+".json","w")    #Output all downloaded json to a file

whois = ""
def send_request(apiurl, scanurl, headers,output):   #This function makes a request to the X-Force Exchange API using a specific URL and headers. 
    print apiurl
    response = requests.get(apiurl, params='', headers=headers, timeout=20)
    all_json = response.json()
    output.write(json.dumps(all_json,indent=4,sort_keys=True))
    return all_json

def get_md5(filename):     #This function returns the MD5 hash of a provided file
    try:
        f = open(filename,"rb")
        md5 = hashlib.md5((f).read()).hexdigest()
        return md5
    except e:
        print str(e)

def check_ip_exist(Table,Provided_IP):           #This function confirms whether or not an entry already exists. If so, it returns the entry 
    while(1):
        count = session.query(Table).filter(Table.IP == Provided_IP).count()  
        if count > 0:               #If the entry for this IP exists already (There is 1 occurence of this IP in the table)
            return session.query(Table).filter(Table.IP == Provided_IP).one()
        else:
            new_IP = Table(IP = Provided_IP)
            session.add(new_IP)
            session.commit()
            return 0

def update_both_tables(column_number,input_string,Provided_IP):              #This function will update both current and historic tables for a given column
    columns = ["IP","Location","Date","Score","Category","registrar_name","registrar_organization"]
    columner1 = str(columns[column_number])
    
    input_current = session.query(IP_Current).filter(IP_Current.IP == Provided_IP).one()
    setattr(input_current,str(literal_column(str(columner1))),str(input_string))         #Update current table with new information
    session.commit()
    
    input_historic = session.query(IP_History).filter(IP_History.IP == Provided_IP).one()
    setattr(input_historic,str(literal_column(str(columner1))),str(input_string))   #Update historic table with new information
    session.commit()

def date_parse(date_string):                          #This function parses the date that comes from the raw JSON output and puts it in a Month/Day/Year format
    parsed_date = dateutil.parser.parse(date_string).strftime("%x")
    return parsed_date

def get_current_info(column_number,review_count,Provided_IP,all_json):             #This function pulls current information from JSON output for a handful of keys
     
    keys = ["tag","updated"]
    attr = keys[column_number]                              #Declarations
    key_count = 0
    current_info = ""

    if attr == "updated":   #If the attribute we are looking for is the created date or score
        return all_json["results"][0][attr]
    else:
        return all_json["results"][0][attr]  #For every report except the most recent report (Which is current, not history)

if __name__ == "__main__":
    Provided_IP = str(sys.argv[2])

    headers = {'Authorization': token}
    url = "https://cymon.io"


    parser = OptionParser()
    parser.add_option("-i", "--ip", dest="s_ip" , default="none",
                      help="ip to be checked on cymon", metavar="ipaddress")                                           #Use this option to check an IP address
(options, args) = parser.parse_args()

IP_exists = check_ip_exist(IP_Current,Provided_IP)              #Check if the IP provided exists in the table already. If so, they we don't need to create another entry
IP_exists_history = check_ip_exist(IP_History,Provided_IP)


if (options.s_ip is not "none"):    #If the -i option was used
    scanurl = options.s_ip
    apiurl = url + "/api/nexus/v1/ip/" + scanurl + "/events/"
    all_json = send_request(apiurl, scanurl, headers,output)
    apiurl = url + '/api/nexus/v1/ip/' + scanurl + '/domains/'
    domain_json = send_request(apiurl,scanurl,headers,output)
IP_Location = domain_json["results"][0]['name']
print IP_Location
     #Used to hold categories of an IP or URL that have already been listed in the report.
update_both_tables(1,IP_Location,Provided_IP)


already_categorized=[]
current_categories = ""
key_count = 0                                           #Declarations
category_count = 0
review_count = 0
update_both_tables(4,get_current_info(0,review_count,Provided_IP,all_json),Provided_IP)             #Update Categorization of IP on Current Table   ***TO_DO*** (needs to only update current, not historic) ***TO_DO***
update_both_tables(1,IP_Location,Provided_IP)
review_count =0 
for key in all_json['results']:    #For every entry in the json output 
    if(key['tag'] in already_categorized):                               #If this categorization has already been reported, don't report it again
        continue
    else:       #Since we already have this IP in our DB,
            
            
        update_historic_category = session.query(IP_History).filter(IP_History.IP == Provided_IP).one()
        if category_count == 0:    #If this is the first categorization that has been assigned to this IP
            update_historic_category.Category = str(key['tag'])
            category_count += 1
        else:   #Otherwise we need commas and to keep what was already in there
            update_historic_category.Category = update_historic_category.Category + " , " + str(key['tag'])
            category_count += 1 
        session.commit()


        already_categorized.append(key['tag'])   #Add the category to the list of already printed categories so we don't repeat

update_both_tables(2,date_parse(str(get_current_info(1,review_count,Provided_IP,all_json))),Provided_IP)   #Adds the latest security check on this IP address to IP_Current Table information
if len(sys.argv[1:]) == 0:
    parser.print_help()
