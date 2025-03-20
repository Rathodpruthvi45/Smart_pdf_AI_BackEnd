from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from huggingface_hub import InferenceClient
from dotenv import load_dotenv
import os
import shutil
from ...core.security import get_current_user
from ...models.user import User
from ...core.config import settings
from datetime import datetime

# Load environment variables
load_dotenv()

router = APIRouter()


# Pydantic models for request/response
class QuestionRequest(BaseModel):
    pdf_id: str
    num_questions: int = 5
    question_types: List[str] = [
        "multiple_choice",
        "descriptive",
    ]  # Allow multiple question types


class Question(BaseModel):
    question: str
    answer: str
    question_type: str
    options: Optional[List[str]] = None


class QuestionResponse(BaseModel):
    questions: List[Question]


# Initialize embeddings and LLM
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")
client = InferenceClient(token=settings.HUGGINGFACE_API_TOKEN)


def generate_text(prompt: str) -> str:
    try:
        # General system prompt that works for any content
        system_prompt = """Create clear questions based on the provided text. Format exactly as instructed."""

        # Trim prompt if too long
        if len(prompt) > 800:
            prompt = prompt[:800]

        full_prompt = f"{system_prompt}\n\n{prompt}"

        print(f"Sending prompt (length: {len(full_prompt)}): {full_prompt[:100]}...")

        response = client.text_generation(
            full_prompt,
            model="google/gemma-3-27b-it",
            max_new_tokens=250,
            temperature=0.4,
            top_p=0.8,
            do_sample=True,
            return_full_text=False,
        )
        print(f"Response length: {len(response)}")
        print(f"Response preview: {response[:100]}...")

        # Clean and format the response
        cleaned_response = response.strip()

        # Generic fallback for invalid responses
        if "Question:" not in cleaned_response:
            if "multiple_choice" in prompt:
                return """Question: What is the main topic discussed in this content?
Options:
A) The primary subject matter
B) A secondary concept
C) An unrelated topic
D) A tangential reference
Answer: A - The primary subject matter is the main focus of the text."""
            else:
                return """Question: Explain the key concept presented in this text.
Answer: The text discusses important information related to the main topic. It provides details, explanations, and examples to help understand the concept."""

        return cleaned_response

    except Exception as e:
        print(f"Error in text generation: {str(e)}")
        return f"Error: Could not generate question. Details: {str(e)}"


@router.post("/upload-pdf/", status_code=201)
async def upload_pdf(
    file: UploadFile = File(..., description="The PDF file to upload"),
    current_user: User = Depends(get_current_user),
):
    try:
        # Validate file type
        if not file.filename.endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")

        # Check if file is empty
        if not file.file:
            raise HTTPException(status_code=400, detail="No file provided")

        # Check user's subscription limits
        if not check_user_pdf_limits(current_user):
            raise HTTPException(
                status_code=403,
                detail="PDF upload limit reached for your subscription tier",
            )

        # Save PDF temporarily
        pdf_path = f"temp/{file.filename}"
        os.makedirs("temp", exist_ok=True)

        try:
            with open(pdf_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            # Process PDF
            loader = PyPDFLoader(pdf_path)
            documents = loader.load()

            # Split text
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000, chunk_overlap=200
            )
            texts = text_splitter.split_documents(documents)

            # Create vector store
            vectorstore = FAISS.from_documents(texts, embeddings)

            # Save vectorstore
            pdf_id = f"pdf_{current_user.id}_{file.filename}"
            vectorstore.save_local(f"vectorstores/{pdf_id}")

            return {"pdf_id": pdf_id}

        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error processing PDF: {str(e)}"
            )
        finally:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.post("/generate-questions/", response_model=QuestionResponse)
async def generate_questions(
    request: QuestionRequest, current_user: User = Depends(get_current_user)
):
    try:
        print(f"Received request data: {request.dict()}")

        if not check_question_generation_limits(current_user):
            raise HTTPException(
                status_code=403, detail="Monthly question generation limit reached"
            )

        vectorstore_path = f"vectorstores/{request.pdf_id}"
        if not os.path.exists(vectorstore_path):
            raise HTTPException(
                status_code=404, detail=f"PDF with ID {request.pdf_id} not found"
            )

        try:
            vectorstore = FAISS.load_local(
                vectorstore_path,
                embeddings,
                allow_dangerous_deserialization=True,
            )
            # Use page_content as metadata to track pages
            retriever = vectorstore.as_retriever(search_kwargs={"k": 2})
        except Exception as e:
            print(f"Error loading vectorstore: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error loading PDF data: {str(e)}"
            )

        questions = []
        questions_per_type = request.num_questions // len(request.question_types)
        remaining_questions = request.num_questions % len(request.question_types)

        # Generate diverse queries across different dimensions
        query_topics = [
            "main concepts and principles",
            "key terms and definitions",
            "important facts and figures",
            "processes and methods",
            "theories and frameworks",
            "examples and case studies",
            "problems and solutions",
            "causes and effects",
            "advantages and disadvantages",
            "historical developments",
            "practical applications",
            "future implications",
        ]

        # Track used subjects to avoid repetition
        used_subjects = set()
        used_questions = set()

        # Track which parts of the document we've used
        used_contexts = set()
        all_docs = []

        # Gather a pool of document chunks first to ensure diversity
        for topic in query_topics[:6]:  # Use first 6 topics to gather diverse content
            docs = retriever.get_relevant_documents(topic)
            for doc in docs:
                if doc.page_content not in used_contexts:
                    all_docs.append(doc)
                    # Only track the first 100 chars as a signature to allow some overlap
                    used_contexts.add(doc.page_content[:100])

        # If we didn't get enough chunks, get more with different queries
        if len(all_docs) < request.num_questions * 2:
            for i in range(10):  # Try up to 10 additional random terms
                random_term = f"topic_{i}"
                docs = retriever.get_relevant_documents(random_term)
                for doc in docs:
                    if doc.page_content not in used_contexts:
                        all_docs.append(doc)
                        used_contexts.add(doc.page_content[:100])
                if len(all_docs) >= request.num_questions * 2:
                    break

        print(f"Gathered {len(all_docs)} unique document chunks")

        print(
            f"Generating {request.num_questions} questions across {len(request.question_types)} types"
        )

        for q_type in request.question_types:
            num_questions = questions_per_type + (1 if remaining_questions > 0 else 0)
            remaining_questions -= 1 if remaining_questions > 0 else 0

            print(f"Generating {num_questions} questions of type {q_type}")

            for i in range(num_questions):
                try:
                    # Use a different document chunk for each question to ensure diversity
                    doc_index = (i + len(questions)) % len(all_docs)
                    doc = all_docs[doc_index]
                    context = doc.page_content[:350]  # Slightly longer context

                    query_index = (i + len(questions)) % len(query_topics)
                    query = query_topics[query_index]

                    print(f"Query for question {len(questions)+1}: {query}")
                    print(f"Context length: {len(context)}")
                    print(f"Context preview: {context[:50]}...")

                    # Extract potential subjects
                    words = context.split()

                    # Look for capitalized words that haven't been used yet
                    potential_subjects = [
                        w.strip(".,():;!?")
                        for w in words
                        if len(w) > 3
                        and w[0].isupper()
                        and w.strip(".,():;!?") not in used_subjects
                    ]

                    # Also look for key phrases using consecutive capitalized words
                    key_phrases = []
                    for j in range(len(words) - 1):
                        if (
                            len(words[j]) > 2
                            and words[j][0].isupper()
                            and len(words[j + 1]) > 2
                            and words[j + 1][0].isupper()
                        ):
                            phrase = f"{words[j]} {words[j+1]}".strip(".,():;!?")
                            key_phrases.append(phrase)

                    # Prioritize phrases, then single words, then fallback
                    if key_phrases:
                        subject = key_phrases[0]
                    elif potential_subjects:
                        subject = potential_subjects[0]
                    else:
                        # Find any technical or specific terms as backup
                        technical_terms = [
                            w.strip(".,():;!?")
                            for w in words
                            if len(w) > 5
                            and w.lower()
                            not in ["because", "therefore", "however", "although"]
                        ]
                        subject = (
                            technical_terms[0] if technical_terms else f"topic {i+1}"
                        )

                    # Add the chosen subject to used subjects
                    used_subjects.add(subject)

                    # Create dynamic prompts
                    if q_type == "multiple_choice":
                        # Vary the prompt structure for each question
                        prompt_templates = [
                            f"""Based on this text: {context}

Create a multiple choice question about {subject} using this format:
Question: (Ask about {subject} and its significance, purpose, or function)
Options:
A) (correct answer)
B) (plausible but incorrect answer)
C) (plausible but incorrect answer)
D) (plausible but incorrect answer)
Answer: (letter) - (brief explanation based on the text)""",
                            f"""From the following content: {context}

Generate a multiple choice question that tests understanding of {subject} with this format:
Question: (Ask about how {subject} works, relates to other concepts, or is applied)
Options:
A) (correct answer)
B) (plausible but incorrect answer)
C) (plausible but incorrect answer)
D) (plausible but incorrect answer)
Answer: (letter) - (brief explanation based on the text)""",
                            f"""Using this excerpt: {context}

Create a conceptual multiple choice question about {subject} using this format:
Question: (Ask about the characteristics, types, or components of {subject})
Options:
A) (correct answer)
B) (plausible but incorrect answer)
C) (plausible but incorrect answer)
D) (plausible but incorrect answer)
Answer: (letter) - (brief explanation based on the text)""",
                        ]
                        prompt = prompt_templates[i % len(prompt_templates)]
                    else:
                        # Vary descriptive question formats
                        prompt_templates = [
                            f"""Based on this text: {context}

Create a descriptive question about {subject} using this format:
Question: (Ask about what {subject} is and why it's important)
Answer: (Detailed explanation with relevant information from the text)""",
                            f"""From the following content: {context}

Generate a descriptive question that explores {subject} with this format:
Question: (Ask about how {subject} works or is implemented)
Answer: (Step-by-step explanation with examples from the text)""",
                            f"""Using this excerpt: {context}

Create an analytical descriptive question about {subject} using this format:
Question: (Ask about the impact, benefits, or challenges of {subject})
Answer: (Analytical explanation with evidence from the text)""",
                        ]
                        prompt = prompt_templates[i % len(prompt_templates)]

                    result = generate_text(prompt)
                    print(f"Question {len(questions)+1} result length: {len(result)}")

                    if "Error:" in result:
                        raise ValueError(result)

                    parts = result.split("Question:")
                    if len(parts) < 2:
                        raise ValueError(
                            f"Missing Question section in response: {result[:100]}..."
                        )

                    question_text = (
                        parts[1]
                        .split(
                            "Options:" if q_type == "multiple_choice" else "Answer:"
                        )[0]
                        .strip()
                    )

                    # Check if we've seen this question before to avoid duplicates
                    if question_text in used_questions:
                        raise ValueError(
                            f"Duplicate question detected: {question_text}"
                        )

                    used_questions.add(question_text)
                    print(f"Extracted question: {question_text}")

                    if q_type == "multiple_choice":
                        if "Options:" not in result or "Answer:" not in result:
                            raise ValueError(
                                f"Missing Options or Answer section in response: {result[:100]}..."
                            )

                        options_text = (
                            result.split("Options:")[1].split("Answer:")[0].strip()
                        )
                        options = [
                            opt.strip()[3:].strip()
                            for opt in options_text.split("\n")
                            if opt.strip()
                            and opt.strip().startswith(("A)", "B)", "C)", "D)"))
                        ]

                        print(f"Extracted {len(options)} options")

                        if len(options) != 4:
                            raise ValueError(
                                f"Incorrect number of options: {len(options)}"
                            )

                        answer = result.split("Answer:")[1].strip()
                    else:
                        options = None
                        if "Answer:" not in result:
                            raise ValueError(
                                f"Missing Answer section in response: {result[:100]}..."
                            )
                        answer = result.split("Answer:")[1].strip()

                    print(f"Extracted answer: {answer[:50]}...")

                    # Create the question object
                    question = Question(
                        question=question_text,
                        answer=answer,
                        question_type=q_type,
                        options=options if q_type == "multiple_choice" else None,
                    )
                    questions.append(question)
                    print(
                        f"Successfully added question {len(questions)} of type {q_type}"
                    )

                except Exception as e:
                    print(
                        f"Error generating question {len(questions)+1} of type {q_type}: {str(e)}"
                    )

                    # Create diverse fallback questions
                    if q_type == "multiple_choice":
                        # Create varied fallback questions
                        fallback_templates = [
                            {
                                "question": f"What is the primary role of {subject} described in the text?",
                                "answer": "A - It serves as a fundamental concept central to the topic being discussed.",
                                "options": [
                                    "It serves as a fundamental concept central to the topic being discussed",
                                    "It represents a minor detail with limited relevance",
                                    "It contradicts the main principles presented",
                                    "It is mentioned only as a historical reference",
                                ],
                            },
                            {
                                "question": f"How does {subject} relate to the other concepts in the text?",
                                "answer": "B - It works in conjunction with other elements to form a complete system.",
                                "options": [
                                    "It operates independently of all other components",
                                    "It works in conjunction with other elements to form a complete system",
                                    "It replaces older concepts mentioned in the text",
                                    "It serves as a counterexample to the main theory",
                                ],
                            },
                            {
                                "question": f"What characteristic of {subject} is emphasized in the content?",
                                "answer": "C - Its practical applications in real-world scenarios.",
                                "options": [
                                    "Its theoretical foundation and origins",
                                    "Its limitations and constraints",
                                    "Its practical applications in real-world scenarios",
                                    "Its historical development over time",
                                ],
                            },
                        ]

                        # Use a different template for each fallback
                        template_index = (i + len(questions)) % len(fallback_templates)
                        fallback = fallback_templates[template_index]

                        # Generate a question that hasn't been used before
                        question_text = fallback["question"]
                        # If somehow we still get a duplicate, modify slightly
                        if question_text in used_questions:
                            question_text = f"{question_text} (expanded)"

                        used_questions.add(question_text)

                        question = Question(
                            question=question_text,
                            answer=fallback["answer"],
                            question_type=q_type,
                            options=fallback["options"],
                        )
                    else:
                        # Create varied descriptive fallbacks
                        fallback_templates = [
                            {
                                "question": f"Explain the concept of {subject} as presented in the text.",
                                "answer": f"The text discusses {subject} as an important element that contributes to understanding the main topic. It has specific characteristics and functions that make it relevant in this context.",
                            },
                            {
                                "question": f"What are the key aspects of {subject} mentioned in the content?",
                                "answer": f"According to the text, {subject} encompasses several important aspects. These include its definition, purpose, and application within the broader framework discussed in the document.",
                            },
                            {
                                "question": f"How does {subject} function within the system described in the text?",
                                "answer": f"The text explains that {subject} functions by interacting with other components in the system. This interaction facilitates processes that are essential to the overall operation or concept being discussed.",
                            },
                        ]

                        template_index = (i + len(questions)) % len(fallback_templates)
                        fallback = fallback_templates[template_index]

                        question_text = fallback["question"]
                        if question_text in used_questions:
                            question_text = f"{question_text} (in detail)"

                        used_questions.add(question_text)

                        question = Question(
                            question=question_text,
                            answer=fallback["answer"],
                            question_type=q_type,
                            options=None,
                        )

                    questions.append(question)
                    print(f"Added fallback question {len(questions)} of type {q_type}")

        print(f"Generated total of {len(questions)} questions")
        return QuestionResponse(questions=questions)

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error in generate_questions: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error generating questions: {str(e)}"
        )


def check_user_pdf_limits(user: User) -> bool:
    # Get the user's active subscription
    active_subscription = next(
        (
            sub
            for sub in user.subscriptions
            if sub.is_active and sub.end_date > datetime.utcnow()
        ),
        None,
    )

    # If no active subscription, treat as free tier
    if not active_subscription:
        return len(user.pdfs) < 3  # Free tier limit

    # Check limits based on subscription plan
    if active_subscription.plan_name.lower() == "free":
        return len(user.pdfs) < 3
    elif active_subscription.plan_name.lower() == "pro":
        return len(user.pdfs) < 10
    return True  # Enterprise tier has no limit


def check_question_generation_limits(user: User) -> bool:
    # Get the user's active subscription
    active_subscription = next(
        (
            sub
            for sub in user.subscriptions
            if sub.is_active and sub.end_date > datetime.utcnow()
        ),
        None,
    )

    # If no active subscription, treat as free tier
    if not active_subscription:
        return True  # Free tier can generate questions

    # Check limits based on subscription plan
    if active_subscription.plan_name.lower() == "free":
        return True  # Free tier can generate questions
    elif active_subscription.plan_name.lower() == "pro":
        return True  # Pro tier can generate questions
    return True  # Enterprise tier has no limit
