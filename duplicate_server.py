from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP

import os
import base64
from email.message import EmailMessage

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from typing import List, TypedDict, Any, Optional, Tuple

from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode
from uuid import uuid4
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.embeddings import Embeddings
import re
from langchain_openai import OpenAIEmbeddings

email_templates = [
    {
        "template": "Write a polite email requesting {{request_topic}} from {{recipient}}.",
        "category": "request",
        "keywords": ["request", "ask", "need", "require", "polite"],
        "description": "General request email template"
    },
    {
        "template": "Draft a follow-up email regarding {{previous_conversation}} to {{recipient}}.",
        "category": "follow-up",
        "keywords": ["follow-up", "follow up", "check in", "reminder", "previous"],
        "description": "Follow-up on previous communication"
    },
    {
        "template": "Write a formal complaint email about {{issue}} that happened on {{date}}.",
        "category": "complaint",
        "keywords": ["complaint", "issue", "problem", "dissatisfied", "formal"],
        "description": "Formal complaint or issue reporting"
    },
    {
        "template": "Write a thank-you email to {{recipient}} for {{reason}}.",
        "category": "gratitude",
        "keywords": ["thank", "gratitude", "appreciate", "grateful", "thanks"],
        "description": "Express gratitude and appreciation"
    },
    {
        "template": "Write an application email for {{position}} at {{organization}}.",
        "category": "application",
        "keywords": ["application", "apply", "job", "position", "role", "career"],
        "description": "Job or position application"
    },
    {
        "template": "Write a professional apology email for {{mistake}} to {{recipient}}.",
        "category": "apology",
        "keywords": ["apology", "sorry", "mistake", "error", "regret"],
        "description": "Professional apology for mistakes"
    },
    {
        "template": "Write a polite email requesting an extension of the deadline for {{task}}.",
        "category": "extension",
        "keywords": ["extension", "deadline", "delay", "more time", "postpone"],
        "description": "Request deadline extension"
    },
    {
        "template": "Draft an email asking for a recommendation letter from {{professor}}.",
        "category": "recommendation",
        "keywords": ["recommendation", "reference", "letter", "endorse", "vouch"],
        "description": "Request for recommendation letter"
    },
    {
        "template": "Write a meeting request email to {{recipient}} about {{meeting_topic}}.",
        "category": "meeting",
        "keywords": ["meeting", "schedule", "appointment", "discuss", "call"],
        "description": "Schedule meetings or appointments"
    },
    {
        "template": "Draft a project update email to {{stakeholders}} regarding {{project_name}}.",
        "category": "update",
        "keywords": ["update", "progress", "status", "project", "report"],
        "description": "Project status and progress updates"
    },
    {
        "template": "Write a welcome email to new {{team_member}} joining {{department}}.",
        "category": "welcome",
        "keywords": ["welcome", "new", "joining", "onboard", "introduction"],
        "description": "Welcome new team members"
    },
    {
        "template": "Create a reminder email about {{event}} scheduled for {{date}}.",
        "category": "reminder",
        "keywords": ["reminder", "upcoming", "scheduled", "don't forget", "alert"],
        "description": "Event or deadline reminders"
    },
    {
        "template": "Write a resignation email to {{manager}} with {{notice_period}} notice.",
        "category": "resignation",
        "keywords": ["resignation", "quit", "leave", "departure", "notice"],
        "description": "Professional resignation notice"
    },
    {
        "template": "Draft a sales pitch email for {{product}} to {{prospect}}.",
        "category": "sales",
        "keywords": ["sales", "pitch", "offer", "product", "proposal", "sell"],
        "description": "Sales and marketing outreach"
    },
    {
        "template": "Write a customer service response to {{customer_complaint}}.",
        "category": "customer_service",
        "keywords": ["customer service", "support", "help", "resolve", "assist"],
        "description": "Customer service and support responses"
    },
    {
        "template": "Write a networking email to {{contact}} about {{networking_purpose}}.",
        "category": "networking",
        "keywords": ["networking", "connect", "professional", "relationship", "contact"],
        "description": "Professional networking and connections"
    },
    {
        "template": "Draft an invoice email to {{client}} for {{service_description}}.",
        "category": "billing",
        "keywords": ["invoice", "bill", "payment", "charge", "due"],
        "description": "Billing and payment requests"
    },
    {
        "template": "Write a congratulations email to {{recipient}} for {{achievement}}.",
        "category": "congratulations",
        "keywords": ["congratulations", "achievement", "success", "celebrate", "proud"],
        "description": "Celebrate achievements and milestones"
    }
]

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

mcp = FastMCP("gmail")
import os
from dotenv import load_dotenv

load_dotenv()  # ✅ Correct function to load .env file

# Optionally, set it in os.environ again (not required if using os.getenv)
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

class EmailTemplateVectorSearch:
    """Vector search system for email templates"""
    
    def __init__(self, embedding_model: Optional[Embeddings] = None):
        # Initialize embeddings model
        if embedding_model is None:
            self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        else:
            self.embeddings = embedding_model
        
        # Create documents for vector search
        self.documents = self._create_documents()
        
        # Initialize vector store
        self.vector_store = FAISS.from_documents(self.documents, self.embeddings)
        
    def _create_documents(self) -> List[Document]:
        """Create Document objects for vector search"""
        documents = []
        
        for i, template_data in enumerate(email_templates):
            # Combine template, keywords, and description for better search
            search_content = f"""
            Template: {template_data['template']}
            Category: {template_data['category']}
            Keywords: {', '.join(template_data['keywords'])}
            Description: {template_data['description']}
            """
            
            doc = Document(
                page_content=search_content.strip(),
                metadata={
                    "template_id": i,
                    "template": template_data['template'],
                    "category": template_data['category'],
                    "keywords": template_data['keywords'],
                    "description": template_data['description']
                }
            )
            documents.append(doc)
            
        return documents
    
    def search_templates(self, query: str, k: int = 3) -> List[Tuple[Document, float]]:
        """Search for relevant email templates using vector similarity"""
        results = self.vector_store.similarity_search_with_score(query, k=k)
        return results
    
    def get_best_template(self, query: str) -> Tuple[int, str, float]:
        """Get the best matching template for a query"""
        results = self.search_templates(query, k=1)
        if results:
            doc, score = results[0]
            template_id = doc.metadata['template_id']
            template = doc.metadata['template']
            return template_id, template, score
        return -1, "", 1.0

def extract_variables(template: str) -> List[str]:
    """Extract variable names from a template"""
    variables = re.findall(r'\{\{(\w+)\}\}', template)
    return list(set(variables))

def get_service():
    """Get Gmail service with authentication"""
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

# Initialize the vector search system
email_vector_search = EmailTemplateVectorSearch()

class EmailTemplateResult(TypedDict):
    """Type definition for email template search results"""
    template: str
    category: str
    keywords: List[str]
    description: str
    similarity_score: float
    template_id: int
    variables: List[str]

@mcp.tool()
def vector_search_email(query: str, k: int = 3) -> List[EmailTemplateResult]:
    """
    Vector search for email templates based on natural language query.
    
    Args:
        query: Natural language description of the email type needed
        k: Number of results to return (default: 3)
    
    Returns:
        List of matching email templates with metadata and similarity scores
    """
    try:
        results = email_vector_search.search_templates(query, k=k)
        
        template_results = []
        for doc, score in results:
            template_result: EmailTemplateResult = {
                "template": doc.metadata['template'],
                "category": doc.metadata['category'],
                "keywords": doc.metadata['keywords'],
                "description": doc.metadata['description'],
                "similarity_score": 1 - score,  # Convert distance to similarity
                "template_id": doc.metadata['template_id'],
                "variables": extract_variables(doc.metadata['template'])
            }
            template_results.append(template_result)
        
        return template_results
    
    except Exception as e:
        # Return empty list with error information
        return [{
            "template": f"Error: {str(e)}",
            "category": "error",
            "keywords": [],
            "description": "An error occurred during search",
            "similarity_score": 0.0,
            "template_id": -1,
            "variables": []
        }]

@mcp.tool()
def generate_email_content(query: str, variables: dict = None) -> str:
    """
    Generate email content using the best matching template and LLM.
    
    Args:
        query: Natural language description of the email needed
        variables: Dictionary of variables to fill in the template
    
    Returns:
        Generated email content
    """
    if variables is None:
        variables = {}
    
    try:
        # Get the best matching template
        template_id, template, score = email_vector_search.get_best_template(query)
        
        if template_id == -1:
            return "No suitable template found for your query."
        
        # Get template metadata
        template_data = email_templates[template_id]
        required_vars = extract_variables(template)
        
        # Create the prompt for LLM
        prompt = f"""
        Based on the following email template and user requirements, generate a professional email:
        
        Template Category: {template_data['category']}
        Template Description: {template_data['description']}
        User Query: {query}
        
        Email Template: {template}
        
        Required Variables:
        {chr(10).join([f"- {var}: {variables.get(var, '[PLEASE PROVIDE]')}" for var in required_vars])}
        
        Please generate a complete, professional email that follows the template structure but with natural, engaging content. 
        Make sure to:
        1. Use appropriate tone for the email type
        2. Include proper email structure (greeting, body, closing)
        3. Fill in any missing variables with reasonable placeholders
        4. Make the content specific and actionable
        """
        
        return prompt
    
    except Exception as e:
        return f"Error generating email: {str(e)}"

@mcp.tool()
def gmail_create_draft(to: str, subject: str, body: str) -> str:
    """
    Create a Gmail draft with the specified content.
    
    Args:
        to: Recipient email address
        subject: Email subject line
        body: Email body content
    
    Returns:
        Success message with draft ID or error message
    """
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

        return f"✅ Draft created successfully! Draft ID: {draft['id']}"
    
    except HttpError as error:
        return f"❌ Gmail API error: {error}"
    except Exception as error:
        return f"❌ An error occurred: {error}"

@mcp.tool()
def create_email_draft_from_query(query: str, to: str, variables: dict = None) -> str:
    """
    Complete workflow: Search template, generate content, and create Gmail draft.
    
    Args:
        query: Natural language description of email needed
        to: Recipient email address
        variables: Dictionary of template variables
    
    Returns:
        Status message with draft creation result
    """
    if variables is None:
        variables = {}
    
    try:
        # Step 1: Find best template
        template_id, template, score = email_vector_search.get_best_template(query)
        
        if template_id == -1:
            return "❌ No suitable template found for your query."
        
        # Step 2: Generate email prompt for LLM
        email_prompt = generate_email_content(query, variables)
        
        # Step 3: Extract subject from query or use default
        template_data = email_templates[template_id]
        default_subject = f"{template_data['category'].title()} - {query[:50]}..."
        subject = variables.get('subject', default_subject)
        
        # Step 4: Create draft (using the prompt as body for now)
        # In a real implementation, you'd send this prompt to an LLM to generate the actual email
        draft_body = f"""
[AI-Generated Email Draft]

Template Used: {template_data['category']} (Similarity: {1-score:.3f})
Query: {query}

{email_prompt}

---
This draft was created using AI email templates. Please review and edit before sending.
        """
        
        result = gmail_create_draft(to, subject, draft_body)
        
        return f"""
📧 Email Draft Workflow Complete!

Template Match: {template_data['category']} (Similarity: {1-score:.3f})
Subject: {subject}
Recipient: {to}
Required Variables: {extract_variables(template)}

{result}
        """
    
    except Exception as e:
        return f"❌ Error in draft creation workflow: {str(e)}"

@mcp.tool()
def list_template_categories() -> List[str]:
    """
    Get all available email template categories.
    
    Returns:
        List of unique email categories
    """
    try:
        categories = list(set(template['category'] for template in email_templates))
        return sorted(categories)
    except Exception as e:
        return [f"Error: {str(e)}"]

@mcp.tool()
def get_template_by_category(category: str) -> List[EmailTemplateResult]:
    """
    Get all templates for a specific category.
    
    Args:
        category: Email category to filter by
    
    Returns:
        List of templates in the specified category
    """
    try:
        category_templates = []
        for i, template_data in enumerate(email_templates):
            if template_data['category'].lower() == category.lower():
                template_result: EmailTemplateResult = {
                    "template": template_data['template'],
                    "category": template_data['category'],
                    "keywords": template_data['keywords'],
                    "description": template_data['description'],
                    "similarity_score": 1.0,
                    "template_id": i,
                    "variables": extract_variables(template_data['template'])
                }
                category_templates.append(template_result)
        
        return category_templates
    
    except Exception as e:
        return [{
            "template": f"Error: {str(e)}",
            "category": "error",
            "keywords": [],
            "description": "An error occurred during category search",
            "similarity_score": 0.0,
            "template_id": -1,
            "variables": []
        }]

@mcp.tool()
def gmail_get_status() -> str:
    """
    Check Gmail authentication and connection status.
    
    Returns:
        Status message indicating connection state
    """
    try:
        service = get_service()
        profile = service.users().getProfile(userId='me').execute()
        email = profile['emailAddress']
        return f"✅ Gmail Status: Connected and ready! Authenticated as: {email}"
    except Exception as e:
        return f"❌ Gmail Status: Error - {str(e)}"

if __name__ == "__main__":
    # Test the functionality before running server
    try:
        # Test vector search
        print("Testing vector search...")
        results = vector_search_email("I need to thank my colleague", k=2)
        print(f"Found {len(results)} templates")
        
        # Test Gmail status
        print("Testing Gmail connection...")
        status = gmail_get_status()
        print(status)
        
    except Exception as e:
        print(f"Initialization error: {e}")
    
    # Initialize and run the server
    # mcp.run(transport="stdio")