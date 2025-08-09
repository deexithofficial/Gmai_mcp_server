#Model Initialising
from langchain.embeddings import HuggingFaceEmbeddings
import faiss
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores import FAISS
from uuid import uuid4
from langchain_core.documents import Document
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")
from typing import List
#Prompts_Template
import json

# Load JSON from file
with open('templates/prompts.json', 'r', encoding='utf-8') as file:
    data = json.load(file)

# Access prompts
prompts = data.get("prompts", [])


index = faiss.IndexFlatL2(len(embeddings.embed_query("hello world")))

vector_store = FAISS(
    embedding_function=embeddings,
    index=index,
    docstore=InMemoryDocstore(),
    index_to_docstore_id={},
)

def build_docs(prompts:list):
    documents = []
    for prompt in prompts:
        document = Document(page_content=prompt["prompt"] , metadata={
            "category" : prompt["category"],
            "template" : prompt["template type"],
            "purpose of mail" : prompt["purpose of mail"],
            "prompt": prompt["prompt"]
        })

        documents.append(document)
    return documents

documents = build_docs(prompts)
uuids = [str(uuid4()) for _ in range(len(documents))]
vector_store.add_documents(documents=documents, ids=uuids)


    




if __name__=="__main__":
    # for prompt in prompts:
    #     print(f"Category:{prompt["category"]}\n")
    #     print(f"Template:{prompt["template type"]}\n")
    #     print(f"purpose of mail:{prompt["purpose of mail"]}\n")
    #     print(f"prompt:{prompt["prompt"]}\n")
    #     print("="*50)
    results = vector_store.similarity_search(
    "Email to request leave for 2 days",
    k=2
    )
    for res in results:
        print(f"* {res.page_content} [{res.metadata}]")