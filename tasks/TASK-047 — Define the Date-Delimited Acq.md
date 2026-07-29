TASK-047 — Define the Date-Delimited Acquisition Contract

Status

Done

Objective

Define the canonical contract used by all future repository acquisition implementations for retrieving artifacts within a date-delimited interval.

This task establishes the architectural boundary between the application, acquisition implementations, and the repository. It intentionally specifies observable behavior and ownership while leaving implementation strategy to individual acquisition implementations. The contract shall remain stable as additional artifact families are introduced, allowing independent acquisition implementations to evolve without requiring changes to application or repository integration.

This task specifies observable behavior and ownership, not a required class hierarchy, interface, or naming convention. Implementations shall follow existing repository architectural patterns.

No production artifact retriever shall be implemented in this task.

⸻

Background

The repository is evolving from single-artifact acquisition toward interval-based acquisition for artifact families such as earnings calls and press releases.

Future tasks will independently implement production retrievers for those artifact families. Those implementations shall share a common acquisition contract but are not expected to share internal implementation.

This task establishes that contract before production retrievers are introduced.

⸻

Scope

Define and integrate the shared acquisition request and result contract used by all artifact-specific acquisition implementations.

Implement the supporting repository and application integration required to consume the contract.

Provide contract verification using a non-production test implementation.

⸻

In Scope

	•	Canonical interval acquisition request.
	•	Canonical interval acquisition result.
	•	Coverage model.
	•	Structured failure model.
	•	Retry ownership semantics.
	•	Repository recording of acquisition outcomes.
	•	Application integration with the acquisition contract.
	•	Contract verification tests.
	•	Architecture documentation.

⸻

Explicitly Out of Scope

This task shall not implement production acquisition for any artifact family.

Specifically excluded are:

	•	earnings-call retrieval;
	•	press-release retrieval;
	•	provider-specific discovery;
	•	HTTP retrieval logic;
	•	parsing production artifacts;
	•	production source adapters;
	•	shared retrieval framework inferred from future implementations.

Likewise, this task shall not prescribe implementation mechanics, including:

	•	callbacks;
	•	background workers;
	•	asynchronous execution;
	•	generators or iterators;
	•	queues;
	•	session identifiers;
	•	durable acquisition sessions;
	•	resume protocols;
	•	context managers;
	•	parallel execution.

Future implementations remain free to choose any internal execution strategy that satisfies the contract.

⸻

Required Contract

The contract intentionally does not distinguish between sequential and parallel acquisition. Either implementation shall satisfy the same observable behavior.

The request shall identify:

	•	firm;
	•	artifact type;
	•	start date;
	•	end date.

Date intervals shall use closed-open semantics:
[start_date, end_date)

The result shall provide:

	•	zero or more successfully acquired artifact envelopes;
	•	structured acquisition failures;
	•	interval coverage status.

Coverage shall distinguish at minimum:

	•	complete;
	•	incomplete;
	•	indeterminate.

Acquisition shall never silently report complete coverage when known failures or indeterminate coverage remain.

Artifact ordering shall not be semantically significant.

⸻

Responsibility Boundaries

Acquisition implementation

Owns:

	•	discovery;
	•	retrieval;
	•	bounded retries for transient failures occurring during a single invocation;
	•	reporting successful artifacts;
	•	reporting structured failures;
	•	reporting interval coverage.

Does not own:

	•	scheduling;
	•	durable retry management;
	•	operator workflow;
	•	repository persistence;
	•	duplicate handling.

⸻

Repository

Owns:

	•	canonical identity;
	•	duplicate detection;
	•	idempotent persistence;
	•	artifact history;
	•	acquisition history;
	•	recording interval outcomes.

Repeated acquisition of the same interval shall be supported through repository idempotency rather than acquisition session state.

⸻

Application

Owns:

	•	deciding when interval acquisition occurs;
	•	deciding whether incomplete intervals should be retried;
	•	scheduling future acquisition;
	•	operator-visible policy.

Later recovery of missing artifacts shall occur by reacquiring the applicable interval rather than by resuming an acquisition session.

⸻

Implementation Deliverables

This task shall produce:

	1	Canonical interval acquisition request model.
	2	Canonical interval acquisition result model.
	3	Coverage status model.
	4	Structured acquisition failure model.
	5	Repository support for recording interval acquisition outcomes.
	6	Application integration consuming the acquisition contract.
	7	Non-production reference implementation (or equivalent test double) demonstrating contract consumption.
	8	Updated architecture documentation describing the acquisition boundary.

⸻

Follow-on Tasks

This task intentionally precedes production acquisition implementations.

Subsequent tasks are expected to independently implement the shared contract for at least:

	•	earnings-call acquisition;
	•	press-release acquisition.

Those implementations should initially remain independent. This task intentionally avoids introducing a generic acquisition framework. Common implementation infrastructure should emerge only after multiple production implementations demonstrate genuine shared behavior. Common implementation infrastructure should be introduced later, only when justified by demonstrated shared behavior rather than anticipated similarity.

⸻

Required Invariants

The implementation shall preserve:

	•	repository ownership of identity;
	•	repository ownership of duplicate handling;
	•	repository ownership of persistence;
	•	independent artifact-family acquisition implementations;
	•	implementation freedom behind the public contract.

Observable correctness shall not depend upon:

	•	retrieval order;
	•	sequential execution;
	•	parallel execution;
	•	synchronous versus asynchronous implementation.

Future implementations may introduce bounded parallelism without changing the acquisition contract.

Interval acquisition shall be safely repeatable. Reacquiring an interval shall rely on repository idempotency rather than acquisition-maintained execution state.

⸻

Documentation

Update architectural documentation to describe:

	•	the interval acquisition contract;
	•	ownership boundaries;
	•	retry responsibilities;
	•	interval coverage semantics;
	•	repository responsibilities;
	•	application responsibilities;
	•	rationale for intentionally leaving execution strategy unspecified.

⸻

Verification

Demonstrate through focused automated tests:

	•	empty interval;
	•	interval with no qualifying artifacts;
	•	single-artifact interval;
	•	multi-artifact interval;
	•	correct interval boundary behavior;
	•	complete coverage;
	•	incomplete coverage;
	•	indeterminate coverage;
	•	structured failure reporting;
	•	repository recording acquisition outcomes;
	•	idempotent repeated acquisition of the same interval using the reference implementation.

Verification shall demonstrate contract behavior without requiring a production retriever.

⸻

Review Criteria

Reject implementations that:

	•	expose execution mechanics as part of the public contract;
	•	require acquisition session management;
	•	prescribe callbacks, queues, workers, or concurrency;
	•	move repository responsibilities into acquisition;
	•	silently suppress acquisition failures;
	•	implement production earnings-call or press-release retrieval.

Accept implementations that establish a stable acquisition boundary while allowing future artifact-specific retrievers to evolve independently behind the same contract.
