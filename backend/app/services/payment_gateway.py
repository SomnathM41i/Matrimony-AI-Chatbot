from abc import ABC, abstractmethod

from app.models.commercial_model import PaymentGateway, PaymentOrder


class PaymentAdapter(ABC):
    """Provider-neutral payment contract.

    Adapters may create hosted checkout orders and verify callbacks, but only the
    subscription service is allowed to activate entitlements.
    """

    @abstractmethod
    async def create_provider_order(self, order: PaymentOrder) -> dict:
        raise NotImplementedError

    @abstractmethod
    async def verify_callback(self, payload: dict, signature: str | None) -> dict:
        raise NotImplementedError


class ManualPaymentAdapter(PaymentAdapter):
    async def create_provider_order(self, order: PaymentOrder) -> dict:
        return {
            "checkout_available": False,
            "provider_order_id": None,
            "message": "Manual administrator verification is required.",
        }

    async def verify_callback(self, payload: dict, signature: str | None) -> dict:
        raise RuntimeError("Manual payments do not accept public callbacks")


def payment_adapter(gateway: PaymentGateway | None) -> PaymentAdapter:
    adapter_type = gateway.adapter_type if gateway else "manual"
    if adapter_type == "manual":
        return ManualPaymentAdapter()
    raise RuntimeError(f"Payment adapter is not installed: {adapter_type}")
