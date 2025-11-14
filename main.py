from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI


def build_chain(system_prompt: str = "You are a concise assistant."):
    """Wire together the LangChain runnable graph."""
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "{question}"),
        ]
    )
    llm = ChatOpenAI(model="gpt-3.5-turbo")
    parser = StrOutputParser()
    return prompt | llm | parser


def run_cli(question: str | None = None) -> None:
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is missing. Create a .env file or export the variable.")

    if not question:
        question = input("请输入你的问题: ").strip()

    chain = build_chain()
    answer = chain.invoke({"question": question})
    print("\n--- 回答 ---\n")
    print(answer)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simple LangChain CLI demo.")
    parser.add_argument("question", nargs="?", help="Question or prompt to send to the LLM.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_cli(args.question)


if __name__ == "__main__":
    main()
