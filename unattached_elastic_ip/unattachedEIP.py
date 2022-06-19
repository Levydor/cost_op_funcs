import boto3
from datetime import datetime, timedelta 
import os, sys
import boto3
import botocore
from botocore.exceptions import ClientError


regions = ["us-east-2","us-east-1","us-west-1","us-west-2",
                 "ap-south-1", "ap-northeast-3","ap-northeast-2",
                 "ap-southeast-1","ap-southeast-2","ap-northeast-1",
                 "ca-central-1","eu-central-1","eu-west-1","eu-west-2",
                 "eu-west-3","eu-north-1","sa-east-1"]


def validateEnvironmentVariables():
    # make sure to update IGNORE_WINDOW to < 1  for min amount of days is 1
    if(int(os.environ["IGNORE_WINDOW"]) < 1 or int(os.environ["IGNORE_WINDOW"]) > 90):
        print("Invalid value provided for IGNORE_WINDOW. Please choose a value between 1 day and 90 days.")
        raise ValueError('Bad IGNORE_WINDOW value provided')


def getCloudTrailEvents(startDateTime, rgn):
    # gets CloudTrail events from startDateTime until "now"
    cloudTrail = boto3.client('cloudtrail', region_name=rgn)
    attrList = [{'AttributeKey': 'ResourceType', 'AttributeValue': 'AWS::EC2::EIP'}]
    eventList = []
    response = cloudTrail.lookup_events(LookupAttributes=attrList, StartTime=startDateTime, MaxResults=50)
    eventList += response['Events']
    while('NextToken' in response):
        response = cloudTrail.lookup_events(LookupAttributes=attrList, StartTime=startDateTime, MaxResults=50, NextToken=response['NextToken'])
        eventList += response['Events']
    return eventList
    

def getRecentEIP(events):
    # parses volumes from list of events from CloudTrail
    recentEIPList = []
    for e in events:
        for i in e['Resources']:
            if i['ResourceType'] == 'AWS::EC2::EIP':
                recentEIPList.append(i['ResourceName'])
    recentEIPset = set(recentEIPList) # remove duplicates
    return recentEIPset


def elastic_ips_cleanup(region):
    """ Cleanup Unattached elastic IPs that are not being used more than Ignore window """
    client = boto3.client('ec2', region_name=region)
    addresses_dict = client.describe_addresses()
    addresses_count = len(addresses_dict['Addresses'])
    if addresses_count>0:
        for eip_dict in addresses_dict['Addresses']:
            if "NetworkInterfaceId" not in eip_dict:
                print (eip_dict['PublicIp'] +
                       " doesn't have any instances associated, releasing")
                client.release_address(AllocationId=eip_dict['AllocationId'], DryRun=True)
    return addresses_count
        

def lambda_handler(event, context):
    print("boto3 version:"+boto3.__version__)
    print("botocore version:"+botocore.__version__)
    for rgn in regions:
        try:
            validateEnvironmentVariables()
        except ValueError as vErr:
            print(vErr)
            sys.exit(1)
        startDateTime = datetime.today() - timedelta(int(os.environ["IGNORE_WINDOW"])) # IGNORE_WINDOW defined in environment variables
        eventList = getCloudTrailEvents(startDateTime, rgn)
        unattachedEIP = getRecentEIP(eventList)
        if unattachedEIP != None:
            try:
                adrs_count = elastic_ips_cleanup(rgn)
                if adrs_count > 0:
                    print(f'Cleaned {adrs_count} Unattached Elastic IP in region: {rgn}')
            except ClientError as err:
                print(f'unattachedEIP error: {err}')
        else:
            print(f'No Unattached Elastic IP in region: {rgn}')
