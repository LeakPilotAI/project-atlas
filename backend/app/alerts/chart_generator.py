import io
from datetime import datetime
from typing import List, Optional

import mplfinance as mpf
import pandas as pd

from app.core.logging import get_logger

logger = get_logger("chart_generator")


def generate_candlestick_chart(
    symbol: str,
    timestamps: List[datetime],
    opens: List[float],
    highs: List[float],
    lows: List[float],
    closes: List[float],
    volumes: Optional[List[float]] = None,
    entry_price: Optional[float] = None,
    current_price: Optional[float] = None,
    title: str = "",
) -> Optional[bytes]:
    """
    Generate a professional dark-themed candlestick chart.
    Returns PNG bytes ready to send to Discord.
    """
    try:
        if len(closes) < 8:
            return None

        df = pd.DataFrame({
            "Open": opens,
            "High": highs,
            "Low": lows,
            "Close": closes,
        }, index=pd.DatetimeIndex(timestamps))

        if volumes and len(volumes) == len(closes):
            df["Volume"] = volumes

        mc = mpf.make_marketcolors(
            up="#a6e3a1",
            down="#f38ba8",
            edge="inherit",
            wick="inherit",
            volume="#89b4fa",
            alpha=0.9,
        )
        style = mpf.make_mpf_style(
            marketcolors=mc,
            facecolor="#1e1e2e",
            edgecolor="#313244",
            figcolor="#1e1e2e",
            gridcolor="#313244",
            gridstyle="--",
            y_on_right=False,
            rc={
                "axes.labelcolor": "#cdd6f4",
                "xtick.color": "#cdd6f4",
                "ytick.color": "#cdd6f4",
                "axes.titlesize": 13,
            },
        )

        addplots = []
        if entry_price:
            addplots.append(
                mpf.make_addplot([entry_price] * len(df), color="#a6e3a1", linestyle="--", width=1.1)
            )
        if current_price and current_price != entry_price:
            addplots.append(
                mpf.make_addplot([current_price] * len(df), color="#f9e2af", linestyle="-", width=1.1)
            )

        buf = io.BytesIO()

        mpf.plot(
            df,
            type="candle",
            style=style,
            title=title or f"{symbol} • Project Atlas",
            ylabel="Price",
            volume=True if volumes else False,
            addplot=addplots if addplots else None,
            figsize=(11, 5.5),
            tight_layout=True,
            savefig=dict(fname=buf, dpi=140, bbox_inches="tight", facecolor="#1e1e2e"),
        )

        buf.seek(0)
        return buf.read()

    except Exception as e:
        logger.error("Failed to generate candlestick chart", symbol=symbol, error=str(e))
        return None