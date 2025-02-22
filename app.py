import os
from PyPDF2 import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
import streamlit as st
import google.generativeai as genai
from langchain.vectorstores import FAISS
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains.question_answering import load_qa_chain
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv
import io
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'
from PIL import Image


load_dotenv()
os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))



def get_pdf_text(pdf_docs):
    text = ""
    for pdf in pdf_docs:
        pdf_reader = PdfReader(pdf)
        for page in pdf_reader.pages:
            text += page.extract_text()
    return text

# split text into chunks


def get_text_chunks(text):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=10000, chunk_overlap=1000)
    chunks = splitter.split_text(text)
    return chunks  # list of strings

# get embeddings for each chunk


def get_vector_store(chunks):
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001")  # type: ignore
    vector_store = FAISS.from_texts(chunks, embedding=embeddings)
    vector_store.save_local("faiss_index")


def get_conversational_chain():
    prompt_template = """
    Answer the question as detailed as possible from the provided context, make sure to provide all the details, if the answer is not in
    provided context just say, "answer is not available in the context", don't provide the wrong answer\n\n
    Context:\n {context}?\n
    Question: \n{question}\n

    Answer:
    """

    model = ChatGoogleGenerativeAI(
        model="gemini-pro",
        client=genai,
        temperature=0.3,
    )
    prompt = PromptTemplate(
        template=prompt_template,
        input_variables=["context", "question"]
    )
    chain = load_qa_chain(llm=model, chain_type="stuff", prompt=prompt)
    return chain


def clear_chat_history():
    st.session_state.messages = [
        {"role": "assistant", "content": "upload some Docs and ask me a question"}]


def user_input(user_question):
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001")  # type: ignore

    new_db = FAISS.load_local("faiss_index", embeddings, allow_dangerous_deserialization=True) 
    docs = new_db.similarity_search(user_question)

    chain = get_conversational_chain()

    response = chain(
        {"input_documents": docs, "question": user_question}, return_only_outputs=True, )

    print(response)
    return response


def main():
    st.set_page_config(
        page_title="Gen AI Chatbot",
        page_icon="🎉"
    )

    # Sidebar
    with st.sidebar:
        st.title("Menu:")
        uploaded_files = st.file_uploader("Upload PDF or PNG files", type=["pdf","png"], accept_multiple_files=True)

        if 'documents_text' not in st.session_state:
            st.session_state['documents_text'] = []

        if st.button("Submit & Process Files"):
            if uploaded_files:
                for uploaded_file in uploaded_files:
                    file_type = uploaded_file.type
                    if file_type == "application/pdf":
                        pdf_io = io.BytesIO(uploaded_file.read())
                        pdf_io.seek(0)
                        reader = PdfReader(pdf_io)
                        text_content = ""
                        for page in reader.pages:
                            text_content += page.extract_text()
                        st.session_state['documents_text'].append(text_content)
                        text_chunks = get_text_chunks(text_content)
                        get_vector_store(text_chunks)
                        st.success("Done")
                    elif file_type in ["image/png","image/jpeg"]:
                        try:
                            img_bytes = uploaded_file.read()
                            img = Image.open(io.BytesIO(img_bytes))
                            extracted_text = pytesseract.image_to_string(img)
                            st.session_state['documents_text'].append(extracted_text)
                            text_chunks = get_text_chunks(extracted_text)
                            get_vector_store(text_chunks)
                            st.success("Done")
                        except pytesseract.TesseractNotFoundError:
                            st.error("Tesseract not installed or not in PATH.")
                    else:
                        st.error("Unsupported file format.")
                st.write("All files processed successfully.")
            else:
                st.error("No files uploaded.")
        
        if st.button("Start New Chat"):
            st.session_state['documents_text'] = []
            st.write("Chat cleared. Previous context removed.")


    # Main content
    st.title("GenAI-Chatbot")
    st.write("Welcome to the chat!")
    st.sidebar.button('Clear Chat History', on_click=clear_chat_history)

    # input

    if "messages" not in st.session_state.keys():
        st.session_state.messages = [
            {"role": "assistant", "content": "upload some Docs and ask me a question"}]

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    if prompt := st.chat_input():
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

    # bot response
    if st.session_state.messages[-1]["role"] != "assistant":
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = user_input(prompt)
                placeholder = st.empty()
                full_response = ''
                for item in response['output_text']:
                    full_response += item
                    placeholder.markdown(full_response)
                placeholder.markdown(full_response)
        if response is not None:
            message = {"role": "assistant", "content": full_response}
            st.session_state.messages.append(message)


if __name__ == "__main__":
    main()
