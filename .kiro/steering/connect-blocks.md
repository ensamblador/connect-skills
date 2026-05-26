---
inclusion: manual
last_refreshed: 2026-05-24
block_count: 55
source_urls:
  - https://docs.aws.amazon.com/connect/latest/adminguide/contact-block-definitions.html
  - https://docs.aws.amazon.com/connect/latest/adminguide/block-support-by-channel.html
content_checksum: sha256:3701e6a9bfb9afeb
---

# Connect flow block catalog

Quick lookup table for every flow block in Amazon Connect, joined from
the two source pages below. Refresh with
``uv run python scripts/refresh_connect_blocks.py``.

**Activation:** this file is opt-in. Reference it from chat with
`#connect-blocks` when you're sketching a flow, picking blocks for a
mermaid diagram, or generating Flow language JSON.

**Freshness rule (for the agent):** before relying on this catalog,
compare the `last_refreshed` date in the front matter with today's
date. If the file is older than 7 days, run
``uv run python scripts/refresh_connect_blocks.py`` to refresh it
before answering. Always refresh when the user explicitly asks for it.
A regenerated file with no diff is fine — `last_refreshed` is the only
thing that needs updating, and the script handles that automatically.

**Channel column legend** (in `V C T E` order: Voice, Chat, Task, Email):
``+`` supported, ``~`` not supported but emits an Error branch,
``-`` not supported, ``?`` not listed in the channel-support page.

For depth on any block (parameters, branches, examples), follow the
block name link. For the language and JSON shape see the
[Connect Flow language reference](https://docs.aws.amazon.com/connect/latest/APIReference/flow-language.html).

| Block | Channels | Description |
| --- | --- | --- |
| [Authenticate Customer](https://docs.aws.amazon.com/connect/latest/adminguide/authenticate-customer.html) | V~ C+ T~ E~ | Enables the customer to authenticate by using Amazon Cognito and Connect Customer Customer Profiles. |
| [AWS Lambda function](https://docs.aws.amazon.com/connect/latest/adminguide/invoke-lambda-function-block.html) | V+ C+ T+ E+ | Calls AWS Lambda, optionally returns key-value pairs. |
| [Call phone number](https://docs.aws.amazon.com/connect/latest/adminguide/call-phone-number.html) | V+ C~ T~ E~ | Initiates an outbound call from an outbound whisper flow. |
| [Cases](https://docs.aws.amazon.com/connect/latest/adminguide/cases-block.html) | V+ C+ T+ E+ | Gets, updates, and creates cases. |
| [Change routing priority / age](https://docs.aws.amazon.com/connect/latest/adminguide/change-routing-priority.html) | V+ C+ T+ E+ | Changes the priority of the contact in queue. You may want to do this, for example, based on the contact's issue or other variable. |
| [Check call progress](https://docs.aws.amazon.com/connect/latest/adminguide/check-call-progress.html) | V+ C~ T~ E~ | Engages with the output provided by an answering machine, and provides branches to route the contact accordingly. This block works with outbound campaigns only. |
| [Check contact attributes](https://docs.aws.amazon.com/connect/latest/adminguide/check-contact-attributes.html) | V+ C+ T+ E+ | Checks the values of contact attributes. |
| [Check hours of operation](https://docs.aws.amazon.com/connect/latest/adminguide/check-hours-of-operation.html) | V+ C+ T+ E+ | Checks whether the contact is occurring within or outside of the hours of operation defined for the queue. |
| [Check queue status](https://docs.aws.amazon.com/connect/latest/adminguide/check-queue-status.html) | V+ C+ T+ E+ | Checks the status of the queue based on specified conditions. |
| [Check staffing](https://docs.aws.amazon.com/connect/latest/adminguide/check-staffing.html) | V+ C+ T+ E+ | Checks the current working queue, or queue you specify in the block, for whether agents are available, staffed, or online. Staffed availability could be on call, or after contact work status. |
| [Check Voice ID](https://docs.aws.amazon.com/connect/latest/adminguide/check-voice-id.html) | V+ C~ T~ E~ | Branches based on the enrollment status, voice authentication status, or status of detection of fraudsters in a watchlist of the caller returned by Voice ID. |
| [Connect assistant](https://docs.aws.amazon.com/connect/latest/adminguide/connect-assistant-block.html) | V+ C+ T~ E+ | Associates an Connect AI agents domain to a contact to enable real-time recommendations. |
| [Contact tags](https://docs.aws.amazon.com/connect/latest/adminguide/contact-tags-block.html) | V+ C+ T+ E+ | Create and apply user-defined tags (key:value pairs) to your contacts. |
| [Create persistent contact association](https://docs.aws.amazon.com/connect/latest/adminguide/create-persistent-contact-association-block.html) | V~ C+ T~ E~ | Specify an attribute to create a persistent contact association, enabling conversations to continue from where they left off. |
| [Create task](https://docs.aws.amazon.com/connect/latest/adminguide/create-task-block.html) | V+ C+ T+ E+ | Creates a new task, sets the tasks attributes, and initiates a contact flow to start the task. To learn more about Connect Customer Tasks, see [The task channel in Connect Customer](tasks.md). |
| [Customer profiles](https://docs.aws.amazon.com/connect/latest/adminguide/customer-profiles-block.html) | V+ C+ T+ E+ | Enables you to retrieve, create, and update a customer profile. |
| [Data Table](https://docs.aws.amazon.com/connect/latest/adminguide/data-table-block.html) | ? | Evaluate, list, or write data from data tables within your contact flows. |
| [Disconnect / hang up](https://docs.aws.amazon.com/connect/latest/adminguide/disconnect-hang-up.html) | V+ C+ T+ E+ | Disconnects a contact. |
| [Distribute by percentage](https://docs.aws.amazon.com/connect/latest/adminguide/distribute-by-percentage.html) | V+ C+ T+ E+ | Routes customers randomly based on a percentage. |
| [End flow / Resume](https://docs.aws.amazon.com/connect/latest/adminguide/end-flow-resume.html) | V+ C+ T+ E+ | Ends the current flow without disconnecting the contact. |
| [Get customer input](https://docs.aws.amazon.com/connect/latest/adminguide/get-customer-input.html) | V+ C? T- E- | Branches based on customer intent. |
| [Get metrics](https://docs.aws.amazon.com/connect/latest/adminguide/get-queue-metrics.html) | V+ C+ T+ E+ | Retrieves real-time metrics about queues and agents in your contact center and returns them as attributes. |
| [Get stored content](https://docs.aws.amazon.com/connect/latest/adminguide/get-stored-content.html) | ? | Retrieves content stored in S3 and returns them as attributes to be used within flows. |
| [Hold customer or agent](https://docs.aws.amazon.com/connect/latest/adminguide/hold-customer-agent.html) | V+ C~ T~ E~ | Places a customer or agent on or off hold. |
| [Invoke module](https://docs.aws.amazon.com/connect/latest/adminguide/invoke-module-block.html) | V+ C+ T+ E+ | Calls a published module. |
| [Loop](https://docs.aws.amazon.com/connect/latest/adminguide/loop.html) | V+ C+ T+ E+ | Loops through, or repeats, the **Looping** branch for the number of loops specified or the number of elements in the provided array. |
| [Loop prompts](https://docs.aws.amazon.com/connect/latest/adminguide/loop-prompts.html) | V+ C~ T~ E~ | Loops a sequence of prompts while a customer or agent is on hold or in queue. |
| [Play prompt](https://docs.aws.amazon.com/connect/latest/adminguide/play.html) | V+ C+ T? E? | Plays an interruptible audio prompt, delivers a text-to-speech message, or delivers a chat response. |
| [Resume contact](https://docs.aws.amazon.com/connect/latest/adminguide/resume-contact.html) | V~ C~ T+ E~ | Resumes a contact from a paused state. |
| [Return (from module)](https://docs.aws.amazon.com/connect/latest/adminguide/return-module.html) | V+ C+ T+ E+ | Exits the flow module after it has run successfully. |
| [Send message](https://docs.aws.amazon.com/connect/latest/adminguide/send-message.html) | ? | Sends a message to your customer based on a template or custom message you specify. |
| [Set callback number](https://docs.aws.amazon.com/connect/latest/adminguide/set-callback-number.html) | V+ C~ T~ E~ | Sets a callback number. |
| [Set contact attributes](https://docs.aws.amazon.com/connect/latest/adminguide/set-contact-attributes.html) | V+ C+ T+ E+ | Stores key-value pairs as contact attributes. |
| [Set customer queue flow](https://docs.aws.amazon.com/connect/latest/adminguide/set-customer-queue-flow.html) | V+ C+ T+ E+ | Specifies the flow to invoke when a customer is transferred to a queue. |
| [Set disconnect flow](https://docs.aws.amazon.com/connect/latest/adminguide/set-disconnect-flow.html) | V+ C+ T+ E+ | Sets the flow to run after a disconnect event. |
| [Set event flow](https://docs.aws.amazon.com/connect/latest/adminguide/set-event-flow.html) | ? | Specifies which flow to run during a contact event. |
| [Set hold flow](https://docs.aws.amazon.com/connect/latest/adminguide/set-hold-flow.html) | V+ C~ T~ E~ | Links from one flow type to another. |
| [Set logging behavior](https://docs.aws.amazon.com/connect/latest/adminguide/set-logging-behavior.html) | V+ C+ T+ E+ | Enables flow logs so you can track events as contacts interact with flows. |
| [Set recording and analytics behavior](https://docs.aws.amazon.com/connect/latest/adminguide/set-recording-behavior.html) | V+ C+ T~ E~ | Sets options for recording conversations. |
| [Set recording, analytics and processing behavior](https://docs.aws.amazon.com/connect/latest/adminguide/set-recording-analytics-processing-behavior.html) | V+ C+ T+ E+ | Sets options to configure recording behavior for agent and customer, enable automated interaction, enable screen recording, set analytics behavior for contacts, and set custom processing behavior. |
| [Set routing criteria](https://docs.aws.amazon.com/connect/latest/adminguide/set-routing-criteria.html) | V+ C+ T+ E+ | Sets routing criteria on contacts of any channel, such as Voice, Chat, and Task, to define how the contact should be routed within its queue. A routing criteria is a sequence of one or more routing steps. |
| [Set Touchtone Buffer Behavior](https://docs.aws.amazon.com/connect/latest/adminguide/set-touchtone-buffer-behavior.html) | ? | Controls touchtone buffering behavior, enabling customers to type ahead during IVR interactions. |
| [Set voice](https://docs.aws.amazon.com/connect/latest/adminguide/set-voice.html) | V+ C? T? E? | Sets the text-to-speech (TTS) language and voice to be used in the flow. |
| [Set Voice ID](https://docs.aws.amazon.com/connect/latest/adminguide/set-voice-id.html) | V+ C~ T~ E~ | When the call is connected to a flow, sends audio to Connect Customer Voice ID to verify the caller's identity and match against fraudsters on a watch list. |
| [Set whisper flow](https://docs.aws.amazon.com/connect/latest/adminguide/set-whisper-flow.html) | V+ C+ T+ E+ | Overrides the default whisper by linking to a whisper flow. |
| [Set working queue](https://docs.aws.amazon.com/connect/latest/adminguide/set-working-queue.html) | V+ C+ T+ E+ | Specifies the queue to be used when **Transfer to queue** is invoked. |
| [Show view](https://docs.aws.amazon.com/connect/latest/adminguide/show-view-block.html) | V~ C+ T~ E+ | Configures UI based workflows that you can surface to users in front end applications. |
| [Start media streaming](https://docs.aws.amazon.com/connect/latest/adminguide/start-media-streaming.html) | V+ C~ T~ E~ | Starts capturing customer audio for a contact. |
| [Stop media streaming](https://docs.aws.amazon.com/connect/latest/adminguide/stop-media-streaming.html) | V+ C~ T~ E~ | Stops capturing customer audio after it is started with a **Start media streaming** block. |
| [Store customer input](https://docs.aws.amazon.com/connect/latest/adminguide/store-customer-input.html) | V+ C~ T~ E~ | Stores numerical input to a contact attribute. |
| [Transfer to agent (beta)](https://docs.aws.amazon.com/connect/latest/adminguide/transfer-to-agent-block.html) | V+ C~ T~ E~ | Transfers the customer to an agent. |
| [Transfer to flow](https://docs.aws.amazon.com/connect/latest/adminguide/transfer-to-flow.html) | V+ C+ T+ E+ | Transfers the customer to another flow. |
| [Transfer to phone number](https://docs.aws.amazon.com/connect/latest/adminguide/transfer-to-phone-number.html) | V+ C~ T~ E~ | Transfers the customer to a phone number external to your instance. |
| [Transfer to queue](https://docs.aws.amazon.com/connect/latest/adminguide/transfer-to-queue.html) | V+ C+ T+ E+ | In most flows, this block ends the current flow and places the customer in queue. When used in a customer queue flow, this block transfers a contact already in a queue to another queue. |
| [Wait](https://docs.aws.amazon.com/connect/latest/adminguide/wait.html) | V~ C+ T+ E+ | Pauses the flow. |
