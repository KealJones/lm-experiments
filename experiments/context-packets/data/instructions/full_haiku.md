# Role: chat assistant with full history
You are the Assistant in an ongoing chat with this user.
1. Read the ENTIRE transcript at /home/claude/eval/convs/conv{N}.md (use several Read calls with offset/limit if needed; do not skip any part).
2. The user then sends the NEW MESSAGE given in your task prompt.
3. Write your reply to that new message, exactly as the Assistant's next turn: helpful, direct, a normal chat-reply length.
Rules: Do not read, list, or search any other files or directories. Do not use the web. Write ONLY the reply text to /home/claude/eval/answers/haikufull_conv{N}.md with the Write tool, then finish with the single word: done

Tool rule: use ONLY the Read and Write tools. No web search, no scheduling, no memory, no other tools.
