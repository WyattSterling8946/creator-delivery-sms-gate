import os

from creator_delivery.infrai_sms import Infrai
from creator_delivery.media_login import CodeVerification, CreatorDeliveryWorkflow, DeliveryRequest


phone = os.environ.get("CREATOR_PHONE")
code = os.environ.get("CREATOR_CODE")
if not phone or not code:
    raise RuntimeError("CREATOR_PHONE and CREATOR_CODE are required")

flow = CreatorDeliveryWorkflow(Infrai.from_env())
request = DeliveryRequest(asset_id="episode-42-master", creator_phone=phone)
print(flow.ingest(request).model_dump())
print(flow.mark_processing(request.asset_id).model_dump())
print(flow.request_creator_delivery(request.asset_id).model_dump())
print(
    flow.verify_and_deliver(
        CodeVerification(asset_id=request.asset_id, creator_phone=phone, code=code)
    ).model_dump()
)
