---
name: task-finish-audio
description: Use when all requested work is complete and you are about to send the final response. Run the completion-audio script from the global agents skills folder so the user hears a finish notification.
---

# Task Finish Audio

Use this skill only after the task is fully complete.

## Workflow

1. Confirm implementation and validation are finished.
2. Run `bash /home/sherzod/.agents/skills/task-finish-audio/scripts/play-completion-audio.sh`.
3. Send the final response.

## Rules

- Do not run the sound before the task is complete.
- Run the script once per finished task.
- If playback fails, mention that in the final response.
