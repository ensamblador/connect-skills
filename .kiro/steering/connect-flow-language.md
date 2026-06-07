---
inclusion: manual
last_refreshed: 2026-05-26
action_count: 56
source_urls:
  - https://docs.aws.amazon.com/connect/latest/devguide/flow-language-actions.html
  - https://docs.aws.amazon.com/connect/latest/devguide/contact-actions.html
  - https://docs.aws.amazon.com/connect/latest/devguide/flow-control-actions.html
  - https://docs.aws.amazon.com/connect/latest/devguide/interactions.html
  - https://docs.aws.amazon.com/connect/latest/devguide/participant-actions.html
content_checksum: sha256:310c45593e013075
---

# Connect Flow language reference

Distilled from the Connect Flow language API reference. Two parts:
the **grammar** (how every Action is shaped) and the **action catalog**
(every concrete Action type, its category, and a one-line description).

Refresh with ``uv run python .kiro/hooks/scripts/refresh_connect_flow_language.py``.

**Activation:** opt-in. Reference from chat with `#connect-flow-language`
when generating, validating, or reviewing flow JSON. Pair with
`#connect-blocks` when you need both the UI block names and the
Flow language Action types.

**Freshness rule (for the agent):** before relying on this reference,
compare the `last_refreshed` date in the front matter with today's
date. If the file is older than 7 days, run
``uv run python .kiro/hooks/scripts/refresh_connect_flow_language.py`` to refresh it
before answering. Always refresh when the user explicitly asks for it.

For depth on any Action (full Parameters object, errors, examples),
follow the action name link. The
[Connect Flow language overview](https://docs.aws.amazon.com/connect/latest/devguide/flow-language.html)
and the
[example flow](https://docs.aws.amazon.com/connect/latest/devguide/flow-language-example.html)
are the authoritative entry points.

## Action grammar

Every Action in a flow has four fields: `Identifier`, `Type`,
`Parameters`, `Transitions`.

### Identifier

A string unique among all Actions in the same flow. Up to 50 characters.
Can include unicode and spaces. May be opaque or human-friendly.

**Forbidden characters:** ``%``, ``:``, ``(``, ``\``, ``/``, ``)``,
``=``, ``$``, ``,``, ``;``, ``[``, ``]``, ``{``, ``}``.

**Forbidden values:** ``__proto__``, ``constructor``, ``__defineGetter__``,
``__defineSetter__``, ``toString``, ``hasOwnProperty``, ``isPrototypeOf``,
``propertyIsEnumerable``, ``toLocaleString``, ``valueOf``.

### Type

The Action type, drawn from the Action catalog below
(``InvokeLambdaFunction``, ``Loop``, ``MessageParticipant``, etc.).

### Parameters

Per-Action object whose shape is defined on the individual Action's
reference page. Differs for every Action — follow the link in the
catalog to get the exact schema.

### Transitions

Defines how to leave this Action. Three sub-fields:

- **NextAction** *(string)* — Identifier of the Action to run if no
  error or condition preempts. For terminal Actions (e.g.
  `EndFlowExecution`), set Transitions to an empty object.
- **Errors** *(list)* — each entry: ``{ "ErrorType": "<error>", "NextAction": "<Identifier>" }``.
  The list of valid ``ErrorType`` values is per-Action.
- **Conditions** *(list, ordered)* — each entry:
  ``{ "NextAction": "<Identifier>", "Condition": { "Operator": ..., "Operands": [...] } }``.
  Evaluated in order; the first to evaluate true wins.

### The Condition object

A `Condition` has two required fields: `Operator` and `Operands`.

| Operator | Description | Operand type | Operand count |
| --- | --- | --- | --- |
| Equals | true if the string exactly equals the result. | String | One |
| TextStartsWith | true if the result, as text, begins with the string. | String | One |
| TextEndsWith | true if the result, as text, ends with the string. | String | One |
| TextContains | true if the result, as text, contains the string at least once. | String | One |
| NumberGreaterThan | true if the result, as a number, is larger than the string. False if either is not numeric. | String | One |
| NumberGreaterOrEqualTo | true if the result, as a number, is ≥ the string. False if either is not numeric. | String | One |
| NumberLessThan | true if the result, as a number, is smaller than the string. False if either is not numeric. | String | One |
| NumberLessOrEqualTo | true if the result, as a number, is ≤ the string. False if either is not numeric. | String | One |

**Nesting limits:** Conditions may not be nested more than 5 deep,
and a single Condition may not contain more than 50 sub-Conditions
total (regardless of nesting depth).

**Example Condition** — true if the result starts with ``ABC``:

```json
{
    "Operator": "TextStartsWith",
    "Operands": ["ABC"]
}
```

## Server-side deploy gaps (validate_flow_json does NOT catch these)

`validate_flow_json` checks structure but is looser than the
`CreateContactFlow` / `CreateContactFlowModule` server schema. Real
400s seen in practice that the local validator passes:

- **`UpdateFlowLoggingBehavior` must NOT carry an `Errors` array.**
  Declare only `Transitions.NextAction`. Adding
  `Errors: [{ErrorType: NoMatchingError, ...}]` fails create with
  `Invalid Action error. Error: NoMatchingError, Path: Actions[N]`.
- **`EndFlowModuleExecution` takes empty `Parameters: {}` on create.**
  The flow designer *exports* a `Result` (and sometimes `ResultData`)
  field on the Return block, but `create-contact-flow-module` rejects
  `Result` / `ResultData` with `Invalid Action property name`. Named
  multi-branch returns authored from scratch via the API collapse to
  a single empty-param `EndFlowModuleExecution`; the named branches
  live only in the top-level `Settings.Transitions` list.
- **Flow modules require a top-level `Settings` block** with
  `InputParameters`, `OutputParameters`, and `Transitions` (the named
  return branches). Regular flows have no `Settings`. Omitting it on a
  module fails with `JSON field is missing or null for field name:
  settings`.
- **Modules cannot read `$.Lex.*`, `$.External.*`, Customer-Profiles,
  or Connect-AI-agent attributes** of the invoking flow. Copy those
  into plain contact attributes in the parent **before** invoking the
  module, and have the module consume the contact attributes.
- When a create fails with `<complex value>`, re-run with
  `--cli-error-format json` to see the actual `problems` / `Problems`
  array with the offending `Path`.

## Action catalog

| Action | Category | Description |
| --- | --- | --- |
| [CompleteOutboundCall](https://docs.aws.amazon.com/connect/latest/devguide/contact-actions-completeoutboundcall.html) | Contact | When a flow is run before an outbound call is made as part of an outbound contact, this action calls the outbound destination. If this action is not used, the first participant action implicitly completes the outbound call. |
| [CreateCase](https://docs.aws.amazon.com/connect/latest/devguide/createcase.html) | Contact | Creates a new case using an existing case template. Templates come with predefined fields, some of which are required and will appear in a side panel when you start. You can review and fill in the required fields, and optionally update any other available fields based on your needs. These fields are set up in your instance ahead of time. You can also choose to link a contact to the new case if needed. |
| [CreateTask](https://docs.aws.amazon.com/connect/latest/devguide/createtask.html) | Contact | Creates a new task to run an assigned flow. |
| [CreateWisdomSession](https://docs.aws.amazon.com/connect/latest/devguide/createwisdomsession.html) | Contact | Associates a Wisdom domain to a contact that is being executed in a Flow to enable real-time recommendations on the current contact. |
| [DequeueContactAndTransferToQueue](https://docs.aws.amazon.com/connect/latest/devguide/contact-actions-dequeuecontactandtransfertoqueue.html) | Contact | This action is a combination of a "Dequeue" action and a "TransferContactToQueue" action. This means that a contact in a queue is removed from the queue, a new contact segment is created with the existing contact as its previous contact, and the new contact is placed into the specified queue (referred to as "Queue-to-queue transfer"). If this contact has not been queued, is actively being joined to an agent, or has been routed to an agent, this action fails. |
| [EndFlowModuleExecution](https://docs.aws.amazon.com/connect/latest/devguide/endflowmoduleexecution.html) | Contact | Ends the current module execution without disconnecting the contact. |
| [GetCase](https://docs.aws.amazon.com/connect/latest/devguide/getcase.html) | Contact | Searches all existing cases with the provided customer ID. Add request fields to filter by case fields. Specify the case fields to be returned in the response to persist in the context. |
| [InvokeFlowModule](https://docs.aws.amazon.com/connect/latest/devguide/flow-language-actions-invoke-flow-module.html) | Contact | Invokes a flow module. *Flow modules* are reusable sections of a flow. You use them to extract repeatable logic across your flows, and create common functions. For more information about flow modules, see [Flow modules for reusable functions](https://docs.aws.amazon.com/connect/latest/adminguide/contact-flow-modules.html), in the *Connect Customer Administrator Guide*. |
| [ResumeContact](https://docs.aws.amazon.com/connect/latest/devguide/contact-actions-updatecontactresumecontact.html) | Contact | Resumes a contact from a paused state. |
| [StartOutboundChatContact](https://docs.aws.amazon.com/connect/latest/devguide/contact-actions-startoutboundchatcontact.html) | Contact | Initiate an outbound chat contact to a customer. Only SMS chats are supported. For more information, see the [StartOutboundChatContact](https://docs.aws.amazon.com/connect/latest/APIReference/API_StartOutboundChatContact.html) in the *Connect Customer API Reference*. |
| [TagContact](https://docs.aws.amazon.com/connect/latest/devguide/contact-actions-tagcontact.html) | Contact | Sets a collection of tag to the current contact. With this type of operation, either all tags are set or none are set. |
| [TransferContactToAgent](https://docs.aws.amazon.com/connect/latest/devguide/contact-actions-transfercontacttoagent.html) | Contact | Ends the current flow and transfers the customer to an agent. If the agent is already with someone else, the contact is disconnected. Transfer contact to agent works only for voice interactions. |
| [TransferContactToQueue](https://docs.aws.amazon.com/connect/latest/devguide/contact-actions-transfercontacttoqueue.html) | Contact | This action places a contact that is not already in a queue into the contact's TargetQueue. If the contact has already been put into a queue (meaning that it is currently being routed to an agent, being joined to an agent, or is connected to an agent), the action fails. |
| [UnTagContact](https://docs.aws.amazon.com/connect/latest/devguide/contact-actions-untagcontact.html) | Contact | Removes a collection of tags on the current contact. With this type of operation, either all tags are set or none are set. |
| [UpdateCase](https://docs.aws.amazon.com/connect/latest/devguide/updatecase.html) | Contact | Updates an existing case by providing the case’s id and the fields that should be updated. |
| [UpdateContactAttributes](https://docs.aws.amazon.com/connect/latest/devguide/contact-actions-updatecontactattributes.html) | Contact | Sets a collection of contact attributes on either the current contact or the related contact. With this type of operation, either all attributes are set or none are set. |
| [UpdateContactCallbackNumber](https://docs.aws.amazon.com/connect/latest/devguide/contact-actions-updatecontactcallbacknumber.html) | Contact | Updates the contact callback number, which is the number used by the CreateCallbackContact action. This value defaults to the customer participant caller ID if this action is never used. |
| [UpdateContactData](https://docs.aws.amazon.com/connect/latest/devguide/contact-actions-updatecontactdata.html) | Contact | Sets a collection of connect defined attributes on specified contact. With this type of operation, either all attributes are set or none are set. |
| [UpdateContactEventHooks](https://docs.aws.amazon.com/connect/latest/devguide/contact-actions-updatecontacteventhooks.html) | Contact | Sets one or more contact event hooks, which are flows associated with contact events, such as customer whisper or agent hold. For more information, see [Contact records data model](https://docs.aws.amazon.com/connect/latest/adminguide/ctr-data-model.html). The following event hooks are valid: + AgentHold + AgentWhisper + CustomerHold + CustomerQueue + CustomerRemaining + CustomerWhisper + DefaultAgentUI + DisconnectAgentUI + PauseContact + ResumeContact |
| [UpdateContactMediaProcessing](https://docs.aws.amazon.com/connect/latest/devguide/contact-actions-updatecontactmediaprocessing.html) | Contact | Allows customers to configure their own Lambda processor, which will be applied to in-flight messages. |
| [UpdateContactMediaStreamingBehavior](https://docs.aws.amazon.com/connect/latest/devguide/contact-actions-updatecontactmediastreamingbehavior.html) | Contact | Enables or disables contact media streaming for a set of participants. |
| [UpdateContactRecordingAndAnalyticsBehavior](https://docs.aws.amazon.com/connect/latest/devguide/contact-actions-updatecontactrecordingandanalyticsbehavior.html) | Contact | Sets contact recording behavior, including analysis behavior and which participants of the contact to record. |
| [UpdateContactRecordingBehavior](https://docs.aws.amazon.com/connect/latest/devguide/contact-actions-updatecontactrecordingbehavior.html) | Contact | Sets contact recording behavior, including analysis behavior and which participants of the contact to record. |
| [UpdateContactRoutingBehavior](https://docs.aws.amazon.com/connect/latest/devguide/contact-actions-updatecontactroutingbehavior.html) | Contact | Updates the contact's routing details. This can move the contact forward or backward in queue, or specify a queue priority. |
| [UpdateContactTargetQueue](https://docs.aws.amazon.com/connect/latest/devguide/contact-actions-updatecontacttargetqueue.html) | Contact | Sets the contact's TargetQueue. This is the queue is used by all other instructions that check a queue implicitly, and for TransferContactToQueue. |
| [UpdateContactTextToSpeechVoice](https://docs.aws.amazon.com/connect/latest/devguide/contact-actions-updatecontacttexttospeechvoice.html) | Contact | Updates the Amazon Polly voice used by text-to-speech for voice contacts (message with text-to-speech, or Amazon Lex bots). This defaults to Joanna if this action is never run. |
| [UpdatePreviousContactParticipantState](https://docs.aws.amazon.com/connect/latest/devguide/contact-actions-updatepreviouscontactparticipantstate.html) | Contact | This action is primarily used to prevent previous participants on the contact from observing the contact. Common use cases are disconnecting the agent that initiates a transfer when they transfer a contact to a secure destination, or putting the agent on hold when transferring to a quick connect that securely gathers customer input such as credit card numbers. |
| [CheckHoursOfOperation](https://docs.aws.amazon.com/connect/latest/devguide/flow-control-actions-checkhoursofoperation.html) | Flow control | Returns whether the specified hours of operation object (or the hours of operation object associated with the current queue if no hours of operation is referenced) is in hours or out of hours as its result, allowing comparisons against it. |
| [CheckMetricData](https://docs.aws.amazon.com/connect/latest/devguide/flow-control-actions-checkmetricdata.html) | Flow control | A shortcut single action to avoid using GetMetricData and Compare for a set of simple metrics. This action loads the specified metric data for the specified queue, and allows comparisons to the loaded value. For example, it loads number of contacts in queue, age of oldest contact in queue, number of agents staffed on the queue, number of agents available on the queue, or number of agents online on the queue. |
| [CheckOutboundCallStatus](https://docs.aws.amazon.com/connect/latest/devguide/flow-control-actions-checkoutboundcallstatus.html) | Flow control | Engages with the output provided by an answering machine, and provides branches to route the contact accordingly. |
| [CheckVoiceId](https://docs.aws.amazon.com/connect/latest/devguide/flow-control-actions-checkvoiceid.html) | Flow control | Checks the enrollment status, voice authentication or fraud detection results of the voice analysis returned by Voice ID. |
| [Compare](https://docs.aws.amazon.com/connect/latest/devguide/flow-control-actions-compare.html) | Flow control | Allows comparisons against the specified value. |
| [DistributeByPercentage](https://docs.aws.amazon.com/connect/latest/devguide/flow-control-actions-distributebypercentage.html) | Flow control | Returns a random number between 1 and 100 (inclusive) as its result, allowing comparisons against it. |
| [EndFlowExecution](https://docs.aws.amazon.com/connect/latest/devguide/flow-control-actions-endflowexecution.html) | Flow control | Finishes flow, but does not explicitly disconnect the participant. The participant may be disconnected by contact logic after this. For example, if a flow ends before the contact is put into queue, ending the flow results in the contact being ended. |
| [GetMetricData](https://docs.aws.amazon.com/connect/latest/devguide/flow-control-actions-getmetricdata.html) | Flow control | Loads real time queue metrics for the queue specified by queue ID, agent ID (for agent queues), or the target queue, and makes them available on the flow run data. May be extended in the future to allow getting historical metric data in addition to current metric data, and to getting agent metrics in addition to queue metrics. |
| [Loop](https://docs.aws.amazon.com/connect/latest/devguide/flow-control-actions-loop.html) | Flow control | When the same action (the same Action Identifier) is run multiple times, this block returns a result of "NotDone" a number of times equal to the specified loop count, then "Done" once, then reset. |
| [StartVoiceIdStream](https://docs.aws.amazon.com/connect/latest/devguide/flow-control-actions-startvoiceidstream.html) | Flow control | Sends audio to Connect Customer Voice ID to verify the caller's identity and match against fraudsters in watchlist, as soon as the call is connected to a flow. |
| [TransferToFlow](https://docs.aws.amazon.com/connect/latest/devguide/flow-control-actions-transfertoflow.html) | Flow control | Execution jumps to a different flow, and continues running at that flow's beginning. |
| [UpdateFlowAttributes](https://docs.aws.amazon.com/connect/latest/devguide/flow-control-actions-updateflowattributes.html) | Flow control | Sets a collection of attributes on the current flow. These attributes are not carried over to the subsequent flows. With this type of operation, either all attributes are set or none are set. |
| [UpdateFlowLoggingBehavior](https://docs.aws.amazon.com/connect/latest/devguide/flow-control-actions-updateflowloggingbehavior.html) | Flow control | Enables or disables flow logging. If this is a flow, this same behavior remains unless it is overridden for the rest of the contact segment. It is also automatically inherited by new segments in the chain. |
| [UpdateRoutingCriteria](https://docs.aws.amazon.com/connect/latest/devguide/flow-control-actions-updateroutingcriteria.html) | Flow control | Sets the routing criteria for the contact. |
| [Wait](https://docs.aws.amazon.com/connect/latest/devguide/flow-control-actions-wait.html) | Flow control | Pauses the flow for a specified duration, or until a specified event happens, whichever happens first. |
| [AssociateContactToCustomerProfile](https://docs.aws.amazon.com/connect/latest/devguide/interactions-associatecontacttocustomerprofile.html) | Interactions | Associate a contact to a customer profile. Customer Profiles must be enabled for your Connect Customer instance. |
| [CreateCallbackContact](https://docs.aws.amazon.com/connect/latest/devguide/interactions-createcallbackcontact.html) | Interactions | Creates a new callback contact. If no customer number is specified, and this is run in context of a contact, the contact's CustomerCallbackNumber is used as the customer number. If you specify a ContactFlowId, then InitialCallDelaySeconds parameter is ignored. |
| [CreateCustomerProfile](https://docs.aws.amazon.com/connect/latest/devguide/interactions-createcustomerprofile.html) | Interactions | Create a customer profile. Customer Profiles must be enabled for your Connect Customer instance. |
| [GetCalculatedAttributesForCustomerProfile](https://docs.aws.amazon.com/connect/latest/devguide/interactions-getcalculatedattributesforcustomerprofile.html) | Interactions | Retrieve calculated attributes for a customer profile. Customer Profiles must be enabled for your Connect Customer instance. |
| [GetCustomerProfile](https://docs.aws.amazon.com/connect/latest/devguide/interactions-getcustomerprofile.html) | Interactions | Retrieve a customer profile based any search identifier, up to five total. Customer Profiles must be enabled for your Connect Customer instance. |
| [GetCustomerProfileObject](https://docs.aws.amazon.com/connect/latest/devguide/interactions-getcustomerprofileobject.html) | Interactions | Retrieve a customer profile object of the desired type, based on recency or any search identifier. Customer Profiles must be enabled for your Connect Customer instance. |
| [InvokeLambdaFunction](https://docs.aws.amazon.com/connect/latest/devguide/interactions-invokelambdafunction.html) | Interactions | Invokes an AWS Lambda function with a collection of optional parameters. This AWS Lambda function is also given a copy of the flow run data if there is an associated contact with the flow. |
| [UpdateCustomerProfile](https://docs.aws.amazon.com/connect/latest/devguide/interactions-updatecustomerprofile.html) | Interactions | Update a customer profile that was previously created or retrieved in the flow. Customer Profiles must be enabled for your Connect Customer instance. |
| [ConnectParticipantWithLexBot](https://docs.aws.amazon.com/connect/latest/devguide/participant-actions-connectparticipantwithlexbot.html) | Participant | Connects the participant with the specified Amazon Lex bot. When the interaction is over, the Intent and Slots of the bot are available to the flow during its run. |
| [DisconnectParticipant](https://docs.aws.amazon.com/connect/latest/devguide/participant-actions-disconnectparticipant.html) | Participant | Disconnects the participant from the contact and stops this flow from running. |
| [GetParticipantInput](https://docs.aws.amazon.com/connect/latest/devguide/participant-actions-getparticipantinput.html) | Participant | Gathers customer input (a DTMF collection for voice contacts, or an entered string for other channels). There are many optional behaviors after gathering this: encryption, validation, storing to a "LastParticipantInput" section on the flow run data, specifying a custom DTMF terminator for voice contacts and so on. Details are in the parameter object section. |
| [MessageParticipant](https://docs.aws.amazon.com/connect/latest/devguide/participant-actions-messageparticipant.html) | Participant | Sends a message to the participant. This is an audio prompt or text-to-speech for voice contacts, or a text message for other channels. |
| [MessageParticipantIteratively](https://docs.aws.amazon.com/connect/latest/devguide/participant-actions-messageparticipantiteratively.html) | Participant | Loops a sequence of prompts while a customer or agent is on hold or in queue. This block can be configured with an interruption timeout when in a Queue flow that interrupts the message loop to run other flow logic. The message loop can include entries for both Text and Prompts. |
| [ShowView](https://docs.aws.amazon.com/connect/latest/devguide/participant-actions-showview.html) | Participant | Initiates a UI-based workflow that can be surfaced to users of front end applications. This action can be used to create [step-by-step guides ](https://docs.aws.amazon.com/connect/latest/adminguide/step-by-step-guided-experiences.html) for agents who are using the Connect Customer agent workspace. |
