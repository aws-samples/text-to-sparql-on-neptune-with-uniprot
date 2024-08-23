"""
This module contains code that is shared amongst the Jupyter notebooks.
"""

from typing import Callable
import os
import re
import json
import csv
from pathlib import Path
from functools import partial
from typing import List, Union, Optional
from typing import Any as JsonType

import requests
from botocore.exceptions import ClientError
from botocore.awsrequest import AWSRequest
from botocore.auth import SigV4Auth

def get_neptune_env(var: str) -> str:
    """
    Return the value of a Neptune environment variable.
    """
    return os.popen(f"source ~/.bashrc ; echo ${var}").read().split("\n")[0]


def run_bedrock(system: str,
                messages: List,
                temperature: float,
                bedrock_runtime,
                model_id: str) -> str:
    """
    The input string is the prompt. Run the model on the prompt and return the response.
    """
    try:
        response = bedrock_runtime.invoke_model(
            modelId=model_id,
            body=json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1024,
                    "temperature": temperature,
                    "messages": [
                        {
                            "role": "user",
                            "content": [{"type": "text", "text": prompt}],
                        }
                    ],
                }
            ),
        )
        
        
        result = json.loads(response.get("body").read())
        output_list = result.get("content", [])
        return "".join(output["text"] for output in output_list
                       if output["type"] == "text")
    except ClientError as err:
        print(f"Error invoking {model_id}: {err.response['Error']['Code']} "
              f"{err.response['Error']['Message']}")
        raise err



# Grab Neptune cluster host/port from notebook instance environment variables
# Or manually set these values
GRAPH_NOTEBOOK_HOST = get_neptune_env("GRAPH_NOTEBOOK_HOST")
GRAPH_NOTEBOOK_PORT = get_neptune_env("GRAPH_NOTEBOOK_PORT")
GRAPH_NOTEBOOK_AUTH_MODE = get_neptune_env("GRAPH_NOTEBOOK_AUTH_MODE")
AWS_REGION = get_neptune_env("AWS_REGION")
USE_IAM_AUTH = GRAPH_NOTEBOOK_AUTH_MODE != "DEFAULT"
NEPTUNE_ENDPOINT = f"https://{GRAPH_NOTEBOOK_HOST}:{GRAPH_NOTEBOOK_PORT}/sparql"

def execute_sparql(query: str,
                   sagemaker_session,
                   crud_type: str = "query"):
    request_data = {crud_type: query}
    data = request_data
    request_hdr = None

    if USE_IAM_AUTH:
        credentials = sagemaker_session.get_credentials()
        credentials = credentials.get_frozen_credentials()
        access_key = credentials.access_key
        secret_key = credentials.secret_key
        service = "neptune-db"
        session_token = credentials.token
        params = None
        creds = SimpleNamespace(
            access_key=access_key,
            secret_key=secret_key,
            token=session_token,
            region=AWS_REGION
        )
        request = AWSRequest(
            method="POST", url=NEPTUNE_ENDPOINT, data=data, params=params
        )
        SigV4Auth(creds, service,AWS_REGION).add_auth(request)
        request.headers["Content-Type"] = "application/x-www-form-urlencoded"
        request_hdr = request.headers
    else:
        request_hdr = {}
        request_hdr["Content-Type"] = "application/x-www-form-urlencoded"

    response = requests.request(
        method="POST", url=NEPTUNE_ENDPOINT, headers=request_hdr, data=data
    )
    if str(response.status_code) != "200":
        print(f"Query error {response.status_code} {response.text}")
        print(f"Here is the query:\n{query}\n")
        print(f"CRUD type is *{crud_type}*")
        print(f"Here is the result:\n{response.text}\n")
        raise Exception({response.status_code, response.text})

    try:
        json_resp = json.loads(response.text)
        return json_resp
    except Exception as e:
        print("Exception: {}".format(type(e).__name__))
        print("Exception message: {}".format(e))
        print(f"Here is the query:\n{query}\n")
        print(f"CRUD type is *{crud_type}*")
        print(f"Here is the result:\n{response.text}\n")
        raise e
        
UNIPROT_REF_ENDPOINT="https://sparql.uniprot.org/sparql"
def execute_sparql_uniprotref(query: str):
    request_data = query.strip()
    data = request_data
    request_hdr = {}
    request_hdr["Content-Type"] = "application/sparql-query"
    request_hdr['Accept']='application/sparql-results+json'

    response = requests.request(
        method="POST", url=UNIPROT_REF_ENDPOINT, headers=request_hdr, data=data
    )
    if str(response.status_code) != "200":
        print(f"Query error {response.status_code} {response.text}")
        print(f"Here is the query:\n{query}\n")
        print(f"Here is the result:\n{response.text}\n")
        raise Exception({response.status_code, response.text})

    try:
        json_resp = json.loads(response.text)
        return json_resp
    except Exception as e:
        print("Exception: {}".format(type(e).__name__))
        print("Exception message: {}".format(e))
        print(f"Here is the query:\n{query}\n")
        print(f"Here is the result:\n{response.text}\n")
        raise e
        
def write_sparql_res(folder_name, file_prefix, question, expected_sparql, actual_sparql, res, error_msg):
    res_record = {
        'question': question, 
        'expected_sparql': expected_sparql,
        'actual_sparql': actual_sparql,
        'res': res,
        'error_msg': error_msg
    }
    with open(f"{folder_name}/{file_prefix}.json", 'w') as resfile: 
        resfile.write(json.dumps(res_record, indent=3))

        
def make_report(folder_name):

    files=os.listdir(folder_name)

    with open(f'{folder_name}_report.csv', 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["qfile","question", "numresults", "errormsg", "expected_sparql", "gen_sparql"])
        for fn in files:
            with open(f"{folder_name}/{fn}", 'r') as jfile: 
                j = json.load(jfile)
                index=fn.split(".")[0]
                nlq=j['question'].replace("\n", "")
                error_msg=j['error_msg'].replace("\n", "")
                expected_sparql=j['expected_sparql'].replace("\n", "")
                gen_sparql=j['actual_sparql'].replace("\n", "")
                res=j['res']
                num_results=len(res['results']['bindings']) if 'results' in res and 'bindings' in res['results'] else 0
                writer.writerow([index, nlq, num_results, error_msg, expected_sparql, gen_sparql])


