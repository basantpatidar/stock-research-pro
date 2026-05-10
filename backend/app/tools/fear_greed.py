import httpx


def get_fear_greed() -> dict:
    try:
        resp = httpx.get("https://api.alternative.me/fng/?limit=7", timeout=8)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        if not data:
            return {"error": "No data returned"}

        current = data[0]
        value = int(current["value"])
        classification = current["value_classification"]

        if value <= 20:
            color = "red"
            signal = "Extreme Fear — historically strong buy zone"
        elif value <= 40:
            color = "amber"
            signal = "Fear — cautious optimism for buyers"
        elif value <= 60:
            color = "neutral"
            signal = "Neutral — no strong directional edge"
        elif value <= 80:
            color = "green"
            signal = "Greed — momentum favors bulls, caution on chasing"
        else:
            color = "red"
            signal = "Extreme Greed — contrarian sell signal, elevated pullback risk"

        history = [
            {
                "value": int(d["value"]),
                "classification": d["value_classification"],
                "timestamp": d["timestamp"],
            }
            for d in data
        ]

        return {
            "value": value,
            "classification": classification,
            "color": color,
            "signal": signal,
            "history": history,
        }
    except Exception as e:
        return {"error": str(e)}
