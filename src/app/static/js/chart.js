// chart.js

document.addEventListener('DOMContentLoaded', () => {
    const chartContainer = document.getElementById('tvchart');
    if (!chartContainer) return;

    // Create the Lightweight Chart
    const chart = LightweightCharts.createChart(chartContainer, {
        layout: {
            background: { type: 'solid', color: '#0f172a' }, // Tailwind bg-slate-900
            textColor: '#94a3b8', // Tailwind text-slate-400
        },
        grid: {
            vertLines: { color: '#1e293b' }, // Tailwind bg-slate-800
            horzLines: { color: '#1e293b' },
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
        },
        rightPriceScale: {
            borderColor: '#334155', // Tailwind slate-700
        },
        timeScale: {
            borderColor: '#334155',
            timeVisible: true,
            secondsVisible: false,
        },
    });

    // Handle resize
    new ResizeObserver(entries => {
        if (entries.length === 0 || entries[0].target !== chartContainer) { return; }
        const newRect = entries[0].contentRect;
        chart.applyOptions({ height: newRect.height, width: newRect.width });
    }).observe(chartContainer);

    // Initial series setup
    const candlestickSeries = chart.addCandlestickSeries({
        upColor: '#10b981', // emerald-500
        downColor: '#ef4444', // red-500
        borderVisible: false,
        wickUpColor: '#10b981',
        wickDownColor: '#ef4444',
    });

    const ema9Series = chart.addLineSeries({
        color: '#3b82f6', // blue-500
        lineWidth: 2,
        title: 'EMA9'
    });
    
    const ema50Series = chart.addLineSeries({
        color: '#f59e0b', // amber-500
        lineWidth: 2,
        title: 'EMA50'
    });

    // TODO: Fetch historical data from backend
    // Since we don't have a history endpoint yet, we will just show live points arriving via WebSocket.
    
    let lastTime = null;
    let lastClose = null;

    // Expose update function to the WebSocket listener in dashboard.html
    window.updateLivePrice = function(price, timeStr = null) {
        // time should be a unix timestamp or business day object.
        // If not provided, use current time
        const timeObj = timeStr ? new Date(timeStr) : new Date();
        const timeVal = Math.floor(timeObj.getTime() / 1000);
        
        // Very basic mock of a live candlestick. We just append a new dot or update current candle.
        // In a real scenario, the backend should send Open, High, Low, Close (OHLC).
        // If we only get price, we treat it as a new candle or update the existing one if time is same.
        
        if (lastTime === null || timeVal > lastTime) {
            // New time tick, create new candle (or just use close as open/high/low/close for simplicity)
            candlestickSeries.update({
                time: timeVal,
                open: price,
                high: price,
                low: price,
                close: price
            });
            lastTime = timeVal;
            lastClose = price;
        } else {
            // Update current candle
            const high = Math.max(lastClose, price);
            const low = Math.min(lastClose, price);
            candlestickSeries.update({
                time: lastTime,
                open: lastClose,
                high: high,
                low: low,
                close: price
            });
        }
    };
});
