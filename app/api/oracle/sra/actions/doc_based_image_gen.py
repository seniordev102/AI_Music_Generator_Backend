import asyncio
from operator import itemgetter
from typing import List

from langchain.schema.messages import HumanMessage
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores.faiss import FAISS
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.api.oracle.sra.utils.common import (
    SRA_IMAGE_GENERATION_END,
    SRA_IMAGE_GENERATION_ERROR,
    SRA_IMAGE_GENERATION_START,
    emit_websocket_event,
    get_chat_message_history_by_session_id,
    get_most_recent_sra_document,
    save_generated_image_to_db,
)
from app.api.oracle.sra.utils.generate_art import generate_art
from app.logger.logger import logger


async def generate_sra_image_based_on_documents(
    session_id: str,
    message_id: str,
    user_prompt: str,
    aspect_ratio: str,
    art_style: str,
    art_style_description: str,
    sid: str,
):

    await emit_websocket_event(
        event_name=SRA_IMAGE_GENERATION_START,
        data={
            "session_id": session_id,
            "message_id": message_id,
            "payload": True,
        },
        sid=sid,
    )
    # Allow the event loop to process the emit
    await asyncio.sleep(0)

    # fetch the most recent chat by session and find the image url
    recent_uploaded_document = await get_most_recent_sra_document(session_id=session_id)

    chain = None
    llm = ChatOpenAI(model="gpt-4o", temperature=0.1)

    system_prompt = """
            Create a prompt to generate an image based on the user's document
            Please note that you only need to generate the prompt in text format. you won't be generating the image
            """

    if recent_uploaded_document is None:
        await emit_websocket_event(
            event_name=SRA_IMAGE_GENERATION_ERROR,
            data={
                "error_code": "general_error",
                "session_id": session_id,
                "message_id": message_id,
                "payload": "Sorry, we couldn't find any reference document to generate a custom variant",
            },
            sid=sid,
        )

    else:
        if recent_uploaded_document.file_content:
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=2000, chunk_overlap=100
            )
            docs: List[Document] = text_splitter.create_documents(
                [recent_uploaded_document.file_content]
            )

            embeddings = OpenAIEmbeddings()
            vector_store = FAISS.from_documents(docs, embeddings)
            retriever = vector_store.as_retriever(search_kwargs={"k": 5})

            def format_docs(docs: List[Document]):
                return "\n\n".join(doc.page_content for doc in docs)

            context = RunnablePassthrough.assign(
                context=itemgetter("input") | retriever | format_docs
            )

            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", system_prompt + "\n\nContext: {context}"),
                    MessagesPlaceholder(variable_name="chat_history"),
                    ("human", "{input}"),
                ]
            )

            chain = context | prompt | llm

        elif recent_uploaded_document.file_url:
            logger.info("User document url is available probably an image")
            prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        system_prompt,
                    ),
                    MessagesPlaceholder(variable_name="chat_history"),
                    ("human", "{input}"),
                    HumanMessage(
                        content=[
                            {"type": "text", "text": user_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": recent_uploaded_document.file_url,
                                    "details": "high",
                                },
                            },
                        ]
                    ),
                ]
            )

            chain = prompt | llm

        history = await get_chat_message_history_by_session_id(session_id=session_id)
        chain_with_message_history = RunnableWithMessageHistory(
            chain,
            lambda session_id: history,
            input_messages_key="input",
            history_messages_key="chat_history",
        )

        response = chain_with_message_history.invoke(
            {"input": user_prompt}, {"configurable": {"session_id": session_id}}
        )

        image_prompt = response.content

        # create the image
        image_url = await generate_art(
            user_prompt=image_prompt,
            aspect_ratio=aspect_ratio,
            art_style=art_style,
            art_style_description=art_style_description,
        )

        # save the generated image to the database
        await save_generated_image_to_db(
            session_id=session_id, message_id=message_id, image_url_s3=image_url
        )

        # send end event
        await emit_websocket_event(
            event_name=SRA_IMAGE_GENERATION_END,
            data={
                "session_id": session_id,
                "message_id": message_id,
                "payload": image_url,
            },
            sid=sid,
        )

        return image_url
