from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import SystemMessage, HumanMessage

from app.agent.state import AgentState
from app.agent.prompts import get_system_prompt
from app.llm.factory import get_llm_with_fallback
from app.config import get_settings

# Import all tools
from app.tools.price import get_price
from app.tools.technicals import get_technicals
from app.tools.news import get_news_impact
from app.tools.sentiment import get_sentiment
from app.tools.analyst import get_analyst_consensus
from app.tools.earnings import get_earnings
from app.tools.fundamentals import get_fundamentals
from app.tools.options import get_options_signals
from app.tools.insider import get_insider_activity
from app.tools.institutional import get_institutional_changes
from app.tools.short_interest import get_short_interest
from app.tools.geopolitical import get_geopolitical_events
from app.tools.macro import get_macro_environment
from app.tools.sector import get_sector_heatmap
from app.tools.cascade import get_cascade_impact
from app.tools.forecast import get_price_forecast
from app.tools.risk_reward import get_risk_reward
from app.tools.screener import run_screener
from app.tools.convergence import get_convergence_score
from app.tools.google_trends import get_trends
from app.tools.new.investor_personas import investor_personas
from app.tools.new.bull_bear import bull_bear_debate
from app.tools.new.congressional import get_congressional_trades
from app.tools.new.backtester import run_backtest
from app.tools.new.earnings_transcript import analyze_earnings_transcript
from app.tools.new.paper_trade import analyze_paper_trade

ALL_TOOLS = [
    get_price,
    get_technicals,
    get_news_impact,
    get_sentiment,
    get_analyst_consensus,
    get_earnings,
    get_fundamentals,
    get_options_signals,
    get_insider_activity,
    get_institutional_changes,
    get_short_interest,
    get_geopolitical_events,
    get_macro_environment,
    get_sector_heatmap,
    get_cascade_impact,
    get_price_forecast,
    get_risk_reward,
    run_screener,
    get_convergence_score,
    get_trends,
    investor_personas,
    bull_bear_debate,
    get_congressional_trades,
    run_backtest,
    analyze_earnings_transcript,
    analyze_paper_trade,
]


def build_agent_graph():
    settings = get_settings()
    llm = get_llm_with_fallback(settings, task="agent")
    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    def agent_node(state: AgentState):
        system_prompt = get_system_prompt(state.mode)
        messages = [SystemMessage(content=system_prompt)] + state.messages
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    tool_node = ToolNode(ALL_TOOLS)

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")

    return graph.compile()


# Singleton — compiled once at startup
_agent = None


def get_agent():
    global _agent
    if _agent is None:
        _agent = build_agent_graph()
    return _agent
