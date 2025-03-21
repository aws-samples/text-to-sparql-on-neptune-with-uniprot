"""
This module contains code that is shared amongst the Jupyter notebooks.
"""

from typing import Tuple
import os
import re
import json
import shutil
from pathlib import Path
from typing import List
from typing import Any as JsonType
from time import sleep
from itertools import count

import requests
import boto3
from botocore.exceptions import ClientError
from botocore.awsrequest import AWSRequest
from botocore.auth import SigV4Auth


def extract_tag(response: str, name: str, greedy: bool = True) -> Tuple[str, int]:
    """
    >>> extract_tag("foo <a>baz</a> bar", "a")
    ('baz', 10)

    """
    patn = f"<{name}>(.*)</{name}>" if greedy else\
           f"<{name}>(.*?)</{name}>"
    match = re.search(patn, response, re.DOTALL)
    if match:
        return match.group(1).strip(), match.end(1)
    else:
        #print(f"Couldn't find tag <{name}>; trying without")
        patn2 = f"(.*)</{name}"
        match2 = re.search(patn2, response, re.DOTALL)
        if match2:
            return match2.group(1).strip(), match2.end(1)
        else:
            #print(f"Couldn't find tag <{name}> or </{name}>; giving up")
            return None, -1


def extract_multiple_tags(response: str, name: str) -> List[str]:
    result = []
    for iter in count(0):
        if iter > 50:
            return result
        contents, next_idx = extract_tag(response, name, greedy=False)
        # print(f"contents {contents} next_idx {next_idx}")
        if contents is None:
            return result
        result.append(contents)
        response = response[next_idx+len(name)+3:]
        # print(f"response -> {response}\n-----------")


'''
Get Neptune notebook environment variable
'''
def get_neptune_env(var: str) -> str:
    """
    Return the value of a Neptune environment variable.
    """
    return os.popen(f"source ~/.bashrc ; echo ${var}").read().split("\n")[0]

'''
Invoke Bedrock runtime for given model_id using specified system, messages, temperature.
Return LLM response.
'''
def run_bedrock(system: str,
                messages: List,
                temperature: float,
                bedrock_runtime,
                model_id: str) -> str:
    """
    The input string is the prompt. Run the model on the prompt and return the response.
    """
    for retry in range(20):
        try:
            response = bedrock_runtime.invoke_model(
                modelId=model_id,
                body=json.dumps(
                    {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 1024,
                        "temperature": temperature,
                        "system": system,
                        "messages": messages
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
            if "ThrottlingException" in str(err):
                print(f"Throttled; retry #{retry}")
                sleep(10 * retry)
            else:
                raise ex
    return None


# Grab Neptune cluster host/port from notebook instance environment variables
# Or manually set these values
GRAPH_NOTEBOOK_HOST = get_neptune_env("GRAPH_NOTEBOOK_HOST")
GRAPH_NOTEBOOK_PORT = get_neptune_env("GRAPH_NOTEBOOK_PORT")
GRAPH_NOTEBOOK_AUTH_MODE = get_neptune_env("GRAPH_NOTEBOOK_AUTH_MODE")
AWS_REGION = get_neptune_env("AWS_REGION")
USE_IAM_AUTH = GRAPH_NOTEBOOK_AUTH_MODE != "DEFAULT"
NEPTUNE_ENDPOINT = f"https://{GRAPH_NOTEBOOK_HOST}:{GRAPH_NOTEBOOK_PORT}/sparql"

'''
Run SPARQL query against Neptune database.
Return SPARQL result.
'''
def execute_sparql(query: str,
                   sagemaker_session=None,
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

'''
Run SPARQL query against Uniprot reference site.
Return SPARQL result.
'''

UNIPROT_REF_ENDPOINT = "https://sparql.uniprot.org/sparql"
UNIPROT_TIMEOUT_SEC = 60 * 20

def execute_sparql_uniprotref(query: str, session=None):

    request_data = query.strip()
    data = request_data
    request_hdr = {}
    request_hdr["Content-Type"] = "application/sparql-query"
    request_hdr['Accept']='application/sparql-results+json'

    response = requests.request(
        method="POST", url=UNIPROT_REF_ENDPOINT, headers=request_hdr,
        data=data,
        timeout=UNIPROT_TIMEOUT_SEC
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
 
'''
Write a SPARQL result to {folder_name}/{file_prefix}.json
The file is a JSON that contains:
- question: The natural language question
- expected_sparql: The SPARQL we expect for that question
- actual_sparql: The SPARQL actually generated for that question
    If you pass a string, that string is the actual sparql
    If you pass an array of two strings, the first is the originally-generated SPARQL; the second is the SPARQL with suggestions incorporated
- res: The SPARQL result from running the actual_sparql
- error_msg: If there was an error running the SPARQL
- is_orig_used:
    If you pass an array for actual_sparql, pass True if the actual SPARQL is the first (original) value; pass False if the actual is the second.
- attempt: 1 for first attempt; 2, 3, .. for retries
    If attempt>1, backup the result for previous attempt as {folder_name}/{file_prefix}_{attempt-1}.json
'''

ERR_TIMEOUT = "timeout"
ERR_BLANK = "blank"
ERR_OTHER = "x"
ERR_NONE = ""

def write_sparql_res(folder_name, file_prefix, question, expected_sparql, actual_sparql, res, error_msg, 
                     is_orig_used=False, attempt=1):
    print(f"Writing results to {folder_name}")
    print("Results:")
    pprint_sparql_results(res)
    # retry logic
    file_name=f"{folder_name}/{file_prefix}.json"
    attempt_file_name=f"{folder_name}/{file_prefix}_{attempt-1}.json"    
    if attempt>1:
        shutil.copy(file_name, attempt_file_name)

    #
    # error logic
    #
    def is_blank(res):
        if  'boolean' in res:
            return False
        if not ("head" in res) or not("vars" in res["head"]):
            return False
        return not ("results" in res) or not("bindings" in res["results"]) or (len(res["results"]["bindings"]) == 0)

    # Based on error message, also set error_type
    error_type=ERR_NONE 
    if len(error_msg) > 0:
        if "Read timed out" in error_msg:
            error_type=ERR_TIMEOUT
        else:
            error_type=ERR_OTHER
    elif is_blank(res):
        # no results is a blank error
        error_type=ERR_BLANK
        
    # classify the sparql query
    act_list = isinstance(actual_sparql, list)
    initial_sparql = actual_sparql[0] if act_list else None
    improved_sparql = actual_sparql[1] if act_list else None
    actual_sparql = actual_sparql[2] if act_list else actual_sparql
    
    # ok write it
    res_record = {
        'question': question, 
        'expected_sparql': expected_sparql,
        'initial_sparql': initial_sparql,
        'improved_sparql': improved_sparql,
        'actual_sparql': actual_sparql,
        'is_orig_used': is_orig_used,
        'res': res,
        'error_msg': error_msg,
        'error_type': error_type,
        'attempt': attempt
    }
    with open(file_name, 'w') as resfile: 
        resfile.write(json.dumps(res_record, indent=3))
    return res_record

PREFIXES = {
    "http://purl.uniprot.org/taxonomy/": "taxon"
}

def shorten_uri(uri: str) -> str:
    for uri_prefix, prefix in PREFIXES.items():
        if uri.startswith(uri_prefix):
            return f"{prefix}:{uri[len(uri_prefix):]}"
    return uri
    

def pprint_sparql_results(all_results: JsonType):
    # print(f"all results:\n{json.dumps(all_results, indent=2)}")

    def value_2_str(value: JsonType):
        if value["type"] == "uri":
            return shorten_uri(value["value"])
        else:
            return value["value"]

    try:
        head = all_results["head"]
        vars = head["vars"]
        print(" \t".join(vars))
        print("-"*30)
        results = all_results["results"]
        for binding in results["bindings"]:
            print(" \t".join(value_2_str(binding[var]) for var in vars))
    except Exception as ex:
        print(f"Caught: {ex}")

def get_sagemaker_region() -> str:
    # SageMaker stores instance metadata at this path
    metadata_path = "/opt/ml/metadata/resource-metadata.json"
    try:
        metadata_str = Path(metadata_path).read_text()
        metadata = json.loads(metadata_str)
        resource_arn = metadata["ResourceArn"]
        return resource_arn.split(":")[3]
    except FileNotFoundError:
        # Fallback: Use boto3 default session
        return boto3.session.Session().region_name
