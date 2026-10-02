# Choosing the workspace

## Chat

Use Chat for framing a problem, quick explanations, writing, review, and decisions that do not require a persistent working tree. Move durable conclusions into repository documentation.

## ChatGPT Work / Projects

Use Work or Projects to group related chats, files, and longer-running coordination. It is an organizing surface, not the only backup; put the authoritative deliverable and state in a repository or durable storage.

## Codex

Use Codex for repository changes, tests, diffs, structured artifacts, and checkpointed workflows. Start with the smallest relevant files and use project-scoped skills when their exact workflow applies.

## Web and research

Use web research when facts may have changed, sources are requested, or the claim is specialized. Prefer primary sources, cite durable evidence, and write the conclusion plus source into `docs/decisions.md` or an experiment record. Do not repeatedly research a settled decision without a changed premise.

## GitHub and Drive

Use a Git remote as the canonical versioned copy for code and text. Push stable blocks. Use Drive (or another approved secondary store) only for exported milestones, large non-Git artifacts, or a second recovery copy. Verify authentication and access before claiming either integration is active; do not put secrets, private keys, or sensitive datasets in public remotes or unencrypted archives.

## Skills by domain

Create a domain skill only for repeated, non-obvious decisions: regulated-data handling, lab protocol, build/deploy rules, data contracts, or evaluation methodology. Keep its name/description precise, its instructions short, and heavier tables/examples in `references/`. Do not duplicate `AGENTS.md` or general coding advice.
