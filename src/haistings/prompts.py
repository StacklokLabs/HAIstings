# This is the system message we give to the Assistant to explain the task.
ASSISTANT_PROMPT = """"You are a Software Security assistant. Your goal is to
help infrastructure engineerings to secure their deployments. You are
tasked with prioritizing what software to update first. You have a list of
container image references with their list of vulnerabilities. You also have a list of known
vulnerabilities and their severity. Your goal is to write a concise summary
that's actionable and informative.

Note that your chatacter is based on a fictional persona that resembles Arthur
Hastings, a character from the Agatha Christie's Poirot series. You are
intelligent, meticulous, and have a keen eye for detail. You are also
methodical and systematic in your approach. You are not afraid to ask
questions and seek clarification when needed. You are also a good listener
and have a knack for understanding complex technical concepts.

Start the report with a Hasting's sounding introduction. Then, provide a
summary of the vulnerabilities in the container images.

ONLY provide the information that is relevant to the task at hand. Do not
provide extraneous information. Your summary should be clear, concise, and
easy to understand. Make sure to prioritize the software components based on
the severity of the vulnerabilities, the impact on the infrastructure, and
the reachability of the vulnerability.

Aggregate image references of different tags or hashes into the same
container image and thus, into the same priority.

End the report with a closing statement that also sounds like something
Hastings would say.

Let the format of the report be markdown and look as follows:

# HAIsting's Security Report

## Introduction

<Introduction goes here>

## Summary

<Summary of the vulnerabilities goes here>

## Conclusion
<Closing statement goes here>
"""

# This is the kickoff question the chatbot sends to the assistant.
# It kicks off the conversation and provides the necessary context to start the task.
# NOTE: This requires the usage of the following placeholders:
# - {question} - The question the user asks the agent
# - {context} - The list of images and their vulnerabilities
# - {usercontext} - Extra context the user thinks is important
# - {deployment_file_context} - If set, it'll contain additions to the prompt that are
#                               specific to the deployment files. This is optional.
# It has to be passed into a formatter.
KICKOFF_USER_QUESTION = """{question}

{deployment_file_context}

Do the prioritization based on the following information which is a list of vulnerabilities
found in a scan with the relevant container images:

{context}


The system administrator also provided the following context which is
important for the prioritization: {usercontext}
"""

# This is additional context that the system administrator provides to the assistant.
# This is to help the assistant understand the context of the deployment.
# NOTE: This requires the {ingested_repo} placeholder to be filled with the
#       list of ingested files.
DEPLOYMENT_FILE_CONTEXT = """The team is using the following files to deploy the given infrastructure:

{ingested_repo}

This is important context for the prioritization. Use file name references as part of the report
to help the user understand the context better.
"""


# In case the chatbot picks up the conversation where it left off
# (which is done via checkpoint saving), it will ask this question to continue the conversation.
CONTINUE_FROM_CHECKPOINT = (
    "Given all the context available, especially the extra "
    "context provided by the system administrator, "
    "Can you generate another prioritized report?"
)


# This helps categorize the user's response and guide the conversation
# based on the user's input.
# The idea is to understand if the user wants to provide more information
# stop the conversation, or is unsure.
#
# NOTE: This requires the %s placeholder to be filled with the user's response.
#       We're not using named placeholders here to keep the code simple and not
#       clash with the expected JSON output.
USER_RESPONSE_CATEGORIZATION = """
Based on the following text that the user typed: \"%s\"
Does the user want to provide more information or stop the conversation?

Before this, the user was given a priority list of components and their vulnerabilities,
and this tool is meant to help you prioritize.

If the user typed text such as \"no\" \"exit\", or an empty string, this would indicate that 
the user wants to end the conversation.

If the user asks a question or indicates they're not sure, then it means
they're unsure. Note that this is explicitly only when they ask
questions about this tool, and not a software component.

If the user talks about some infrastructure component, changes in priorization
or provides more context, then it means they want to provide more information
and want to continue the conversation. The user might also want to stop
showing a component from the list, that would also mean they want to
continue the conversation. They might also want more information about
types of components and how to upgrade them.

Output the answer with a JSON format that looks as follows:
{
    "continue_conversation": "yes" | "no" | "unsure",
    "explanation": "<why the text was interpreted the way it was>"
}

ONLY answer with that JSON and don't provide any other information.
DO NOT put the JSON within markdown tags or any other formatting.

Format the explanation by talking directly to the user. e.g. "you've asked for more information, ..."
"""

# This is the message the chatbot will send to the assistant when the user
# wants to provide more information.
# This requires the {extra} placeholder to be filled with the user's input.
PROVIDE_EXTRA_CONTEXT = """
Here's extra context to help with the prioritization by the system administrator:

{extra}

Given this new information, can you provide a better report?
"""
