# SMS OTP Delivery Can Fail After Sender Registration (A Signup Runbook)

Treat SMS OTP delivery for a signup verification link as an unreliable attempt: carrier filtering can make it fail after the application receives an acceptance response.

**Short answer:** a valid link can disappear because acceptance by an SMS gateway is only the start of delivery. Sender registration, carrier filtering, a shared sending path, and anti-fraud controls can each stop or delay the message after the application has created it. The reliable design is to give every attempt an internal ID, separate provider acceptance from terminal delivery, let the user retry without minting an unlimited stream of credentials, and preserve a second verification path. Page on the user-visible failure budget, not on a pretty submission count.

That rule matters in customer support because a new user who cannot verify an account cannot open the ticket they came to file. The link is short-lived by design, while the delivery path has several independent decision points. A dashboard that says `accepted=99.9%` answers the wrong question.

## How can carrier filtering make SMS OTP delivery fail?

The first postmortem question should be: **what page fired?** If it fired on gateway errors alone, the alert watched an integration rather than the signup journey. An API can accept a request while the downstream carrier later filters it; conversely, a delayed status event can make an already completed signup look unfinished if the system treats webhook arrival as the user's state.

Model the path as evidence with different strength. `requested` means the application admitted the operation. `accepted` means the downstream messaging service accepted it for processing. A later delivery report may add useful transport evidence. Only redemption of the verification link proves that this signup completed. These states must not collapse into a single Boolean called `sent`.

Sender identity is part of the path, not decoration. In the United States, application-to-person traffic over 10-digit long-code numbers has a registration framework; the linked compliance documentation describes registration of brands and campaigns and the consequences attached to unregistered traffic. Treat registration state as deployable configuration with an owner and a preflight check. Do not discover it from a drop in conversions.

The European Union is not one carrier network or one uniform sender policy. That observation should change the runbook, even without pretending that a country list is permanent: segment results by destination country, carrier when the data is available, sender identity, and route. A global average can remain calm while one destination cohort is effectively down.

Shared routes add another boundary. They may couple the reputation and capacity of unrelated traffic, so the application must not infer route health from its own request acceptance. Anti-fraud controls create a different ambiguity: a blocked burst may be protecting accounts, or it may be rejecting a legitimate retry wave after delayed messages. Weak observability makes those two cases look identical.

A limitation of this architecture is its dependence on a reachable phone and a sender path the service can monitor. SMS is a poor primary factor when the service cannot establish that path for its actual destinations, when users may lack reliable mobile coverage, or when a threat model cannot tolerate control of a phone number standing in for control of an account. In those cases, choose a verification method that fits the threat model and user access conditions rather than hiding the mismatch behind more SMS retries. The fallback has a trade-off too: greater reach costs extra state, support procedures, and abuse surface, so it should be an independently protected recovery path, not a button that bypasses the original controls.

There is no universal route fix.

## Build one attempt ledger, not three conflicting dashboards

The useful unit is an immutable delivery attempt linked to a verification challenge. Store no raw one-time secret or full link in logs. Record the internal attempt ID, challenge ID, destination region at the minimum useful resolution, sender identity class, route class, submission result, provider message reference, status timestamps, and final redemption outcome. Retention and access should match the sensitivity of authentication metadata.

Keep the contract deliberately small. The following Go types show the boundary; they do not assume a commercial API or claim that every carrier exposes the same status vocabulary.

```go
package verification

import (
	"context"
	"time"
)

type AttemptState string

const (
	Requested AttemptState = "requested"
	Accepted  AttemptState = "accepted"
	Delivered AttemptState = "delivered"
	Failed    AttemptState = "failed"
)

type SendRequest struct {
	AttemptID  string
	To         string
	Message    string
	IdempotencyKey string
}

type Receipt struct {
	ProviderMessageID string
	AcceptedAt        time.Time
}

type Messenger interface {
	Send(ctx context.Context, req SendRequest) (Receipt, error)
}

type AttemptStore interface {
	Create(ctx context.Context, challengeID, attemptID string, createdAt time.Time) error
	MarkAccepted(ctx context.Context, attemptID string, receipt Receipt) error
	MarkFailed(ctx context.Context, attemptID, reasonClass string, at time.Time) error
}
```

An idempotency key prevents an application retry from silently becoming a fresh logical attempt when the first response is lost. It does not mean the carrier deduplicates messages, and it does not replace a challenge-level resend policy. The application should decide, explicitly, whether a retry reuses a still-valid challenge or rotates it; whichever rule it chooses, only the latest permitted challenge should verify the account, and the rule should be tested under concurrent requests.

Keep failure reasons coarse in application logic. Configuration rejection, rate control, downstream filtering, unreachable destination, expired challenge, and unknown are useful operational classes. Raw downstream codes belong in restricted diagnostic data, with the external reference attached, because code meanings and availability can differ by path. Hard-coding a universal carrier taxonomy into the signup service produces confident nonsense.

Do not retry everything. A bounded retry can help with a transient submission failure, but automatic retries after an accepted request can create duplicate links, amplify fraud signals, and make the user trust the oldest message just as the application invalidates it.

Slow down.

Put a challenge-level cooldown and an attempt ceiling around another send, then offer a fallback path whose health is measured independently. Email is a distinct transport with its own sending and deliverability controls; the referenced email service documentation is useful background, not evidence that email is infallible.

## Verify the journey before changing traffic

Predeployment verification needs three layers. First, unit-test state transitions and idempotency. Second, run controlled integration tests through the configured sender identities for the destination cohorts the service actually supports. Third, canary the release against signup completion, because synthetic delivery reports do not click links.

A compact test matrix is more useful than a wall of green totals:

| Question | Signal | Decision |
| --- | --- | --- |
| Did the application submit? | requested-to-accepted ratio and latency | Inspect credentials, configuration, and gateway availability |
| Did transport evidence arrive? | accepted-to-terminal-status ratio by destination and sender | Inspect registration, route, and filtering evidence |
| Did the user finish? | accepted-to-redemption ratio within the challenge window | Inspect delay, link handling, expiry, and user friction |
| Did retries help or hurt? | redemption by attempt number, plus duplicate attempts | Tune cooldown and attempt ceiling |

Use counts and distributions, not a single success percentage. Compare a destination cohort with its own established baseline and require a minimum sample size before automation moves traffic; the exact threshold depends on normal volume and the error budget, so inventing a universal number would be reckless. Low-volume cohorts need a longer window or a manual decision.

The alert should join cause-oriented signals with the user outcome. A sharp fall in redemption with stable request volume is page-worthy even if acceptance remains high. A missing webhook stream is also actionable, but it should not automatically declare every pending message failed. Reconcile late and duplicate events by provider message reference and event time, make handlers idempotent, and preserve the previous state when an older event arrives after a newer one.

Test the ugly sequence: request accepted, callback delayed, user asks for resend, second message arrives first, user opens the first link, and both callbacks are delivered twice. If the expected account state is not obvious, the implementation is not ready.

## Roll back the change, not the evidence

Rollback should restore the last known-good sender and route configuration while preserving attempt records, provider references, and callback ingestion. Deleting the evidence makes the next incident harder and can turn a reversible delivery problem into an authentication audit problem.

Prepare the rollback before rollout: version sender configuration; separate it from application binaries; keep the previous configuration deployable; and define who may switch traffic. A route change also needs a canary. Moving all traffic because one aggregate chart turned red can transfer the same registration mistake everywhere at once.

During an incident, freeze unrelated authentication changes, confirm that link redemption itself still works, and compare requested, accepted, terminal transport status, and redeemed counts over the same challenge-age window. Then segment. Country, sender identity, route class, application release, and attempt number usually narrow the fault domain more honestly than a vendor status page.

Recovery is not the moment the acceptance graph rises. Hold the incident open until delayed messages stop causing stale-link confusion, the affected cohorts return to their normal completion range, and the resend queue drains without another anti-fraud spike. Document which page fired, which user outcome it represented, and which missing dimension slowed diagnosis. That is the part worth carrying into the next runbook.

## References

- Amazon Simple Email Service documentation: https://docs.aws.amazon.com/ses/latest/dg/Welcome.html
- US A2P 10DLC compliance documentation: https://www.twilio.com/docs/messaging/compliance/a2p-10dlc
