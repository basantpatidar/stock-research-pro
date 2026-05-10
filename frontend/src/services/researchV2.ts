import { api } from "./api"
import type { TradeMode, ExecMode, Tier1Response, Tier2Response, Tier3Response, TokenEstimate } from "../types"

function handleError(e: any): never {
  if (e.response?.status === 429) {
    const detail = e.response.data?.detail ?? "Token or API call limit reached"
    throw new Error(`Rate limited: ${detail}`)
  }
  throw e
}

export const researchV2 = {
  tier1: (ticker: string, mode: TradeMode, execMode: ExecMode): Promise<Tier1Response> =>
    api.post("/v2/research/tier1", { ticker, mode, exec_mode: execMode }, { timeout: 60000 })
      .then(r => r.data)
      .catch(handleError),

  tier2: (ticker: string, tool: string, mode: TradeMode, execMode: ExecMode, params: Record<string, unknown> = {}): Promise<Tier2Response> =>
    api.post("/v2/research/tier2", { ticker, tool, mode, exec_mode: execMode, params })
      .then(r => r.data)
      .catch(handleError),

  tier3: (ticker: string, tool: string, mode: TradeMode): Promise<Tier3Response> =>
    api.post("/v2/research/tier3", { ticker, tool, mode })
      .then(r => r.data)
      .catch(handleError),

  estimate: (tool: string, ticker: string): Promise<TokenEstimate> =>
    api.get(`/v2/research/tier3/estimate?tool=${tool}&ticker=${ticker}`)
      .then(r => r.data)
      .catch(handleError),
}
