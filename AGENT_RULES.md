# AGENT RULES

1. **Inspect before acting.** List files and read relevant code before proposing anything.
2. **Never invent results.** Only report command output you actually ran and saw. If you did not run something, say "not run".
3. **Never read aloud, print, log or echo secret values.** You may say whether a variable or file EXISTS, never its value. Do not open any `.env` or `.env.local` file's contents.
4. **The folder targets/ is a READ-ONLY analysis target.** Never edit, create, delete, format, or run code inside `targets/`. Never run its `main.py`, notebooks or scripts.
5. **Do not install packages, create cloud resources, call NVIDIA/Pinecone APIs, push to Git, or delete anything without explicit approval in chat.**
6. **Stay inside the current phase.** If a task belongs to a later phase, list it under "Next phase" instead of doing it.
7. **Stop and ask when something is ambiguous, blocked, or would need a secret.**
8. **Prefer focused edits over rewrites; list changed files at the end of every phase.**
