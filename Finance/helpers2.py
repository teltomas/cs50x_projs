import csv
import requests
import subprocess
import urllib
import uuid


def quote100():
    
    headers={"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"}
    res=requests.get("https://api.nasdaq.com/api/quote/list-type/nasdaq100",headers=headers)
    main_data=res.json()['data']['data']['rows']

    # for i in range(len(main_data)):
    #    print("Symbol: ", main_data[i]['symbol'], ". Name: ", main_data[i]['companyName'], ". Price: ", main_data[i]['lastSalePrice'])

    return main_data

