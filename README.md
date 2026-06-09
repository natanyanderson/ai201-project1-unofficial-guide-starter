# The Unofficial Guide — Project 1

> **How to use this template:**
> Complete each section *after* you've built and tested the corresponding part of your system.
> Do not write placeholder text — if a section isn't done yet, leave it blank and come back.
> Every section below is required for submission. One-liners will not receive full credit.

---

## Domain

<!-- What topic or category of knowledge does your system cover?
     Why is this knowledge valuable, and why is it hard to find through official channels?
     Example: "Student reviews of CS professors at [university] — useful because official
     course descriptions don't reflect teaching style, exam difficulty, or workload." -->

This system answers questions about Computer Science courses, electives, and degree requirements at Mercy University (formerly Mercy College), using the official course catalog and degree requirements alongside informal student reviews from Rate My Professors and Coursicle. The information is hard to find simply because it's scattered across multiple sites with very different formats and structures — official sources tell you what a course covers but not what it's like to take, and student reviews are spread across individual professor pages with no way to search across them. A single search interface that combines structural facts (prerequisites, when courses are offered, who teaches them) with student perspectives lets CS students at Mercy make better choices about electives and plan their semesters more confidently.

---

## Document Sources

<!-- List every source you collected documents from.
     Be specific: include URLs, subreddit names, forum thread titles, or file names.
     Aim for variety — sources that together cover different subtopics or perspectives. -->

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

<!-- Describe your chunking approach with enough specificity that someone else could reproduce it.
     Include:
     - Chunk size (characters or tokens) and why that size fits your documents
     - Overlap size and why (or why not) you used overlap
     - Any preprocessing you did before chunking (e.g., stripping HTML, removing headers)
     - What your final chunk count was across all documents -->

**Chunk size:**
depends on structure, because all sources have different structures.
**Overlap:**
overlap = 0 for all four source types, because chunks are complete semantic units with no shared content across boundaries.
**Why these choices fit your documents:**
My documents have four  very different shapes, so a single chunk size would either over-split the short stuff or break apart the structured stuff:

- **Rate My Professors reviews** one review = one chunk. Otherwise reviews are mixed and messy because the review will either be cut short or have another review attached, which will give an inaccurate and confusing response because it is two different opinions being put into one review.
- **Coursicle course descriptions** one course = one chunk because students will want the whole course description, otherwise it will be cut.
- **Degree requirements PDF** by semester = one chunk because those will be very common questions, and if we chunked it another way it won't be able to answer this question correctly — it may give you 3 classes out of the 4 you have to take. If you wanted to ask a specific question like what is the prereq or coreq of Artificial Intelligence, it's better if you gave some extra information attached to this answer than if you chunked by class, since it might not be able to find this info. Note that every semester chunks has a noisy last line where the final course row gets smushed with the credit total and some footer next. Ex: the Year 4 Fall chunk picks up footer legend text from the bottom of the PDF (e.g., 'PROGRAM TOTALS Credits: 120 Legend: CR: Credits...') and Year 1 Fall last line: CISC120 Intro Computers & App Software | 3 | x Gen Ed or ENGL 110 3 x Term Credit Total: 15 15
I left this for now and will revisit it if the noise causes retrieval problems in evaluation.
- **Course Catalog** one course = one chunk. The catalog is by courses with descriptions and requirements. 

**Final chunk count:**
124 chunks total. 88 RMP + 15 Coursicle + 13 Catalog + 8 requirements.

Preprocessing happens during ingestion. My ingestion script cleans documents before chunking by stripping "Source:" headers, removing "Section information text:" artifacts from Coursicle and adding "Student review of Professor X" to RMP chunks.

---

## Embedding Model

<!-- Name the embedding model you used and explain your choice.
     Then answer: if you were deploying this system for real users and cost wasn't a constraint,
     what tradeoffs would you weigh in choosing a different model?
     Consider: context length limits, multilingual support, accuracy on domain-specific text,
     latency, and local vs. API-hosted. -->

**Model used:**

**Production tradeoff reflection:**

---

## Grounded Generation

<!-- Explain how your system enforces grounding — how does it prevent the LLM from answering
     beyond the retrieved documents?
     Describe both your system prompt (what instruction you gave the model) and any structural
     choices (e.g., how you formatted the context, whether you filtered low-relevance chunks).
     Do not just say "I told it to use the documents" — show the actual instruction or explain
     the mechanism. -->

**System prompt grounding instruction:**

**How source attribution is surfaced in the response:**

---

## Evaluation Report

<!-- Run your 5 test questions from planning.md through your system and record the results.
     Be honest — a partially accurate or inaccurate result that you explain well is more
     valuable than a suspiciously perfect result. -->

| # | Question | Expected answer | System response (summarized) | Retrieval quality | Response accuracy |
|---|----------|-----------------|------------------------------|-------------------|-------------------|
| 1 | Who teaches Object/Structure/Algorithm I at Mercy and what do students say about them? | Sisi Li, single review says can't explain concepts | Sisi Li teaches CISC311. No student review in context. | Partially relevant | Partially accurate |
| 2 | What courses do I need to take in my second semester as a CS major? | ENGL112, MATH201, CISC131, COMM110, Gen Ed | Exactly correct, Year 1 Spring listed | Relevant | Accurate |
| 3 | How is Samer Almazahreh as a professor at Mercy College? | Mixed reviews | Mixed reviews, specific quotes cited | Relevant | Accurate |
| 4 | What is the corequisite or prerequisite for the Artificial Intelligence class at Mercy College? | CISC231/MATH231 and MATH244 | Exactly correct, Prerequisites are CISC231/MATH231 and MATH244, sourced from catalog | Relevant | Accurate |
| 5 | Does Mercy College have any Game Design classes? | Yes, Game Design I | "I don't have enough information" | Off-target | Inaccurate |

**Retrieval quality:** Relevant / Partially relevant / Off-target  
**Response accuracy:** Accurate / Partially accurate / Inaccurate

---

## Failure Case Analysis

<!-- Identify at least one question where retrieval or generation did not work as expected.
     Write a specific explanation of *why* it failed, tied to a part of the pipeline.

     "The answer was wrong" is not an explanation.

     "The relevant information was split across a chunk boundary, so retrieval returned
     only half the context — the model didn't have enough to answer correctly" is an explanation.

     "The embedding model treated the professor's nickname as out-of-vocabulary and returned
     results from an unrelated review" is an explanation. -->

**Question that failed:**
Does Mercy have any Game Design classes?
**What the system returned:**
I don't have enough information in my sources to answer that.
**Root cause (tied to a specific pipeline stage):**
The failure is at the retrieval stage. The query "Does Mercy have any Game Design classes" returned 4 RMP professor reviews with distances between 0.50 and 0.55. Zero course chunks. CISC360 Game Design I exists in my Coursicle file and was ingested correctly (15 Coursicle chunks including CISC360), but it didn't surface at all. This happened because when searching for "Game Design classes," the embedding model finds chunks that are semantically close to "class" and "teaching" which describes almost every RMP review. The word "class" in the query is pulling RMP chunks about classes in general, not the specific course CISC360. The embedding model (all-MiniLM-L6-v2) is a general-purpose model that doesn't know "Game Design classes" at a university is specifically asking about course catalog entries. This is the source-skew failure I predicted in Anticipated Challenge #1 — 88 of 124 chunks are RMP reviews, so the embedding space is dominated by professor-opinion text and course-existence queries get drowned out.
**What you would change to fix it:**
I can either do metadata filtering that lets me query only Coursicle/catalog chunks when the question is about course existence or adding more course-type chunks to rebalance the corpus.
---

## Spec Reflection

<!-- Reflect on how planning.md shaped your implementation.
     Answer both questions with at least 2–3 sentences each. -->

**One way the spec helped you during implementation:**
It helped me be more efficient and lay out my thoughts. Like when I prompted Claude for ingestion code, I handed it the Documents table and Chunking Strategy and got good, useful code back. I would not have been able to get useful code if I had not handed Claude context about my project. 
**One way your implementation diverged from the spec, and why:**
The catalog source turned out not to be scrapeable so I had to manually copy-paste instead of writing a scraper. The Mercy catalog uses JavaScript rendering, so a standard HTTP scraper would have returned an empty page so manual copy-paste was the only reliable option. I did this to get the correct answers and format instead of trying to take a shortcut I knew wouldn't even work. 
---

## AI Usage

<!-- Describe at least 2 specific instances where you used an AI tool during this project.
     For each: what did you give the AI as input, what did it produce, and what did you
     change, override, or direct differently?

     "I used Claude to help me code" is not sufficient.
     "I gave Claude my Chunking Strategy section from planning.md and asked it to implement
     chunk_text(). It returned a function using a fixed character split. I overrode the
     chunk size from 500 to 200 because my documents are short reviews, not long guides." -->

**Instance 1**

- *What I gave the AI:*
 I gave Claude my Documents table, Chunking Strategy, and example files, and asked it to write three ingestion functions. 
- *What it produced:*
It produced an ingestion script with PDF parsing code. The first version treated the two-column PDF layout as a single table, merging Fall and Spring semester courses onto the same row, giving only 4 requirements chunks instead of 8.
- *What I changed or overrode:*
I caught the two-column layout bug, leading to a second iteration where I specified I caught a bug and what I was looking for. 

**Instance 2**

- *What I gave the AI:*
I gave Claude my Retrieval Approach section
- *What it produced:*
It produced a ChromaDB embedding and retrieval script using all-MiniLM-L6-v2 with a persistent local collection and a retrieve(query, k=4) function.
- *What I changed or overrode:*
It caught the cosine distance issue and added a truncation warning I hadn't asked for. I accepted the cosine distance suggestion since it made distance scores easier to interpret. I left DISTANCE_THRESHOLD as None because I wanted to see real retrieval results before picking a cutoff.