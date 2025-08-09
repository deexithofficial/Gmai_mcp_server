import os.path
import base64
from email.message import EmailMessage

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Only this scope is needed for drafts
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

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

def gmail_create_draft():
    try:
        service = get_service()

        message = EmailMessage()
        message.set_content("This is an automated draft email.")
        message["To"] = "dikki6067@gmail.com"
        message["From"] = "me"
        message["Subject"] = "Automated Draft"

        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

        create_message = {"message": {"raw": encoded_message}}

        draft = service.users().drafts().create(userId="me", body=create_message).execute()

        print(f"✅ Draft created successfully!\nDraft ID: {draft['id']}")
    except HttpError as error:
        print(f"❌ An error occurred: {error}")

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


def extract_unread_emails():
    service = get_service()
    unread_emails = []
    try:
        result = service.users().messages().list(userId="me", labelIds=["UNREAD"]).execute()
        messages = result.get("messages", [])
        # print(result)
        for message in messages:
            unread_emails.append(message)
    except HttpError as error:
        print(f"❌ An error occurred: {error}")
    return unread_emails


if __name__ == "__main__":
    print("Extracting unread emails...")
    unread_emails = get_unread_emails_after_date("me", "2025/08/08")
    print(unread_emails)
