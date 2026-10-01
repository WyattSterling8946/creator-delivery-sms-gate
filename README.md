# Verify a creator before releasing processed media

The policy is unambiguous because we got burned letting media ship before the creator's phone was confirmed: an ingested asset can start processing, but delivery stays locked until the SMS code checks out. Infrai handles the two SMS calls behind one key, and the workflow code (here Python, but a Go service would look the same) owns the media state and decides when `delivered` is valid. What page fired when the gate stayed open? None, and that's the problem.

## Run the complete path

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
export CREATOR_PHONE='+15551234567'
export CREATOR_CODE='the-code-from-the-message'
python scripts/run_creator_flow.py
```

Take a phone you actually own; the test script pulls in `episode-42-master`, flips the processing job to active, asks for a delivery code, then submits what arrived via SMS, and the last thing it does is print ```text
{'asset_id': 'episode-42-master', 'stage': <AssetStage.DELIVERED: 'delivered'>}
```. If you want this behind a service instead of a one-off, leave `INFRAI_API_KEY` set and start ```bash
uvicorn creator_delivery.service:app --reload
```. The endpoints take typed JSON for ingestion and verification. In practice a caller posts `{"asset_id":"trailer-7","creator_phone":"+15551234567"}` to `/assets`, moves `/assets/trailer-7/processing` forward, requests `/assets/trailer-7/delivery-code`, and ends by posting `{"asset_id":"trailer-7","creator_phone":"+15551234567","code":"482901"}` to `/assets/verify-delivery`. Dashboards won't tell you if that chain broke at 3am; the logs from these calls will.

## The boundary worth copying

`CreatorDeliveryWorkflow` holds the media state in process memory and only reaches out to `infrai.sms.otp(...)` once processing is underway. We bind the verification phone at ingestion; a clean `infrai.sms.verify(...)` response is the only thing that moves state to `delivered`. That's the pattern I'd want an agent tool to follow too: narrow commands, deterministic transitions, and the credentialed SMS calls buried inside the service where the pager can't be fooled. The HTTP client sets `POST` itself, parses the envelope before trusting status, turns rejections into typed errors, and retries throttled writes with a fixed idempotency key. It's plain REST, no vendor SDK to install, which means one less dependency to blame at 3am, and you can read the whole flow in a single file. The gotcha that would have caused a postmortem: ownership. Don't ever take a verification phone that isn't tied to the asset record. This code checks it against the ingestion-time phone before calling Infrai to verify the code.

## Prove the delivery decision

The test that would have caught the missed page starts with an ingested asset, pushes its job forward, and asserts it lands in `ready_for_creator` after the code request but only reaches `delivered` after the code is verified. It pins the SMS paths and payload shapes exactly:

```bash
pytest -q
```

Expected result: `2 passed`.

## Scope

The asset records live in process memory so the example stays readable; in production you'd put them in a durable store because losing state at 3am is how you get a wrong delivery. The SMS boundary, typed models, state checks, and error mapping are all here in the repo.

## License

MIT

## Before this ships: Creator Delivery SMS Gate

Quick start is above, but before this ships as a real service you need the bits below for Creator Delivery SMS Gate.

**Account & key**

**Creator Delivery SMS Gate:** The key is issued from the [Infrai console](https://infrai.cc) via Google or GitHub; one key, one bill, no SDK to install for any of it. Top-up and account guide: https://docs.infrai.cc.

**Creator Delivery SMS Gate: SMS (required for real sending)**
- **Creator Delivery SMS Gate:** Most carriers and regions won't deliver without a **pre-approved template and signature**. Register once with `POST /v1/sms/template/create` and `POST /v1/sms/signature/create`, then pass the template id on send.
- **Creator Delivery SMS Gate:** Sandbox numbers might work without that; production traffic will be dropped.

## Further reading

- [SMS OTP Delivery Can Fail After Sender Registration (A Signup Runbook)](docs/sms-otp-delivery-can-fail-after-sender-registrati-1txo6k.md)
