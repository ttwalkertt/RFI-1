# Framework Task Operating Model

This document defines the project-wide expectations for Codex. These rules reduce boilerplate in individual task tickets.

## 1. Architectural Milestones
- The unit of work is an architectural milestone, not an implementation milestone.
- Task tickets define objectives, boundaries, invariants, and acceptance criteria.
- Internal implementation decisions are delegated to Codex unless explicitly constrained.

## 2. Scope Discipline
- Respect architectural boundaries.
- Do not expand scope simply because an adjacent improvement is attractive.
- Record opportunities discovered during implementation unless required for task completion.

## 3. Verification Before Completion
A task is not complete until it includes:
- implementation evidence;
- validation evidence;
- review artifacts;
- documented limitations;
- reproducible results.

If evidence cannot be produced, report the task as blocked or partially complete.

## 4. Architectural Status Summary (Required)
Every completed milestone shall conclude with an Architectural Status Summary.

Include:
- major functional subsystems;
- responsibility of each subsystem;
- current status (Complete, Usable with Limitations, Provisional, Blocked, Not Started);
- architectural changes introduced;
- important limitations and technical debt;
- next architectural milestone.

The goal is to refresh the human architect's mental model, not summarize source-code changes.

## 5. Review Philosophy
Review packages serve:
1. Future implementation agents.
2. Independent reviewers.
3. The human architect.

The third audience needs architectural understanding rather than implementation detail.

## 6. Implementation Prompt Philosophy
Implementation prompts should remain concise.

Project-wide operating rules belong here. Task tickets should focus on:
- architectural objective;
- task-specific constraints;
- acceptance criteria;
- required evidence.

## 7. Guiding Principles
- Architectural boundaries are more important than implementation details.
- Immutable evidence, canonical knowledge, retrieval, intelligence, and user workflows remain separate layers.
- Frontier models consume governed knowledge through repository-owned retrieval contracts.
- Whatever a model can retrieve should also be inspectable by the operator.
- Real-world behavior validates architecture better than synthetic assumptions.
- Honest blocking is preferable to unsupported claims of completion.
