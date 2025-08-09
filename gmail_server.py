from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP
# from mcp.types import InputField, ToolCallSchema

import os
import base64
from email.message import EmailMessage

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from vector_db import vector_store



SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

mcp = FastMCP("gmail")


def get_service():
    creds = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    service = build("gmail", "v1", credentials=creds)
    return service

@mcp.tool()
def prompt_templates(query: str):
    """
    Returns example and most relevant email prompt templates using vector search.

    Args:
        query (str): A natural language query from LLM or user, e.g., "email for requesting a leave"

    Returns:
        List[dict]: A list of top matching email prompt templates with their metadata
    """
    results = vector_store.similarity_search(query, k=3)

    return [
        {
            "prompt": doc.page_content,
            "category": doc.metadata.get("category", ""),
            "template_type": doc.metadata.get("template type", ""),
            "purpose": doc.metadata.get("purpose of mail", "")
        }
        for doc in results
    ]



# @mcp.tool()
# def gmail_draft_inputs(prompt_templates : str):
#     """
#     Collects required inputs from user based on the prompt_template and then creates the email draft.
#     """
#     # Example placeholders detected from template: {to}, {subject}, {name}, etc.
#     # You can use regex to dynamically extract them
#     placeholders = {
#         "to": InputField(label="Recipient Email", type="string"),
#         "subject": InputField(label="Email Subject", type="string"),
#         "name": InputField(label="Recipient Name", type="string"),
#         "reason": InputField(label="Reason for Leave", type="string"),
#         "dates": InputField(label="Leave Dates", type="string"),
#     }

#     return ToolCallSchema(
#         name="gmail_create_draft",
#         description="Fill in the placeholder values to finalize the draft.",
#         parameters=placeholders
#     )
@mcp.tool()
def gmail_create_draft(to:str, subject:str, body:str):
    """Fill the email template with dynamic placeholders"""
    try:
        service = get_service()

        message = EmailMessage()
        message.set_content(body)
        message["To"] = to
        message["From"] = "me"
        message["Subject"] = subject

        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

        create_message = {"message": {"raw": encoded_message}}

        draft = service.users().drafts().create(userId="me", body=create_message).execute()

        print(f"✅ Draft created successfully!\nDraft ID: {draft['id']}")
    except HttpError as error:
        print(f"❌ An error occurred: {error}")


@mcp.tool()
def extract_unread_emails():
    service = get_service()
    unread_emails = []
    try:
        result = service.users().messages().list(userId="me", labelIds=["UNREAD"]).execute()
        messages = result.get("messages", [])
        for message in messages:
            unread_emails.append(message)
    except HttpError as error:
        print(f"❌ An error occurred: {error}")
    return unread_emails
    
@mcp.tool()
def get_unread_emails_after_date(user_id, after_date):
    """
    Fetch unread emails after a given date.

    Args:
        service: Authorized Gmail API service instance.
        user_id (str): User's email address or "me".
        after_date (str): Date in "YYYY/MM/DD" format.

    Returns:
        list of dict: Each dict has 'id', 'subject', 'from', 'date', 'body'.
    """
    try:
        service = get_service()
        query = f'is:unread after:{after_date}'
        results = service.users().messages().list(userId=user_id, q=query).execute()
        messages = results.get('messages', [])
        
        unread_mails = []
        for msg in messages:
            msg_id = msg['id']
            mail = service.users().messages().get(userId=user_id, id=msg_id, format='full').execute()

            payload = mail.get('payload', {})
            headers = payload.get('headers', [])
            subject = from_ = date = None
            
            for header in headers:
                name = header.get("name", "").lower()
                if name == "subject":
                    subject = header.get("value")
                elif name == "from":
                    from_ = header.get("value")
                elif name == "date":
                    date = header.get("value")

            # Extract plain text body
            body = ""
            if 'parts' in payload:
                for part in payload['parts']:
                    if part['mimeType'] == 'text/plain':
                        data = part['body'].get('data')
                        if data:
                            body = base64.urlsafe_b64decode(data).decode("utf-8")
                            break
            else:
                data = payload.get('body', {}).get('data')
                if data:
                    body = base64.urlsafe_b64decode(data).decode("utf-8")

            unread_mails.append({
                "id": msg_id,
                "subject": subject,
                "from": from_,
                "date": date,
                "body" : parse_msg(mail)
            })

        return unread_mails

    except HttpError as error:
        print(f"An error occurred: {error}")
        return []

def parse_msg(msg):
    if msg.get("payload").get("body").get("data"):
        return base64.urlsafe_b64decode(msg.get("payload").get("body").get("data").encode("ASCII")).decode("utf-8")
    return msg.get("snippet")    

# @mcp.tool()
# def list_emails(max_results: int = 10, query: str = ""):
#     """List emails from Gmail
    
#     Args:
#         max_results: Maximum number of emails to return (default: 10)
#         query: Gmail search query (e.g., "from:example@gmail.com", "is:unread")
#     """
#     global service
    
#     if not service:
#         return "Error: Gmail not setup. Please run setup_gmail first."
    
#     try:
#         results = service.users().messages().list(
#             userId='me', 
#             maxResults=max_results,
#             q=query
#         ).execute()
        
#         messages = results.get('messages', [])
        
#         if not messages:
#             return "No messages found."
        
#         email_list = []
#         for message in messages:
#             msg = service.users().messages().get(userId='me', id=message['id']).execute()
            
#             # Extract headers
#             headers = msg['payload'].get('headers', [])
#             subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
#             from_email = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
#             date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown Date')
            
#             email_list.append({
#                 'id': message['id'],
#                 'subject': subject,
#                 'from': from_email,
#                 'date': date
#             })
        
#         result = f"Found {len(email_list)} emails:\n\n"
#         for i, email in enumerate(email_list, 1):
#             result += f"{i}. ID: {email['id']}\n"
#             result += f"   From: {email['from']}\n"
#             result += f"   Subject: {email['subject']}\n"
#             result += f"   Date: {email['date']}\n\n"
        
#         return result
        
#     except Exception as e:
#         return f"Error listing emails: {str(e)}"

# @mcp.tool()
# def get_status():
#     """Check Gmail authentication and connection status"""
#     global service, creds
    
#     if not creds:
#         return "Status: Not authenticated. Run setup_gmail first."
    
#     if not service:
#         return "Status: Authenticated but service unavailable."
        
#     try:
#         profile = service.users().getProfile(userId='me').execute()
#         email = profile['emailAddress']
#         return f"Status: Connected and ready! Authenticated as: {email}"
#     except Exception as e:
#         return f"Status: Error checking connection - {str(e)}"
    
if __name__ == "__main__":
    # Initialize and run the server
    # gmail_create_draft(to="dikki6067@gmail.com", subject="Automated Draft", body="This is an automated draft email.")
    mcp.run(transport="stdio")
    # results = prompt_templates("Request of leave for 2 days")
    # print(results)
