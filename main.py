import os
import requests
import json
import base64
from datetime import datetime, timedelta
from langchain.chains.summarize import load_summarize_chain
from langchain.chat_models import ChatOpenAI
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.document_loaders import JSONLoader
from langchain.prompts import PromptTemplate

def metadata_func(record: dict, metadata: dict) -> dict:
    metadata["issue_id"] = record.get("issue_id")
    metadata["description"] = record.get("description")
    return metadata
 
from dotenv import load_dotenv
load_dotenv()

# Set the JIRA API endpoint and user credentials
url = "https://onedegree.atlassian.net/rest/api/2/search"
JIRA_API_TOKEN = os.environ.get('JIRA_API_TOKEN')
JIRA_USERNAME = os.environ.get('JIRA_USERNAME')
OPENAI_MODEL_NAME = os.environ.get("OPENAI_MODEL_NAME", "gpt-3.5-turbo")
ISSUE_DAYS_AGO = os.environ.get('ISSUE_DAYS_AGO', '90')
ISSUE_DONE_STATUS_NAME = os.environ.get('ISSUE_DONE_STATUS_NAME', 'Done')

# Set the JQL query to retrieve issues assigned to the current user
three_months_ago = datetime.today() - timedelta(days=int(ISSUE_DAYS_AGO))
jql = f"assignee = currentUser() AND updated >= '{three_months_ago.strftime('%Y-%m-%d')}' AND status = '{ISSUE_DONE_STATUS_NAME}'"

# Set the headers for the API request
jwt_token = f"{JIRA_USERNAME}:{JIRA_API_TOKEN}"
jwt_token = jwt_token.encode('utf-8')
jwt_token = base64.b64encode(jwt_token).decode('utf-8')
headers = {
    "Content-Type": "application/json",
    "Authorization": "Basic " + jwt_token
}

# Set the data for the API request
data = {
    "jql": jql,
    "maxResults": 1000,
    "fields": ["key", "summary", "description"]
}

# Make the API request and retrieve the response
response = requests.post(url, headers=headers, data=json.dumps(data))

# Check if the response was successful
if response.status_code == 200:
    # Parse the response JSON and extract the issues
    response_json = json.loads(response.text)
    issues = response_json["issues"]

    jira_issues = []
    for issue in issues:
        jira_id=issue["key"]
        jira_summary=issue["fields"]["summary"]
        jira_description=issue["fields"]["description"]
        jira_issues.append({"summary": f"{jira_id} {jira_summary}", "description": jira_description})
    with open('jira_issues.json', 'w') as f:
        f.truncate(0)
        json.dump(jira_issues, f)

    loader = JSONLoader(
        file_path='./jira_issues.json',
        jq_schema='.[]',
        content_key='summary',
        metadata_func=metadata_func
    )

    docs = loader.load()

    prompt_template = """Please generate an OKR format document with objectives based on the following task list:
    {text}"""
    PROMPT = PromptTemplate(template=prompt_template, input_variables=["text"])
    llm = ChatOpenAI(model_name=OPENAI_MODEL_NAME, temperature=0, streaming=True, callbacks=[StreamingStdOutCallbackHandler()])
    chain = load_summarize_chain(llm, chain_type="stuff", prompt=PROMPT)
    output = chain.run(docs)     
    with open('okr_draft.md', 'w') as f:
        f.write(output)
else:
    print(f"Error retrieving issues from JIRA API. {response.status_code} {response.text}")