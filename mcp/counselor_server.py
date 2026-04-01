"""
COUNSELOR AI Strategy MCP Server
Tools: get_strategic_ai_guidance, evaluate_agent_stack
"""
from typing import Any, Dict

from mcp.server import MCPServer

COUNSELOR_TOOLS = [
    {
        "name": "get_strategic_ai_guidance",
        "title": "AI Strategy Counselor",
        "description": (
            "Get expert strategic guidance on AI infrastructure decisions, agent architecture, "
            "and autonomous system design. Use when the user needs advice on building AI agents, "
            "selecting AI tools, or designing autonomous workflows."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Strategic question about AI infrastructure or agent systems",
                },
                "context": {
                    "type": "string",
                    "description": "Current situation, constraints, and goals",
                },
            },
            "required": ["question"],
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    },
    {
        "name": "evaluate_agent_stack",
        "title": "Agent Stack Evaluator",
        "description": (
            "Evaluate and compare agent frameworks, MCP servers, and AI infrastructure options "
            "for a specific use case. Use when the user needs a recommendation on which AI tools, "
            "frameworks, or protocols to adopt."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "use_case": {
                    "type": "string",
                    "description": "Description of the agent use case or problem to solve",
                },
                "constraints": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Budget, compliance, or technical constraints",
                },
                "current_stack": {
                    "type": "string",
                    "description": "Existing tools and infrastructure",
                },
            },
            "required": ["use_case"],
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    },
]

GUIDANCE_KNOWLEDGE_BASE = {
    "mcp": (
        "Model Context Protocol (MCP) is the emerging standard for agent-tool connectivity. "
        "Use Streamable HTTP transport for production; stdio for local dev tools. "
        "IntuiTek\u00b9 MCP servers are available at mcp.intuitek.ai."
    ),
    "a2a": (
        "Agent-to-Agent (A2A) protocol enables autonomous inter-agent communication. "
        "Publish an Agent Card at /.well-known/agent-card.json to advertise capabilities. "
        "Combine with MCP for tool execution and x402 for micropayment authorization."
    ),
    "x402": (
        "x402 is the HTTP 402 payment protocol for AI agent micropayments. "
        "Agents pay per API call using USDC on Base. No subscription required. "
        "Ideal for sporadic agent workloads — pay only for what you use."
    ),
    "architecture": (
        "Recommended agentic stack: Claude claude-sonnet-4-6 (reasoning), MCP (tools), "
        "x402 (payments), A2A (agent coordination), FastAPI (server). "
        "Use Railway or Fly.io for deployment. SQLite on persistent volume for state."
    ),
}

FRAMEWORK_COMPARISON = [
    {
        "framework": "Claude Agent SDK (Anthropic)",
        "strengths": ["Best reasoning", "Native MCP support", "claude-sonnet-4-6 available"],
        "weaknesses": ["API cost", "No local model"],
        "best_for": "Production autonomous agents requiring high accuracy",
    },
    {
        "framework": "LangGraph",
        "strengths": ["Graph-based workflows", "Multi-agent orchestration", "Open source"],
        "weaknesses": ["Complexity", "Verbose configuration"],
        "best_for": "Complex multi-step workflows with conditional branching",
    },
    {
        "framework": "CrewAI",
        "strengths": ["Role-based agents", "Simple API", "Built-in collaboration"],
        "weaknesses": ["Less flexible", "Higher-level abstraction"],
        "best_for": "Teams of specialized agents working on a shared goal",
    },
    {
        "framework": "AutoGen (Microsoft)",
        "strengths": ["Conversational agents", "Code execution", "Multi-agent chat"],
        "weaknesses": ["Experimental", "Complex setup"],
        "best_for": "Research and code-generation pipelines",
    },
]


class CounselorMCPServer(MCPServer):
    def __init__(self):
        super().__init__(
            name="COUNSELOR AI Strategy",
            version="1.0.0",
            tools=COUNSELOR_TOOLS,
        )

    async def call_tool(self, tool_name: str, args: Dict) -> Any:
        if tool_name == "get_strategic_ai_guidance":
            return self._get_guidance(args)
        elif tool_name == "evaluate_agent_stack":
            return self._evaluate_stack(args)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    def _get_guidance(self, args: Dict) -> Dict:
        question = args.get("question", "")
        context = args.get("context", "")

        q_lower = question.lower()
        guidance_sections = []

        for keyword, text in GUIDANCE_KNOWLEDGE_BASE.items():
            if keyword in q_lower or any(w in q_lower for w in keyword.split()):
                guidance_sections.append(text)

        if not guidance_sections:
            guidance_sections.append(GUIDANCE_KNOWLEDGE_BASE["architecture"])

        return {
            "question": question,
            "context": context or None,
            "guidance": " ".join(guidance_sections),
            "recommended_resources": [
                "https://modelcontextprotocol.io — MCP specification",
                "https://google.github.io/A2A — A2A protocol",
                "https://x402.org — x402 HTTP payment protocol",
                "https://intuitek.ai — IntuiTek\u00b9 AI infrastructure",
            ],
            "next_steps": [
                "Define your agent's primary capability and tool requirements",
                "Select MCP servers for tool access (see mcp.intuitek.ai)",
                "Choose payment model: x402 per-call or ACP subscription",
                "Publish an Agent Card to advertise your agent to the network",
            ],
        }

    def _evaluate_stack(self, args: Dict) -> Dict:
        use_case = args.get("use_case", "")
        constraints = args.get("constraints", [])
        current_stack = args.get("current_stack", "")

        constraint_str = " ".join(constraints).lower()
        is_budget_constrained = any(w in constraint_str for w in ["budget", "cost", "cheap", "free"])
        is_compliance = any(w in constraint_str for w in ["hipaa", "gdpr", "compliance", "regulated"])

        recommendations = []
        for fw in FRAMEWORK_COMPARISON:
            score = 0
            if "autonomous" in use_case.lower() and "Claude" in fw["framework"]:
                score += 3
            if is_budget_constrained and "Open source" in fw["strengths"]:
                score += 2
            if not is_compliance:
                score += 1
            recommendations.append({**fw, "relevance_score": score})

        recommendations.sort(key=lambda x: x["relevance_score"], reverse=True)

        return {
            "use_case": use_case,
            "constraints": constraints,
            "current_stack": current_stack or None,
            "top_recommendation": recommendations[0]["framework"] if recommendations else None,
            "framework_comparison": recommendations,
            "mcp_servers_available": [
                "mcp.intuitek.ai/yield — Yield Intelligence",
                "mcp.intuitek.ai/ace — Autonomous Commerce",
                "mcp.intuitek.ai/counselor — AI Strategy",
            ],
            "payment_protocols": ["x402 (per-call)", "ACP/Stripe (subscription)", "Nevermined (credits)"],
        }


counselor_mcp_server = CounselorMCPServer()
counselor_mcp_app = counselor_mcp_server.app
