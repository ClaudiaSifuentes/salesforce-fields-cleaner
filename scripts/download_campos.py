import os
from datetime import datetime

login_cmd = "sf force:auth:web:login -a pluz--dev -d --instance-url https://pluz--dev.sandbox.my.salesforce.com/"

fields_dir = "json_limpieza"
incoming_dir = f"{fields_dir}/incoming_objects"
objects = [
    {
        "label": "Account",
        "apiName": "Account" 
    }, {
        "label": "Contact",
        "apiName": "Contact"
    }, {
        "label": "Party_Relationship",
        "apiName": "PartyRelationship",
    }, {
        "label": "Premises",
        "apiName": "vlocity_cmt__Premises__c"
    }, {
        "label": "Service_Point",
        "apiName": "vlocity_cmt__ServicePoint__c"
    }, {
        "label": "Inventory_Item",
        "apiName": "vlocity_cmt__InventoryItem__c"
    }, {
        "label": "Case",
        "apiName": "Case"
    }, {
        "label": "Contract",
        "apiName": "Contract"
    }, {
        "label": "Asset",
        "apiName": "Asset"
    }, {
        "label": "Action_Plan",
        "apiName": "ActionPlan",
    }, {
        "label": "Action_Plan_Item",
        "apiName": "ActionPlanItem",
    }, {
        "label": "Quote",
        "apiName": "Quote"
    }, {
        "label": "Quote_Line_Item",
        "apiName": "QuoteLineItem"
    }, {
        "label": "Work_Order",
        "apiName": "WorkOrder"
    }, {
        "label": "Task",
        "apiName": "Task"
    }, {
        "label": "Payment_Adjustment",
        "apiName": "vlocity_cmt__PaymentAdjustment__c"
    }
]

# log in
os.system(login_cmd)

# create import fields directory
if not os.path.exists(fields_dir):
    os.makedirs(fields_dir)
if not os.path.exists(incoming_dir):
    os.makedirs(incoming_dir)

# get newest incoming files
for obj in objects:
    cmd_line = f'sf force:schema:sobject:describe --sobjecttype "{obj["apiName"]}" --json > {incoming_dir}/incoming-{obj["label"]}.json'
    print(f'Downloading {obj["label"]}...')
    os.system(cmd_line)
print(f'Done.')