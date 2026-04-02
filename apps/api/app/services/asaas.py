from datetime import date

import httpx

from app.core.config import settings
from app.models.enums import BillingCycle, PaymentMethod


class BillingIntegrationError(RuntimeError):
    pass


ASAAS_CYCLE_MAP = {
    BillingCycle.WEEKLY: "WEEKLY",
    BillingCycle.BIWEEKLY: "BIWEEKLY",
    BillingCycle.MONTHLY: "MONTHLY",
    BillingCycle.QUARTERLY: "QUARTERLY",
    BillingCycle.SEMIANNUALLY: "SEMIANNUALLY",
    BillingCycle.YEARLY: "YEARLY",
}

ASAAS_BILLING_TYPE_MAP = {
    PaymentMethod.BOLETO: "BOLETO",
    PaymentMethod.PIX: "PIX",
    PaymentMethod.CREDIT_CARD: "CREDIT_CARD",
}


class AsaasClient:
    def __init__(self) -> None:
        if not settings.asaas_api_key:
            raise BillingIntegrationError("ASAAS_API_KEY nao configurada.")
        self.base_url = settings.asaas_api_base_url.rstrip("/")
        self.headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "access_token": settings.asaas_api_key,
        }

    async def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
            response = await client.request(method, path, headers=self.headers, json=payload)
        data = response.json()
        if response.status_code >= 400:
            raise BillingIntegrationError(data.get("errors", data))
        return data

    async def create_customer(
        self,
        *,
        name: str,
        email: str | None,
        cpf_cnpj: str | None,
        external_reference: str,
    ) -> dict:
        payload = {
            "name": name,
            "email": email,
            "cpfCnpj": cpf_cnpj,
            "externalReference": external_reference,
        }
        return await self._request("POST", "/v3/customers", payload)

    async def create_subscription(
        self,
        *,
        customer_id: str,
        cycle: BillingCycle,
        payment_method: PaymentMethod,
        value: float,
        next_due_date: date,
        description: str,
        external_reference: str,
    ) -> dict:
        payload = {
            "customer": customer_id,
            "billingType": ASAAS_BILLING_TYPE_MAP[payment_method],
            "cycle": ASAAS_CYCLE_MAP[cycle],
            "value": value,
            "nextDueDate": next_due_date.isoformat(),
            "description": description,
            "externalReference": external_reference,
        }
        return await self._request("POST", "/v3/subscriptions", payload)

    async def update_subscription(
        self,
        subscription_id: str,
        *,
        value: float,
        next_due_date: date,
        cycle: BillingCycle,
    ) -> dict:
        payload = {
            "value": value,
            "nextDueDate": next_due_date.isoformat(),
            "cycle": ASAAS_CYCLE_MAP[cycle],
        }
        return await self._request("POST", f"/v3/subscriptions/{subscription_id}", payload)

    async def delete_subscription(self, subscription_id: str) -> dict:
        return await self._request("DELETE", f"/v3/subscriptions/{subscription_id}")
