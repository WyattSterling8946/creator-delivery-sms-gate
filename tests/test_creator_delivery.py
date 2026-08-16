import json

import pytest

from creator_delivery.infrai_sms import Infrai
from creator_delivery.media_login import (
    AssetStage,
    CodeVerification,
    CreatorDeliveryWorkflow,
    DeliveryRequest,
)


def test_processed_asset_is_delivered_only_after_code_verification() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def transport(path, payload, headers):
        calls.append((path, payload))
        assert headers["Authorization"] == "Bearer test-key"
        return 200, {}, json.dumps({"ok": True, "data": {"verified": True}}).encode()

    flow = CreatorDeliveryWorkflow(Infrai("test-key", transport))
    request = DeliveryRequest(asset_id="trailer-7", creator_phone="+15551234567")
    flow.ingest(request)
    flow.mark_processing(request.asset_id)

    waiting = flow.request_creator_delivery(request.asset_id)
    delivered = flow.verify_and_deliver(
        CodeVerification(
            asset_id=request.asset_id,
            creator_phone=request.creator_phone,
            code="482901",
        )
    )

    assert waiting.stage is AssetStage.READY_FOR_CREATOR
    assert delivered.stage is AssetStage.DELIVERED
    assert calls[0][0] == "/v1/sms/otp"
    assert set(calls[0][1]) == {"to", "idempotency_key"}
    assert calls[1][0] == "/v1/sms/verify"
    assert set(calls[1][1]) == {"to", "code", "idempotency_key"}


def test_ingested_asset_cannot_request_delivery_early() -> None:
    flow = CreatorDeliveryWorkflow(Infrai("test-key", lambda path, payload, headers: (200, {}, b"{}")))
    flow.ingest(DeliveryRequest(asset_id="rough-cut", creator_phone="+15551234567"))

    with pytest.raises(ValueError, match="finish processing"):
        flow.request_creator_delivery("rough-cut")
