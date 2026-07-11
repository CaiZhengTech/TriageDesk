## What

Closes #

## Self-review checklist

- [ ] Every changed line traces to the issue's acceptance criteria (no drive-by edits)
- [ ] Tests written first and failing before implementation (TDD)
- [ ] `ruff check .` and `pytest` green locally
- [ ] No secrets, connection strings, or data files staged (`git diff --staged` checked)
- [ ] Error paths covered: what happens when the LLM call fails / validates wrong / costs too much?
- [ ] Spans/trace output eyeballed if this touches the pipeline
- [ ] Issue acceptance criteria checked off on the issue itself
