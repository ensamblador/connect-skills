---
inclusion: manual
last_refreshed: 2026-06-05
workshop_count: 13
source_urls:
  - https://catalog.workshops.aws/self-service-ai-agents/en-US
  - https://catalog.workshops.aws/amazon-connect-fundamentals/en-US
  - https://catalog.workshops.aws/amazon-connect-ai-agents/en-US
  - https://catalog.us-east-1.prod.workshops.aws/workshops/b60d8bf5-1afe-460f-ba05-6e7ad35d37f9/en-US
  - https://catalog.workshops.aws/amazon-connect-3p-applications/en-US
  - https://catalog.workshops.aws/amazon-connect-outbound-campaigns/en-US
  - https://catalog.us-east-1.prod.workshops.aws/workshops/705f4a6b-6c3f-42ed-bb60-a76e27e78028/en-US
  - https://catalog.workshops.aws/amazon-connect-rules-engine/en-US
  - https://catalog.workshops.aws/amazon-connect-profiles/en-US
  - https://catalog.workshops.aws/amazon-connect-email/en-US
  - https://catalog.workshops.aws/amazon-connect-optimization/en-US
  - https://catalog.workshops.aws/amazon-connect-operational-workshop/en-US
  - https://catalog.us-east-1.prod.workshops.aws/workshops/f91b5bee-9028-47c0-b1c5-11acfec7c9f3/en-US
  - https://catalog.us-east-1.prod.workshops.aws/workshops/401c630f-2901-4f2d-8468-bd9a9066a78f/en-US
  - https://catalog.us-east-1.prod.workshops.aws/workshops/a0299a82-da56-4bd0-b8cb-d7f76dd42d09/en-US
  - https://catalog.us-east-1.prod.workshops.aws/workshops/f33ac20c-57f6-45ee-89fc-f80c5522e2bf/en-US
content_checksum: sha256:8c2faa8673da264d
---

# Amazon Connect workshops & how-to catalog

Quick lookup table for AWS-published Amazon Connect workshops on
``catalog.workshops.aws``. Each entry has a one-liner describing the
scope and a deep-linked module list so you can jump straight to the
right step without re-crawling the catalog.

**Activation:** opt-in. Reference from chat with `#aws-workshops` when
you need to point the user at an end-to-end tutorial, scaffold a
proof-of-concept, or copy a configuration pattern that is documented
as a workshop step.

**Freshness rule (for the agent):** before relying on this catalog,
compare the `last_refreshed` date in the front matter with today's
date. If the file is older than 30 days, run
``uv run python .kiro/hooks/scripts/refresh_aws_workshops.py`` to refresh it
before answering. Always refresh when the user explicitly asks for it.
The refresh script renders each landing page with Playwright (same
machinery the View component refresher uses) because these pages are
JavaScript-rendered and a plain HTTP fetch returns an empty shell.

**How to use this catalog:**
- Pick the workshop whose summary matches the user's intent.
- Use the module list to jump straight to the relevant step instead of
  the landing page.
- For multi-module bootcamps (e.g. Salesforce Contact Center with
  Amazon Connect), each module has its own one-paragraph abstract so
  you can route to the right module without opening the page.
- For module-level detail (commands, screenshots, JSON snippets), open
  the module URL in `web_fetch` with ``mode="rendered"``. Plain
  ``mode="full"`` returns an empty page on these catalogs.


---

## Building Intelligent Customer Service with Agentic AI on Amazon Connect

- **URL:** https://catalog.workshops.aws/self-service-ai-agents/en-US
- **One-liner:** Build an AI-powered self-service assistant for a fictional hotel chain using Amazon Connect AI Agents, MCP servers, and Bedrock AgentCore Gateway. Covers reservation handling, routine Q&A, and human escalation.
- **Modules:**
  - [Welcome to AnyCompany Hotels](https://catalog.workshops.aws/self-service-ai-agents/en-US/01-introduction)
  - [Building the Reservation System](https://catalog.workshops.aws/self-service-ai-agents/en-US/02-reservation-system)
  - [Handling Customer Questions](https://catalog.workshops.aws/self-service-ai-agents/en-US/03-handling-customer-questions)
  - [Human Escalation](https://catalog.workshops.aws/self-service-ai-agents/en-US/04-human-escalation)
  - [Experiment and Explore](https://catalog.workshops.aws/self-service-ai-agents/en-US/05-experiment-and-explore)
  - [References](https://catalog.workshops.aws/self-service-ai-agents/en-US/07-references)

---

## Amazon Connect Fundamentals

- **URL:** https://catalog.workshops.aws/amazon-connect-fundamentals/en-US
- **One-liner:** Introductory hands-on workshop covering Connect basics: queues, routing profiles, security profiles, users, a simple inbound flow, real-time and historical reporting, and Contact Lens conversational analytics.
- **Modules:**
  - [Prerequisites](https://catalog.workshops.aws/amazon-connect-fundamentals/en-US/00-introduction)
  - [Login into Amazon Connect Instance](https://catalog.workshops.aws/amazon-connect-fundamentals/en-US/00-alogin)
  - [Amazon Connect Concepts](https://catalog.workshops.aws/amazon-connect-fundamentals/en-US/01-amazonconnectbasics)
  - [Amazon Connect Reporting & Dashboards](https://catalog.workshops.aws/amazon-connect-fundamentals/en-US/02-amazonconnectreportingdashboards)
  - [Amazon Connect Conversational Analytics](https://catalog.workshops.aws/amazon-connect-fundamentals/en-US/03-amazonconnectanalytics)
  - [Amazon Connect Resources](https://catalog.workshops.aws/amazon-connect-fundamentals/en-US/05-amazonconnectresources)

---

## Amazon Connect AI Agents Workshop

- **URL:** https://catalog.workshops.aws/amazon-connect-ai-agents/en-US
- **One-liner:** Build action-oriented AI agents with Connect AI Agents + MCP integration. Covers orchestration agents, tool calling, 1P MCP tools (Cases, Customer Profiles, Tasks), Nova Sonic generative voice, AgentCore Gateway, guardrails, and observability.
- **Modules:**
  - [Foundation Module](https://catalog.workshops.aws/amazon-connect-ai-agents/en-US/01-foundation)
  - [Agent Assistance Track](https://catalog.workshops.aws/amazon-connect-ai-agents/en-US/02-agent-assistance-track)
  - [Self-Service Track](https://catalog.workshops.aws/amazon-connect-ai-agents/en-US/03-self-service-track)
  - [Additional AI Agent Capabilities](https://catalog.workshops.aws/amazon-connect-ai-agents/en-US/04-additional-ai-agent-capabilities)

---

## Amazon Connect Reporting and Dashboards

- **URL:** https://catalog.us-east-1.prod.workshops.aws/workshops/b60d8bf5-1afe-460f-ba05-6e7ad35d37f9/en-US
- **One-liner:** Build real-time and historical metric reports plus custom dashboards in Amazon Connect.
- **Modules:**
  - [1. Prerequisites](https://catalog.us-east-1.prod.workshops.aws/workshops/b60d8bf5-1afe-460f-ba05-6e7ad35d37f9/en-US/1prerequisites)
  - [2. Introduction](https://catalog.us-east-1.prod.workshops.aws/workshops/b60d8bf5-1afe-460f-ba05-6e7ad35d37f9/en-US/2introduction)
  - [3. Module 1 - Real-time Metrics](https://catalog.us-east-1.prod.workshops.aws/workshops/b60d8bf5-1afe-460f-ba05-6e7ad35d37f9/en-US/3realtimereports)
  - [4. Module 2 - Historical Metrics](https://catalog.us-east-1.prod.workshops.aws/workshops/b60d8bf5-1afe-460f-ba05-6e7ad35d37f9/en-US/4historicalreports)
  - [5. Module 3 - Login/Logout report](https://catalog.us-east-1.prod.workshops.aws/workshops/b60d8bf5-1afe-460f-ba05-6e7ad35d37f9/en-US/5loginlogout)
  - [6. Module 4 - Dashboards](https://catalog.us-east-1.prod.workshops.aws/workshops/b60d8bf5-1afe-460f-ba05-6e7ad35d37f9/en-US/6dashboard)

---

## Third party applications in the Amazon Connect agent workspace

- **URL:** https://catalog.workshops.aws/amazon-connect-3p-applications/en-US
- **One-liner:** Build custom third-party apps and services for the Connect Agent Workspace using the Amazon Connect SDK, and integrate them into Step-by-step Guides.
- **Modules:**
  - [Module 1: Using the Connect SDK to build a third-party application](https://catalog.workshops.aws/amazon-connect-3p-applications/en-US/module-1-home-page-app)
  - [Module 2: Third-party services for workspace automation](https://catalog.workshops.aws/amazon-connect-3p-applications/en-US/module-2-3p-services)
  - [Module 3: Integrating third-party apps into dynamic guided workflows](https://catalog.workshops.aws/amazon-connect-3p-applications/en-US/module-3-guided-workflows)
  - [Resources](https://catalog.workshops.aws/amazon-connect-3p-applications/en-US/resources)

---

## Amazon Connect - Multi-channel Outbound Campaigns

- **URL:** https://catalog.workshops.aws/amazon-connect-outbound-campaigns/en-US
- **One-liner:** End-to-end Outbound Campaigns workshop covering voice, SMS / email digital channels, event-based triggers, preview dialing, customer journeys, segmentation, and agent dispositions via step-by-step guides.
- **Modules:**
  - [Introduction](https://catalog.workshops.aws/amazon-connect-outbound-campaigns/en-US/1-introduction)
  - [Prerequisites](https://catalog.workshops.aws/amazon-connect-outbound-campaigns/en-US/2-prerequisites)
  - [How It Works — Animations](https://catalog.workshops.aws/amazon-connect-outbound-campaigns/en-US/3-how-it-works-animations)
  - [Outbound Campaigns - Voice](https://catalog.workshops.aws/amazon-connect-outbound-campaigns/en-US/4-voice)
  - [Outbound Campaigns - Digital](https://catalog.workshops.aws/amazon-connect-outbound-campaigns/en-US/5-digital)
  - [Outbound Campaigns - Event-based](https://catalog.workshops.aws/amazon-connect-outbound-campaigns/en-US/6-event-based)
  - [Outbound Campaigns - Preview Dialing](https://catalog.workshops.aws/amazon-connect-outbound-campaigns/en-US/7-preview-dialing)
  - [Outbound Campaigns - Journeys](https://catalog.workshops.aws/amazon-connect-outbound-campaigns/en-US/8-journeys)
  - [Segmentation Deep Dives](https://catalog.workshops.aws/amazon-connect-outbound-campaigns/en-US/9-segmentation-deep-dives)
  - [Agent Dispositions - Step By Step Guides](https://catalog.workshops.aws/amazon-connect-outbound-campaigns/en-US/10-agent-dispositions-step-by-step-guides)
  - [Frequently Asked Questions](https://catalog.workshops.aws/amazon-connect-outbound-campaigns/en-US/11-faq)
  - [Other Amazon Connect Training Materials](https://catalog.workshops.aws/amazon-connect-outbound-campaigns/en-US/14-amazon-conncet-free-training-materials)

---

## Amazon Connect Workspaces Workshop

- **URL:** https://catalog.us-east-1.prod.workshops.aws/workshops/705f4a6b-6c3f-42ed-bb60-a76e27e78028/en-US
- **One-liner:** Customise Agent Workspace and Admin Workspace using the no-code UI builder. Covers Views, Step-by-step Guides, Data Tables, Theming, persona-based workspaces, and supervisor business UIs (e.g. emergency closure).
- **Modules:**
  - [Foundation](https://catalog.us-east-1.prod.workshops.aws/workshops/705f4a6b-6c3f-42ed-bb60-a76e27e78028/en-US/01-foundation)
  - [Agent Workspace Track](https://catalog.us-east-1.prod.workshops.aws/workshops/705f4a6b-6c3f-42ed-bb60-a76e27e78028/en-US/02-agent-workspace-track)
  - [Admin Workspace Track](https://catalog.us-east-1.prod.workshops.aws/workshops/705f4a6b-6c3f-42ed-bb60-a76e27e78028/en-US/03-admin-workspace-track)

---

## Amazon Connect Rules Engine - Workshop

- **URL:** https://catalog.workshops.aws/amazon-connect-rules-engine/en-US
- **One-liner:** Use the Connect Rules Engine to automate contact center actions: real-time metric alerts, conversation analytics triggers, evaluation form follow-ups, case events, and schedule adherence notifications.
- **Modules:**
  - [1 Setup Amazon Connect](https://catalog.workshops.aws/amazon-connect-rules-engine/en-US/1-setup)
  - [2. Exercise 1 - Real Time Metrics Rules](https://catalog.workshops.aws/amazon-connect-rules-engine/en-US/2-realtimemetrics)
  - [3. Exercise 2 - Conversation Analytics Rules](https://catalog.workshops.aws/amazon-connect-rules-engine/en-US/3-conversationanalytics)
  - [4. Exercise 3 - Evaluation Form Rules](https://catalog.workshops.aws/amazon-connect-rules-engine/en-US/4-evaluationforms)
  - [5. Exercise 4 - Case Rules](https://catalog.workshops.aws/amazon-connect-rules-engine/en-US/5-cases)
  - [6. Exercise 5 - Schedule Adherence Notifications](https://catalog.workshops.aws/amazon-connect-rules-engine/en-US/6-scheduleadherence)

---

## Amazon Connect Customer Profiles Workshop

- **URL:** https://catalog.workshops.aws/amazon-connect-profiles/en-US
- **One-liner:** Build a unified customer profile inside Amazon Connect by ingesting data from external systems (Salesforce, ServiceNow, Zendesk, Marketo, S3) and surfacing it to agents. Covers Profile Object Types, personalized routing, and ML-powered identity resolution to dedupe customer records.
- **Modules:**
  - [1. Introduction](https://catalog.workshops.aws/amazon-connect-profiles/en-US/1-basics)
  - [2. Ingesting data into Customer Profiles](https://catalog.workshops.aws/amazon-connect-profiles/en-US/2-cont)
  - [3. Enable Personalized Routing and Automation using the Customer Profiles contact flow block](https://catalog.workshops.aws/amazon-connect-profiles/en-US/3-enablerouting)
  - [4. Use Identity Resolution to consolidate similar profiles](https://catalog.workshops.aws/amazon-connect-profiles/en-US/4-identity-resolution)

---

## Amazon Connect Email Enablement Workshop

- **URL:** https://catalog.workshops.aws/amazon-connect-email/en-US
- **One-liner:** Enable the Email channel in Amazon Connect end to end: addresses, security profiles, routing profiles, send/receive flows, templates and quick responses, plus integrations with Customer Profiles and Cases for agent continuity and case creation from emails.
- **Modules:**
  - [Introduction](https://catalog.workshops.aws/amazon-connect-email/en-US/01-introduction)
  - [Getting started with Amazon Connect Email](https://catalog.workshops.aws/amazon-connect-email/en-US/02-setup-email)
  - [Configure security profiles, create email addresses and update routing profiles](https://catalog.workshops.aws/amazon-connect-email/en-US/03-security-email-addresses-routing)
  - [Setting up basic flows to send and receive Email](https://catalog.workshops.aws/amazon-connect-email/en-US/04-setup-basic-flow)
  - [Creating email templates and quick responses](https://catalog.workshops.aws/amazon-connect-email/en-US/05-email-templates-quick-responses)
  - [Build your experience](https://catalog.workshops.aws/amazon-connect-email/en-US/06-use-cases)
  - [Email metrics and contact search](https://catalog.workshops.aws/amazon-connect-email/en-US/07-contact-search-metrics)

---

## Amazon Connect forecasting, capacity planning, and scheduling workshop

- **URL:** https://catalog.workshops.aws/amazon-connect-optimization/en-US
- **One-liner:** Hands-on with Amazon Connect Forecasting, Capacity Planning, and Scheduling: predict contact volume, convert forecasts into staffing needs, build daily shifts, and monitor schedule adherence.
- **Modules:**
  - [Introduction](https://catalog.workshops.aws/amazon-connect-optimization/en-US/1-introduction)
  - [Configuration](https://catalog.workshops.aws/amazon-connect-optimization/en-US/2-configuration)
  - [Forecasting in Amazon Connect](https://catalog.workshops.aws/amazon-connect-optimization/en-US/3-forecasting)
  - [Capacity planning in Amazon Connect](https://catalog.workshops.aws/amazon-connect-optimization/en-US/4-capacityplanning)
  - [Scheduling in Amazon Connect](https://catalog.workshops.aws/amazon-connect-optimization/en-US/5-scheduling)
  - [Agent Scheduling Analytics](https://catalog.workshops.aws/amazon-connect-optimization/en-US/6-analytics)

---

## Amazon Connect Operational Workshop

- **URL:** https://catalog.workshops.aws/amazon-connect-operational-workshop/en-US
- **One-liner:** Operate Amazon Connect in production: monitor and diagnose technical issues across voice, chat, flows, APIs, and the agent application. Covers the operational solution architecture, observability tooling, and hands-on flow / API / agent-app error simulations.
- **Modules:**
  - [1. Before you begin](https://catalog.workshops.aws/amazon-connect-operational-workshop/en-US/1beforeyoubegin)
  - [2. Amazon Connect Operations -Event-driven Insights](https://catalog.workshops.aws/amazon-connect-operational-workshop/en-US/2amazonconnectoperationseventdriveninsights)
  - [3. AWS services for Amazon Connect contact center operations](https://catalog.workshops.aws/amazon-connect-operational-workshop/en-US/3awsservicesforamazonconnectoperations)
  - [4. Exercise - Flow Error Analysis](https://catalog.workshops.aws/amazon-connect-operational-workshop/en-US/4exerciseflowerroranalysis)
  - [5. Exercise - Metrics, Alarms and Dashboard Management](https://catalog.workshops.aws/amazon-connect-operational-workshop/en-US/5exercisemetricsalarmdashboard)
  - [6. Exercise - Amazon Connect API Error Analysis](https://catalog.workshops.aws/amazon-connect-operational-workshop/en-US/6exerciseamazonconnectapi)
  - [7. Amazon Connect Agent Application Operations](https://catalog.workshops.aws/amazon-connect-operational-workshop/en-US/7amazonconnectagentoperations)
  - [8. Exercise - Agent Application Error Analysis](https://catalog.workshops.aws/amazon-connect-operational-workshop/en-US/8exerciseagenterroranalysis)
  - [9. Amazon Connect Operations Review and Continuous Improvements](https://catalog.workshops.aws/amazon-connect-operational-workshop/en-US/9operationsreview)
  - [10. Engaging AWS Support](https://catalog.workshops.aws/amazon-connect-operational-workshop/en-US/10engagingawssupport)

---

## Salesforce Contact Center with Amazon Connect

- **URL:** https://catalog.us-east-1.prod.workshops.aws/workshops/f91b5bee-9028-47c0-b1c5-11acfec7c9f3/en-US
- **One-liner:** Four-module bootcamp on Salesforce Contact Center with Amazon Connect (SCC-AC): generative-AI concepts and architecture, deploying SCC-AC in the Partner Telephony model on a Salesforce developer org, generative-AI self-service inside Salesforce, and generative-AI agent experience. Each module is a separate Workshop Studio workshop linked below.
- **Modules:**
  - **[Module 1: Generative AI concepts, features, architecture](https://catalog.us-east-1.prod.workshops.aws/workshops/f91b5bee-9028-47c0-b1c5-11acfec7c9f3/en-US)**
    Conceptual primer. Introduces Amazon Connect and Salesforce, walks through the integration options (Service Cloud Voice with Partner Telephony, Service Cloud Voice with Amazon Connect, and the CTI Adapter), then zooms in on Salesforce Contact Center with Amazon Connect (SCC-AC) — its architectural choices, generative-AI overview, common contact-center use cases, and the specific generative-AI features Connect ships (Q in Connect, post-contact summarization, AI Agents, Contact Lens, etc.). No deployment yet; this is the slide deck before the labs.
  - **[Module 2: Setup (Service Cloud Voice with Partner Telephony from Amazon Connect)](https://catalog.us-east-1.prod.workshops.aws/workshops/401c630f-2901-4f2d-8468-bd9a9066a78f/en-US)**
    Hands-on deployment. End-to-end install of SCC-AC on a Salesforce developer org in the Partner Telephony model: create the Salesforce Contact Center, validate the Service Cloud Voice deployment, install and configure the SCC-AC managed package, run the guided setup, enable it for the Contact Center, and configure Voice, Messaging, and Omni-Channel routing. Closes with an omni-channel validation and an optional Salesforce REST API access lab. After this module you have a working SCC-AC environment to build Modules 3 and 4 on top of.
  - **[Module 3: Generative AI powered self service](https://catalog.us-east-1.prod.workshops.aws/workshops/a0299a82-da56-4bd0-b8cb-d7f76dd42d09/en-US)**
    Self-service labs. Builds a generative-AI self-service experience inside SCC-AC using Q in Connect (QiC) on Salesforce knowledge as the LLM-grounded knowledge base. Covers the self-service architecture and prompt engineering, then walks through five labs: (1) wire QiC to Salesforce KB, (2) enable QiC inside an Amazon Lex bot, (3) build the Connect contact flow that calls the QiC-enabled bot, (4) author a Prompt for self-service answers, and (5) stand up a customer-facing chat website. Ends with a live test of the QiC self-service path.
  - **[Module 4: Generative AI powered agent experience](https://catalog.us-east-1.prod.workshops.aws/workshops/f33ac20c-57f6-45ee-89fc-f80c5522e2bf/en-US)**
    Agent-assist labs. Layers Connect's generative-AI agent-experience features on top of the SCC-AC environment from Module 2: post-contact summarization (auto-fill the Salesforce wrap-up screen), Amazon Connect AI Agents for live in-call assistance, and Contact Lens performance evaluations to grade interactions and surface coaching cues. Each feature is enabled, configured in SCC-AC, and exercised on a sample contact so the agent sees the gen-AI output inside the Salesforce omni-channel widget.
