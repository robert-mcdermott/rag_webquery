import argparse
import requests
import os
import sys
from langchain_community.llms import Ollama
from langchain_community.document_loaders import WebBaseLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import GPT4AllEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.chains import RetrievalQA
from langchain_core._api.deprecation import suppress_langchain_deprecation_warning

def main():
    """
    Initialize Ollama with the specified model and base_url,
    load data from the given website, splits the text for efficient processing,
    creates a vector store from the document splits, and finally perform a
    retrieval-based question answering using the specified question.
    """
    parser = argparse.ArgumentParser(description="Query a webpage with a local LLM")
    parser.add_argument("website", help="The website URL to retrieve data from")
    parser.add_argument("question", help="The question to ask about the website's content")
    parser.add_argument("--model", default="zephyr:latest", help="The model to use (default: zephyr:latest)")
    parser.add_argument("--base_url", default="http://localhost:11434", help="The base URL for the Ollama (default: http://localhost:11434)")
    parser.add_argument("--chunk_size", type=int, default=200, help="The document token chunk size (default: 200)")
    parser.add_argument("--chunk_overlap", type=int, default=50, help="The amount of chunk overlap (default: 50)")
    parser.add_argument("--top_matches", type=int, default=4, help="The number the of top matching document chunks to retrieve (default: 4)")
    parser.add_argument("--system", default="You are a helpful assistant.", help="The system message provided to the LLM")
    parser.add_argument("--temp", type=float, default=0.0, help="The model temperature setting (default: 0.0)")
    args = parser.parse_args()

    check_server_availability(args.base_url)

    ollama = Ollama(
                base_url=args.base_url,
                model=args.model,
                system=args.system,
                temperature=args.temp,
                num_ctx=2048
    )

    loader = WebBaseLoader(args.website)
    data = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=args.chunk_size, chunk_overlap=args.chunk_overlap)
    all_splits = text_splitter.split_documents(data)

    # Suppress printing of emmbedding model loading message: still doesn't work!
    with SuppressStdout():
        vectorstore = Chroma.from_documents(documents=all_splits, embedding=GPT4AllEmbeddings())

    with suppress_langchain_deprecation_warning():
        qachain = RetrievalQA.from_chain_type(ollama, retriever=vectorstore.as_retriever(search_kwargs={"k": args.top_matches}))
        res = (qachain.invoke({"query": args.question}))

    output(res)

def output(res):
    print("\n### Answer:")
    print(res['result'].strip())

def check_server_availability(base_url):
    """
    Check if the Ollama server is running at the specified base URL.
    """
    try:
        response = requests.get(base_url)
        if response.status_code == 200:
            sys.stderr.write(f"Successfully connected to the Ollama server at {base_url}.\n")
            sys.stderr.flush()
        else:
            sys.stderr.write(f"Failed to connect to the Ollama server at {base_url}. Exiting.\n")
            sys.stderr.flush()
            sys.exit(1)

    except requests.ConnectionError:
        sys.stderr.write(f"Could not connect to the Ollama server at {base_url}. Exiting.\n")
        sys,stderr.flush()
        sys.exit(1)

class SuppressStdout:
    def __enter__(self):
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        sys.stdout = open(os.devnull, 'w')
        sys.stderr = open(os.devnull, 'w')

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout
        sys.stderr = self._original_stderr

if __name__ == "__main__":
    main()
