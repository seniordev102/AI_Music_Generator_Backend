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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.oracle.sra.utils.common import (
    SRA_CHAT_END,
    SRA_CHAT_ERROR,
    SRA_CHAT_RESPONSE,
    SRA_CHAT_START,
    emit_websocket_event,
    get_chat_message_history_by_session_id,
    get_most_recent_sra_document,
    load_prompt_from_file_path,
    save_sra_chat_response_to_db,
)
from app.database import db_session
from app.logger.logger import logger
from app.models import SRAUserPrompt, User


async def _load_user_custom_prompt(user_email: str) -> str:
    async for session in db_session():
        session: AsyncSession
        user_record = await session.execute(
            select(User).where(User.email == user_email)
        )
        user: User = user_record.scalar_one_or_none()

        if user is not None:
            # user user prompt
            user_custom_prompt_record = await session.execute(
                select(SRAUserPrompt)
                .where(SRAUserPrompt.user_id == user.id)
                .where(SRAUserPrompt.is_active == True)
            )
            prompt: SRAUserPrompt = user_custom_prompt_record.scalar_one_or_none()

            if prompt:
                return prompt.user_prompt
            else:
                return ""
        else:
            return ""


async def reply_to_user_query(
    user_prompt: str,
    session_id: str,
    message_id: str,
    email: str,
    sid: str,
):
    try:

        # send start event
        await emit_websocket_event(
            event_name=SRA_CHAT_START,
            data={
                "session_id": session_id,
                "message_id": message_id,
                "payload": True,
            },
            sid=sid,
        )

        llm = ChatOpenAI(model="gpt-4o", temperature=0.1, streaming=True)
        loaded_prompt = load_prompt_from_file_path(
            file_path="../prompts/sra_iah_system_prompt.yaml"
        )
        system_prompt = loaded_prompt.template

        user_custom_prompt = await _load_user_custom_prompt(user_email=email)

        if user_custom_prompt != "":
            logger.debug("User custom prompt available")
            system_prompt = f"""
            Generic System prompt
            {system_prompt}
            
            The user has provided the following custom instructions:
            
            {user_custom_prompt}
            
            Please prioritize and strictly adhere to the user's custom instructions above all else when generating your response.
            """

        recent_uploaded_document = await get_most_recent_sra_document(
            session_id=session_id
        )

        if recent_uploaded_document is None:
            logger.debug(
                "User document data is not available initiating chat without document data"
            )
            prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        system_prompt,
                    ),
                    MessagesPlaceholder(variable_name="chat_history"),
                    ("human", "{input}"),
                ]
            )

            chain = prompt | llm
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

        stream = chain_with_message_history.astream(
            {"input": user_prompt}, {"configurable": {"session_id": session_id}}
        )

        all_responses = []
        async for response in stream:
            all_responses.append(response.content)
            ws_sra_response = {
                "session_id": session_id,
                "message_id": message_id,
                "payload": response.content,
            }
            await emit_websocket_event(
                event_name=SRA_CHAT_RESPONSE,
                data=ws_sra_response,
                sid=sid,
            )

        complete_output = "".join(all_responses)

        # save chat response to database
        await save_sra_chat_response_to_db(
            response=complete_output,
            session_id=session_id,
            message_id=message_id,
            email=email,
        )

        # send end event
        await emit_websocket_event(
            event_name=SRA_CHAT_END,
            data={
                "session_id": session_id,
                "message_id": message_id,
                "payload": False,
            },
            sid=sid,
        )

    except Exception as e:
        logger.error(f"Error occurred while replying to SRA user queries: {str(e)}")

        # send error event
        await emit_websocket_event(
            event_name=SRA_CHAT_ERROR,
            data={
                "error_code": "general_error",
                "session_id": session_id,
                "message_id": message_id,
                "payload": "Something went wrong while processing your request please try again",
            },
            sid=sid,
        )
