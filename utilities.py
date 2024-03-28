"""
This module contains code that is shared amongst the Jupyter notebooks.
"""

from typing import Callable
import os
import json
from pathlib import Path

import requests
from botocore.exceptions import ClientError
from botocore.awsrequest import AWSRequest
from botocore.auth import SigV4Auth


def get_neptune_env(var: str) -> str:
    """
    Return the value of a Neptune environment variable.
    """
    return os.popen(f"source ~/.bashrc ; echo ${var}").read().split("\n")[0]


def run_bedrock(prompt: str,
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


PREFIXES = (Path.cwd() / "resources" / "prefixes.txt").read_text()


def run_generated_query(query_sans_prefixes, sagemaker_session):
    query = f"""
{PREFIXES}

{query_sans_prefixes}
    """
    print(f"SPARQL query:\n{query}")    
    return execute_sparql(query, sagemaker_session)


def generate_and_run(question: str,
                     sparql_generator: Callable[[str], str],
                     sagemaker_session):
    return run_generated_query(sparql_generator(question),
                               sagemaker_session)


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
        if 'results' in json_resp:
            return json_resp['results']['bindings']
        else:
            return json_resp
    except Exception as e:
        print("Exception: {}".format(type(e).__name__))
        print("Exception message: {}".format(e))
        print(f"Here is the query:\n{query}\n")
        print(f"CRUD type is *{crud_type}*")
        print(f"Here is the result:\n{response.text}\n")
        raise e