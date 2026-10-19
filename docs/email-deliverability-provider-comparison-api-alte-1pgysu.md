# Email Deliverability Provider Comparison — API Alternatives, Domain Verification, Suppression Evidence

TL;DR: For a developer-tools contact form, compare email providers by the audit packet you can reconstruct for one acknowledgment, not by a deliverability graph or the speed of domain setup. The application must preserve why the message was allowed, which support queue owned it, whether suppression was checked immediately before sending, and how later delivery events map back to that decision. Domain verification is necessary, an HTTP API can replace SMTP relay, and neither one supplies the consent evidence your system must retain.

This is the trade: keeping a local evidence trail creates storage, retention, and reconciliation work, but leaving the trail inside a provider dashboard makes a disputed send depend on mutable views and account access. I distrust a green dashboard here. My first question is narrower: what page fired, and can the responder explain this one message without guessing?

## What Should an Email Deliverability Provider Comparison Test in an API Alternative?

Use a tabletop incident rather than an invented success story. A person submits a support request through a developer-tools contact form. The router classifies it, assigns a queue, and schedules an acknowledgment. Before the worker runs, the recipient becomes suppressed. Hours later, an event arrives out of order. An auditor then asks why the message was sent, or why it was not.

One message. One timeline.

No guesswork.

The packet should connect the request identifier, the consent record and policy version, the queue decision, the suppression result observed at attempt time, an internal message identifier, the external attempt identifier, and the event chronology. It should omit the contact-form body unless that content is genuinely required; duplicating personal data through an event ledger enlarges the retention and access-control problem.

The governing invariant is **no acknowledgment may cross the delivery boundary without a current authorization decision and suppression check**. Provider events are observations after that boundary. They can report acceptance, delivery, bounce, or complaint in a provider's vocabulary, but they cannot retroactively establish why the application was entitled to send.

DKIM answers a different question. RFC 6376 defines a signing mechanism that lets a verifier associate a message with a responsible domain. It does not establish consent for a processing purpose. GDPR Article 7 separately requires that a controller be able to demonstrate consent where processing is based on consent, and it addresses withdrawal. Conflating those records produces an impressive-looking packet that cannot answer the actual compliance question.

## Reconstruct backward, then choose the provider

Start the evaluation at the incident review and work backward. Give an engineer a synthetic message ID, remove dashboard access, and ask for the authorization decision, queue assignment, attempt, and latest known outcome. If the reconstruction stalls at an external account, record that dependency explicitly. Do not repair the exercise with screenshots.

The resulting evidence map is short enough to review:

| Artifact | System of record | Failure worth detecting |
| --- | --- | --- |
| Consent receipt and policy version | Contact service | Missing or withdrawn authority |
| Classification and queue decision | Router | Request sent to the wrong team |
| Current suppression decision | Delivery worker | Stale queued work bypasses policy |
| Internal and external message IDs | Delivery adapter | Attempt cannot be reconciled |
| Authenticated, normalized event | Event consumer | Forged, duplicate, or orphaned observation |

This reverses the usual demo. Domain verification becomes deployment evidence: retain the required DNS values, the observed verification result, a timestamp, and the reviewer, then inspect actual message authentication. API ergonomics still matter, especially for a small SaaS team, but they sit below the ability to export and reconcile evidence.

An API-only path is reasonable when every sender is application code. It exposes structured errors and provider identifiers directly and avoids maintaining an SMTP relay solely for a new service. The cost is compatibility: an existing component that only speaks SMTP needs a bridge or cannot use that path. That is an integration constraint, not proof of better or worse deliverability.

## A comparison is a controlled incident, not a feature score

Put SendGrid, Resend, and Postmark through the same synthetic exercise. This is not a ranking, and the exercise should be repeated against current documentation and a test account because provider contracts can change. Score evidence you can preserve, not adjectives on a product page. The matrix has 18 result cells: 3 candidates multiplied by 6 checks, each backed by an artifact or an explicit gap. That number is small enough for a beginner SaaS team to review line by line, yet specific enough that a vague "supported" answer can't pass.

For each candidate, run six checks in an order that creates failure pressure:

1. Establish domain control and retain the DNS and review evidence outside the provider dashboard.
2. Send an authorized synthetic acknowledgment carrying an internal message ID; verify that the external attempt can be correlated without treating the email address as the primary key.
3. Queue a second job, change its local suppression state, and confirm that execution blocks it before any external call.
4. Feed duplicate and out-of-order synthetic events to the consumer; confirm transactional deduplication and prevent state from moving backward.
5. Withdraw the synthetic consent, repeat the reconstruction, and show the withdrawal independently of provider state.
6. Remove provider-console access from the responder and rebuild both timelines from the internal ledger.

Record pass, fail, or compensating control. For a compensating control, name an owner, a test, and the failure that should page. A missing native feature is not automatically fatal; an undocumented assumption with no detection path is. SendGrid, Resend, and Postmark are merely three subjects for the same harness, and no conclusion about their relative behavior is valid until the team verifies it directly.

I would accept a less convenient adapter before accepting evidence that disappears with dashboard access. For disposable test mail, I would make the opposite choice because there is no external recipient or compliance claim to defend. The policy context changes the decision.

## Put the policy check on the last responsible boundary

Checking suppression when the form is submitted is too early. A queued job can outlive the decision that created it, so the worker must reload current state immediately before reserving and sending the message. The following Go sketch keeps that ordering visible while leaving provider-specific transport behind an interface.

```go
package delivery

import (
	"context"
	"errors"
	"time"
)

var ErrNotAuthorized = errors.New("delivery is not authorized")

type Decision struct {
	RequestID     string
	Recipient     string
	Queue         string
	ConsentID     string
	PolicyVersion string
	Allowed       bool
}

type Attempt struct {
	MessageID  string
	RequestID  string
	ProviderID string
	CreatedAt  time.Time
}

type Store interface {
	CurrentDecision(context.Context, string) (Decision, error)
	IsSuppressed(context.Context, string) (bool, error)
	ReserveMessage(context.Context, Decision) (string, error)
	RecordAttempt(context.Context, Attempt) error
}

type Mailer interface {
	Send(context.Context, string, string, string) (string, error)
}

func Deliver(ctx context.Context, store Store, mailer Mailer, requestID string, now time.Time) error {
	decision, err := store.CurrentDecision(ctx, requestID)
	if err != nil {
		return err
	}

	blocked, err := store.IsSuppressed(ctx, decision.Recipient)
	if err != nil {
		return err
	}
	if !decision.Allowed || blocked {
		return ErrNotAuthorized
	}

	messageID, err := store.ReserveMessage(ctx, decision)
	if err != nil {
		return err
	}

	providerID, err := mailer.Send(ctx, messageID, decision.Recipient, decision.Queue)
	if err != nil {
		return err
	}

	return store.RecordAttempt(ctx, Attempt{
		MessageID:  messageID,
		RequestID:  decision.RequestID,
		ProviderID: providerID,
		CreatedAt:  now,
	})
}
```

The example deliberately exposes a hard gap: the process can stop after the external send succeeds but before `RecordAttempt` commits. The implementation needs a verified idempotency contract or an outbox and reconciliation design with tested duplicate behavior. Blind retries merely convert an unknown outcome into a possible duplicate.

Event ingestion has an equally sharp boundary. Authenticate the callback before trusting its fields, preserve an event identifier when supplied, deduplicate transactionally, tolerate reordering, and quarantine events that cannot be correlated. Page when authorization is bypassed or quarantine age threatens the evidence guarantee. Delivery-rate movement may belong on a dashboard, but it should not wake someone unless there is a defined action.

## Where does this design become unnecessary?

This design has real limitations. An internal prototype using disposable addresses, with no external mail and no audit requirement, may not need a durable evidence ledger; the extra writes, retention policy, access reviews, and reconciliation job are a poor trade-off there, so a thinner adapter is enough. It is also not suitable for a component that can only submit mail over SMTP unless the team accepts a bridge and owns its new failure boundary. The deadline for adding the stronger control is before real contact data or user-facing acknowledgments enter the path, not after the first disputed message.

At the other extreme, regulated data, multiple legal bases, regional retention requirements, or several downstream support queues demand more than this sketch: counsel-reviewed policy, stricter access control, explicit deletion rules, and possibly evidence storage separated from delivery operations. A provider comparison cannot decide those obligations.

The selection rule remains compact. **Choose the design that can reconstruct one message from current authorization through final observation, across retries, delayed events, suppression changes, and loss of console access.** Domain setup and API quality determine implementation effort. The audit packet determines whether the system can defend its behavior at 3 a.m.

## References

- RFC 6376, DomainKeys Identified Mail (DKIM): https://datatracker.ietf.org/doc/html/rfc6376
- GDPR Article 7, Conditions for consent: https://gdpr-info.eu/art-7-gdpr/

## Sources

- https://datatracker.ietf.org/doc/html/rfc6376
- https://gdpr-info.eu/art-7-gdpr/
