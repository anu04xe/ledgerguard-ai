from typing import Any, Dict, List


class LedgerTools:
    """Read-only investigation tools for LedgerGuard."""

    def __init__(self, orders, gateways, settlements):
        self.orders = orders
        self.gateways = gateways
        self.settlements = settlements

    def get_order(self, order_id: str) -> Dict[str, Any]:
        for order in self.orders:
            if order.order_id == order_id:
                return order.model_dump(mode="json")

        return {
            "found": False,
            "order_id": order_id,
        }

    def get_gateway(self, gateway_ref: str) -> Dict[str, Any]:
        for gateway in self.gateways:
            if gateway.gateway_ref == gateway_ref:
                return gateway.model_dump(mode="json")

        return {
            "found": False,
            "gateway_ref": gateway_ref,
        }

    def get_settlement(self, settlement_id: str) -> Dict[str, Any]:
        for settlement in self.settlements:
            if settlement.settlement_id == settlement_id:
                return settlement.model_dump(mode="json")

        return {
            "found": False,
            "settlement_id": settlement_id,
        }

    def search_settlements(
        self,
        gateway_ref: str,
    ) -> List[Dict[str, Any]]:
        matches = []

        for settlement in self.settlements:
            if settlement.gateway_ref == gateway_ref:
                matches.append(
                    settlement.model_dump(mode="json")
                )

        return matches
