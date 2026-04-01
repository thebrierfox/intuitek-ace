"""
YIELD INTELLIGENCE MCP Server
Tools: analyze_yield_opportunities, optimize_income_portfolio
"""
from typing import Any, Dict

from mcp.server import MCPServer

YIELD_TOOLS = [
    {
        "name": "analyze_yield_opportunities",
        "title": "Yield Opportunity Analyzer",
        "description": (
            "Identify the highest-returning passive income opportunities across asset classes. "
            "Use when the user wants to generate passive income, maximize portfolio yield, "
            "or find dividend and interest-bearing investments."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "investment_capital": {
                    "type": "number",
                    "description": "Available capital in USD",
                },
                "monthly_income_target": {
                    "type": "number",
                    "description": "Target monthly passive income in USD",
                },
                "risk_tolerance": {
                    "type": "string",
                    "enum": ["conservative", "moderate", "aggressive"],
                },
            },
            "required": ["investment_capital"],
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    },
    {
        "name": "optimize_income_portfolio",
        "title": "Income Portfolio Optimizer",
        "description": (
            "Build and rebalance a diversified portfolio to maximize recurring income. "
            "Use when the user wants to achieve financial independence through investment income "
            "or optimize an existing portfolio for yield."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "current_holdings": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Current portfolio positions",
                },
                "target_monthly_income": {
                    "type": "number",
                    "description": "Desired monthly income in USD",
                },
                "time_horizon_years": {
                    "type": "integer",
                    "description": "Investment time horizon in years",
                },
            },
            "required": ["target_monthly_income"],
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    },
]


class YieldMCPServer(MCPServer):
    def __init__(self):
        super().__init__(
            name="YIELD INTELLIGENCE",
            version="1.0.0",
            tools=YIELD_TOOLS,
        )

    async def call_tool(self, tool_name: str, args: Dict) -> Any:
        if tool_name == "analyze_yield_opportunities":
            return self._analyze_yield(args)
        elif tool_name == "optimize_income_portfolio":
            return self._optimize_portfolio(args)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    def _analyze_yield(self, args: Dict) -> Dict:
        capital = args.get("investment_capital", 0)
        target = args.get("monthly_income_target")
        risk = args.get("risk_tolerance", "moderate")

        rate_map = {"conservative": 0.04, "moderate": 0.07, "aggressive": 0.12}
        annual_rate = rate_map.get(risk, 0.07)
        projected_monthly = (capital * annual_rate) / 12

        opportunities = {
            "conservative": [
                {"asset": "US Treasury ETF (BIL)", "yield_pct": 5.1, "risk": "very low"},
                {"asset": "High-yield savings / HYSA", "yield_pct": 4.5, "risk": "very low"},
                {"asset": "Investment-grade bond ETF (LQD)", "yield_pct": 4.8, "risk": "low"},
            ],
            "moderate": [
                {"asset": "Dividend ETF (SCHD)", "yield_pct": 3.5, "risk": "moderate"},
                {"asset": "REITs (VNQ)", "yield_pct": 4.2, "risk": "moderate"},
                {"asset": "Preferred stock ETF (PFF)", "yield_pct": 6.0, "risk": "moderate"},
            ],
            "aggressive": [
                {"asset": "Covered-call ETF (QYLD)", "yield_pct": 11.5, "risk": "high"},
                {"asset": "BDC (ARCC)", "yield_pct": 9.8, "risk": "high"},
                {"asset": "High-yield bond ETF (HYG)", "yield_pct": 7.2, "risk": "high"},
            ],
        }

        return {
            "investment_capital": capital,
            "risk_tolerance": risk,
            "projected_annual_yield_pct": round(annual_rate * 100, 1),
            "projected_monthly_income_usd": round(projected_monthly, 2),
            "projected_annual_income_usd": round(projected_monthly * 12, 2),
            "income_gap_usd": round((target or 0) - projected_monthly, 2) if target else None,
            "top_opportunities": opportunities.get(risk, opportunities["moderate"]),
            "disclaimer": (
                "Projections are illustrative estimates based on historical averages. "
                "Past performance does not guarantee future results. Not financial advice."
            ),
        }

    def _optimize_portfolio(self, args: Dict) -> Dict:
        target = args.get("target_monthly_income", 0)
        holdings = args.get("current_holdings", [])
        horizon = args.get("time_horizon_years", 10)

        required_capital = (target * 12) / 0.06  # assume 6% blended yield

        allocation = [
            {"asset_class": "Dividend equities", "weight_pct": 35, "example": "SCHD, VYM"},
            {"asset_class": "REITs", "weight_pct": 20, "example": "VNQ, O"},
            {"asset_class": "Bonds / fixed income", "weight_pct": 25, "example": "BND, LQD"},
            {"asset_class": "Covered-call ETFs", "weight_pct": 10, "example": "QYLD, JEPI"},
            {"asset_class": "Cash / short-term", "weight_pct": 10, "example": "BIL, HYSA"},
        ]

        return {
            "target_monthly_income_usd": target,
            "target_annual_income_usd": target * 12,
            "estimated_required_capital_usd": round(required_capital, 0),
            "time_horizon_years": horizon,
            "existing_holdings_count": len(holdings),
            "recommended_allocation": allocation,
            "rebalance_frequency": "quarterly",
            "disclaimer": (
                "Portfolio recommendations are for informational purposes only. "
                "Consult a licensed financial advisor before making investment decisions."
            ),
        }


yield_mcp_server = YieldMCPServer()
yield_mcp_app = yield_mcp_server.app
