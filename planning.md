# Project 1 Planning: The Unofficial Guide

> Write this document before you write any pipeline code.
> Your spec and architecture diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Update the Retrieval Approach and Chunking Strategy sections if you change your approach during implementation.
> Update this file before starting any stretch features.

---

## Domain

<!-- What domain did you choose? Why is this knowledge valuable and hard to find through official channels? -->
This system answers questions about Computer Science courses, electives, and degree requirements at Mercy University (formerly Mercy College), drawing on the official course catalog and degree requirements alongside informal student reviews from Rate My Professors and Coursicle. The information is hard to find otherwise because it's scattered across multiple sites with very different formats — official sources tell you what a course covers but not what it's like to take, and student reviews are spread across individual professor pages with no way to search across them. A single search interface that combines structural facts (prerequisites, when courses are offered, who teaches them) with student perspectives lets CS students at Mercy make better choices about electives and plan their semesters more confidently.

---

## Documents

<!-- List your specific sources: URLs, subreddit names, forum threads, or file descriptions.
     Aim for at least 10 sources that together cover different subtopics or perspectives within your domain. -->

| # | Source | Description | URL or location |
|---|--------|-------------|-----------------|
| 1 | Mercy course catalog |Official CS course listings with descriptions, credits, and prereqs| https://ug.catalog.mercy.edu/courses?page=1&cq=computer+science|
| 2 | Mercy BS Computer Science degree requirements | Official PDF listing required courses by semester with prereqs and coreqs | https://mercy.edu/media/2024-2025-bs-computer-science|
| 3 |  Coursicle (Mercy CISC) | Shows which CS courses are actually offered, when, and by whom | https://www.coursicle.com/mercy/courses/CISC/ |
| 4 | Rate My Professors — Samer Almazahreh | Student reviews of CS professor | https://www.ratemyprofessors.com/professor/1725736 |
| 5 | Rate My Professors — John Marchan | Student reviews of CS professor | https://www.ratemyprofessors.com/professor/2575199 |
| 6 | Rate My Professors — Sisi Li | Student reviews of CS professor | https://www.ratemyprofessors.com/professor/3120865 |
| 7 | Rate My Professors — Marion Ben-Jacob | Student reviews of CS professor | https://www.ratemyprofessors.com/professor/789013 | 
| 8 | Rate My Professors — Brian Landin | Student reviews of CS professor | https://www.ratemyprofessors.com/professor/2909340 |
| 9 | Rate My Professors — Angelo Ordonez | Student reviews of CS professor | https://www.ratemyprofessors.com/professor/2206397 | 
| 10 | Rate My Professors — Yun Wang | Student reviews of CS professor | https://www.ratemyprofessors.com/professor/1817836 |

---

## Chunking Strategy

<!-- How will you split documents into chunks?
     State your chunk size (in tokens or characters), overlap size, and explain why those
     numbers fit the structure of your documents.
     A review-heavy corpus warrants different chunking than a long FAQ. -->

**Chunk size:**
depends on structure, because all sources have different structures.
**Overlap:**
overlap = 0 for all three source types, because chunks are complete semantic units with no shared content across boundaries.
**Reasoning:**
My documents have three very different shapes, so a single chunk size would either over-split the short stuff or break apart the structured stuff:

- **Rate My Professors reviews** one review = one chunk. Otherwise reviews are mixed and messy because the review will either be cut short or have another review attached, which will give an inaccurate and confusing response because it is two different opinions being put into one review.
- **Coursicle course descriptions** one course = one chunk because students will want the whole course description, otherwise it will be cut.
- **Degree requirements PDF** by semester = one chunk because those will be very common questions, and if we chunked it another way it won't be able to answer this question correctly — it may give you 3 classes out of the 4 you have to take. If you wanted to ask a specific question like what is the prereq or coreq of Artificial Intelligence, it's better if you gave some extra information attached to this answer than if you chunked by class, since it might not be able to find this info.

Small overlap on prose chunks (Coursicle descriptions) helps catch cases where a key phrase sits at a boundary; no overlap is needed for already-discrete chunks (individual reviews, semester blocks).

---

## Retrieval Approach

<!-- Which embedding model are you using (e.g., all-MiniLM-L6-v2 via sentence-transformers)?
     How many chunks will you retrieve per query (top-k)?
     If you were deploying this for real users and cost wasn't a constraint, what tradeoffs
     would you weigh in choosing a different embedding model — context length, multilingual
     support, accuracy on domain-specific text, latency? -->

**Embedding model:**
Using MiniLM because it runs locally and it was given to us.
**Top-k:**
I'll start at 4 because 3 out of 5 questions are just one-fact answers, but the other 2 are about Rate My Professors reviews, so I think 4 reviews are a good consensus on the professors. I'll tweak as I go if needed. The Data Structures professor question only has one review, so making k any higher wouldn't benefit anything there.
**Production tradeoff reflection:**
If cost didn't matter, I would use a larger model because MiniLM's 256-token window might be too small for semester blocks, so I would use a bigger model that handles higher tokens to make sure no chunks get cut off. All sources are English so I don't need multilingual support. For domain-specific accuracy, my sources have two very distinct styles, so a more powerful or specialized model might handle these differences better than the general MiniLM.
---

<!-- TODO Milestone 5: consider letting users get answers translated even though sources are English -->

## Evaluation Plan

<!-- List your 5 test questions with their expected correct answers.
     Questions should be specific enough that you can judge whether the system's response
     is right or wrong. "What are good dining halls?" is too vague.
     "What do students say about wait times at [dining hall name] during lunch?" is testable. -->

| # | Question | Expected answer |
|---|----------|-----------------|
| 1 | Who teaches Object/Structure/Algorithm I at Mercy and what do students say about them? | Sisi Li. The single review says she doesn't know how to explain concepts properly | 
| 2 | What courses do I need to take in my second semester as a CS major? | ENGL112 Written Engl and Lit Studies II, MATH201 Precalculus, CISC131 Foundations of Computing I, COMM110 Oral Communication, Gen Ed | 
| 3 | How is Samer Almazahreh as a professor at Mercy College? | Mixed reviews, some students say not to take him because he is terrible and others say he is knowledgeable and supportive |
| 4 |  What is the corequisite or prerequisite for the Artificial Intelligence class at Mercy College? | CISC339 Artificial Intelligence requires CISC231 (Foundations of Computing II) and MATH244 (Discrete Structures) as prerequisites | 
| 5 | Does Mercy College have any Game Design classes? | Yes, Game Design 1 | 

---

## Anticipated Challenges

<!-- What could go wrong? Name at least two specific risks with reasoning.
     Consider: noisy or inconsistent documents, missing source attribution, off-topic
     retrieval, chunks that split key information across boundaries. -->

1. My sources are skewed toward professor opinions (7 of 10). If a student asks a question like "how many CS classes are there in total?" my system would struggle because most sources are about professors opinions and don't contain class count at all, and the other sources have catalogs of classes but not a total number of classes.

2. For the Data Structures question, there is only 1 review. I think the system will try to look for more reviews because of how the question is written, and it won't be able to find them so it will probably give other answers about different things plus the actual answer. It also may hallucinate and give something like "most students say..." when there is only one review and the system is just trying to answer the question fully even if it's not true.

3. I need to scrape irrelevant information off the websites except what's needed. Scraped pages contain ads, sidebars, navigation, footers, etc., and if it's left in, it may embed itself as a part of the chunks and it will create irrelevance in the chunks.

4. The degree requirements PDF is a multi-column table, and `pdfplumber` extracts text in reading order rather than preserving columns, which can bunch up information like adding the prereqs/coreqs as a part of the course number. This matters because if this happens, questions like the AI prereq one will give the wrong answer because the prereq is attached to the course name, and the chunks rely on clean semester blocks.
---

## Architecture

<!-- Draw a diagram of your pipeline showing the five stages:
     Document Ingestion → Chunking → Embedding + Vector Store → Retrieval → Generation
     Label each stage with the tool or library you're using.
     You can use ASCII art, a Mermaid diagram, or embed a sketch as an image.
     You'll use this diagram as context when prompting AI tools to implement each stage. -->

```
┌─────────────────────────────┐
│  Document Ingestion         │  Pull from URLs in the Documents table:
│  (requests, BeautifulSoup,  │  — HTML for Mercy catalog, Coursicle, RMP
│   pdfplumber)               │  — PDF for degree requirements
│                             │  Strip ads, sidebars, nav, footers
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│  Chunking                   │  Source-aware chunking (no fixed size):
│  (custom Python)            │  — RMP: 1 review = 1 chunk
│                             │  — Coursicle: 1 course = 1 chunk
│                             │  — Requirements PDF: 1 semester = 1 chunk
│                             │  Overlap = 0
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│  Embedding + Vector Store   │  sentence-transformers (all-MiniLM-L6-v2)
│                             │  → ChromaDB (local, persistent)
│                             │  Metadata: source type, professor, course
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│  Retrieval                  │  Semantic search, top-k = 4
│  (ChromaDB query)           │  Returns chunks + metadata
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│  Generation                 │  Groq llama-3.3-70b-versatile
│  (Groq API)                 │  Prompt: answer ONLY from retrieved chunks,
│                             │  cite source URLs
└─────────────────────────────┘
```
---

## AI Tool Plan

<!-- For each part of the pipeline below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, which requirements)
     - What you expect it to produce
     - How you'll verify the output matches your spec

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Chunking Strategy section and ask it to implement chunk_text()
     with my specified chunk size and overlap" is a plan. -->

     
**Milestone 3 — Ingestion and chunking:**
I'll use Claude and give it the Documents table and Chunking Strategy, then ask it to write three ingestion functions that output a list of text, URL, and metadata. I'll skim through it to make sure that the extracted data is clean with no nav/ads and that the metadata fields (professor's name, course code, semester) are populated correctly for at least one example per source type.
**Milestone 4 — Embedding and retrieval:**
I'll use Claude and give it the Retrieval Approach section, then ask it to write code using MiniLM that stores chunks in ChromaDB with metadata and uses a k=4 retrieval function. I'll verify by running my 5 questions and checking that the retrieved chunks are about the right professor, course, or semester depending on the question, before the LLM sees them.
**Milestone 5 — Generation and interface:**
I'll use Claude and give it the Architecture diagram and Anticipated Challenges section, then ask it to use the Groq API with a prompt that forces grounded answers only. For the interface, I'll start with a CLI since the assignment allows it. For verification, I'll compare the output to my expected answers for each of the 5 test questions.