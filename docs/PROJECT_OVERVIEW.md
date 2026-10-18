# Project Overview — VSL Classroom Assistant

> Status: **Phase 1 (Foundation)**. Recognition does not exist yet. See [ROADMAP.md](ROADMAP.md).

## Problem

Deaf and hard-of-hearing students who use Vietnamese Sign Language (VSL) often cannot easily send a short message to a hearing teacher or classmate, such as "please repeat", "I don't understand", or "may I go out". Hearing teachers rarely sign. Interpreters are scarce. In everyday classroom moments the student usually has to write a note, gesture, or stay silent.

## What this project is

This is a **local-first web application** that runs on one laptop:

1. **VSL → text → speech (primary).** A webcam watches the student. The app recognises **one message unit at a time** from a **small vocabulary (20–50 items) that experts have validated**. It shows the Vietnamese text in large type. After the student **confirms**, the app reads the text aloud with a local Vietnamese voice.
2. **Speech → subtitles (secondary, gated).** The teacher holds a push-to-talk control. The spoken Vietnamese is transcribed locally and shown as subtitles.
3. **Manual text (always available).** Either person can type a message, and the app can speak it. This is the fallback whenever recognition is unavailable.

## What this project is NOT (honest scope)

- **Not a VSL translator.** VSL has its own grammar and uses handshape, movement, location, facial expression, and body posture. VSL words are not Vietnamese words made with the hands. This system classifies a closed set of message units only. It does not produce sentences, and it cannot understand free signing.
- **Not conversation monitoring.** Recognition runs only while the student has deliberately started it ("intentional message mode"). The student signs one unit, then returns their hands to rest.
- **Not validated for children or schools.** The MVP is built and piloted **only with adult participants**. Use in K-12 classrooms is a future phase and needs institutional approval and legal review.
- **No accuracy is promised.** Performance will be measured on signers the model has never seen and reported honestly.

## Users and scenarios

| User | Scenario |
|---|---|
| Deaf/HoH student (adult, VSL signer) | Starts recognition, signs "Xin nhắc lại" (please repeat), confirms, and the laptop speaks it. |
| Hearing teacher | Reads the confirmed message on the large display. Uses push-to-talk to reply, and subtitles appear for the student. |
| Hearing classmate | Types a reply in the manual text box. It appears in the transcript. |
| Developer / researcher | Records consented landmark data, trains small models, and evaluates them on held-out signers. |

## Guiding principles

1. **Privacy by design.** Camera video stays in the browser by default. Nothing is recorded unless someone explicitly consents in data-collection mode.
2. **Confirm before speaking.** A wrong word said aloud in class costs more than a request to sign again.
3. **Never rely on sound alone.** Every status is shown with text, an icon, and colour.
4. **Deaf people are partners.** VSL experts and Deaf signers validate the vocabulary, the data, and the UX.
5. **Simplest architecture that can be tested.** A modular monolith with no database or cloud. Each dependency must earn its place.

## Hardware context

- **Development:** MacBook Air M1, 8 GB RAM. Only unit tests and **mock model mode** run here. No ML models are downloaded or run on this machine.
- **Testing and inference:** Windows laptop, i5-11400H, 16 GB RAM, GTX 1650 with 4 GB VRAM. The real AI pipeline is tested only on this machine.

## Document map

| Document | Purpose |
|---|---|
| [REQUIREMENTS.md](REQUIREMENTS.md) | Functional and non-functional requirements, user stories, traceability |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Components, data flow, diagrams, failure modes |
| [REPOSITORY_STRUCTURE.md](REPOSITORY_STRUCTURE.md) | Every directory and file, with its purpose and phase |
| [API_CONTRACTS.md](API_CONTRACTS.md) | REST and WebSocket contracts |
| [AI_ML_STRATEGY.md](AI_ML_STRATEGY.md) | Recognition pipeline, models, evaluation |
| [DATASET_AND_ANNOTATION.md](DATASET_AND_ANNOTATION.md) | Vocabulary, consent, recording, splits |
| [UX_AND_ACCESSIBILITY.md](UX_AND_ACCESSIBILITY.md) | Screens, states, accessibility |
| [SECURITY_AND_PRIVACY.md](SECURITY_AND_PRIVACY.md) | Privacy and security controls |
| [CROSS_PLATFORM_SETUP.md](CROSS_PLATFORM_SETUP.md) | macOS and Windows setup and workflow |
| [TESTING_STRATEGY.md](TESTING_STRATEGY.md) | Test layers and merge gates |
| [ROADMAP.md](ROADMAP.md) | Phases, gates, exit criteria |
| [DECISIONS.md](DECISIONS.md) | Architecture decision records (ADRs) |
| [RISKS_AND_OPEN_QUESTIONS.md](RISKS_AND_OPEN_QUESTIONS.md) | Risks, review findings, open items |
