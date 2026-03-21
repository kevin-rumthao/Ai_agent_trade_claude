import React, { useState, useEffect, useRef } from 'react';
import { Play, Square, Settings, Activity, Cpu, Briefcase, TrendingUp, AlertTriangle, ShieldCheck } from 'lucide-react';
import './index.css';

interface ApplicationState {
  is_running: boolean;
  current_iteration: number;
  last_error: string | null;
  symbol: string;
  provider: string;
}

interface MarketFeatures {
  price: number;
  ema_9: number | null;
  ema_50: number | null;
  atr: number | null;
  volatility: number | null;
  adx: number | null;
}

interface LogEntry {
  id: string;
  type: 'info' | 'trade' | 'ai' | 'error';
  title: string;
  message: string;
  time: string;
}

function App() {
  const [appState, setAppState] = useState<ApplicationState>({
    is_running: false,
    current_iteration: 0,
    last_error: null,
    symbol: 'Loading...',
    provider: 'Loading...'
  });
  
  const [features, setFeatures] = useState<MarketFeatures | null>(null);
  const [regime, setRegime] = useState<{regime: string, confidence: number} | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  const addLog = (type: LogEntry['type'], title: string, message: string) => {
    const newLog: LogEntry = {
      id: Math.random().toString(36).substring(7),
      type,
      title,
      message,
      time: new Date().toLocaleTimeString([], { hour12: false })
    };
    setLogs(prev => [newLog, ...prev].slice(0, 50));
  };

  useEffect(() => {
    // Initial status fetch
    fetch('http://localhost:8000/api/status')
      .then(res => res.json())
      .then(data => {
        setAppState(data);
      })
      .catch(err => {
        addLog('error', 'API Connection Required', 'Failed to connect to FastAPI backend on :8000');
      });

    // Setup WebSocket
    const setupWebSocket = () => {
      const ws = new WebSocket('ws://localhost:8000/ws');
      wsRef.current = ws;

      ws.onopen = () => {
        addLog('info', 'System Online', 'Connected to trading engine real-time feed');
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          
          if (msg.type === 'system_event') {
            addLog('info', 'System Event', msg.message);
          } else if (msg.type === 'system_error') {
            addLog('error', 'System Error', msg.message);
          } else if (msg.type === 'iteration_start') {
            setAppState(prev => ({ ...prev, current_iteration: msg.iteration }));
          } else if (msg.type === 'state_update') {
            const data = msg.data;
            if (data.features) setFeatures(data.features);
            if (data.regime) {
              setRegime(data.regime);
              addLog('ai', 'Regime Update', `${data.regime.regime} detected with ${(data.regime.confidence * 100).toFixed(0)}% confidence`);
            }
            if (data.signals && data.signals.length > 0) {
              data.signals.forEach((s: any) => {
                 addLog('trade', 'Signal Generated', `${s.direction} on ${s.strategy} (${(s.strength * 100).toFixed(0)}% strength)`);
              });
            }
            if (data.approved_orders && data.approved_orders.length > 0) {
               data.approved_orders.forEach((o: any) => {
                  addLog('trade', 'Order Approved', `${o.side} ${o.quantity} ${o.symbol} @ ${o.order_type}`);
               });
            }
          }
        } catch (e) {
          console.error("Message passing error", e);
        }
      };

      ws.onclose = () => {
        addLog('error', 'Connection Lost', 'WebSocket disconnected. Retrying in 5s...');
        setTimeout(setupWebSocket, 5000);
      };
    };

    setupWebSocket();

    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  const handleStart = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/start', { method: 'POST' });
      const data = await res.json();
      if (data.status === 'started') {
        setAppState(prev => ({ ...prev, is_running: true }));
      }
    } catch (e) {
      addLog('error', 'Start Failed', 'Could not contact backend API');
    }
  };

  const handleStop = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/stop', { method: 'POST' });
      const data = await res.json();
      setAppState(prev => ({ ...prev, is_running: false }));
    } catch (e) {
      addLog('error', 'Stop Failed', 'Could not contact backend API');
    }
  };

  return (
    <div className="app-container">
      {/* Sidebar Navigation */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="brand">
            <Cpu className="text-purple" />
            <span>AiTrader Pro</span>
          </div>
        </div>
        <nav>
          <div className="nav-item active"><Activity size={18} /> Live Arena</div>
          <div className="nav-item"><Briefcase size={18} /> Portfolio</div>
          <div className="nav-item"><TrendingUp size={18} /> Analytics</div>
          <div className="nav-item"><Settings size={18} /> Configuration</div>
        </nav>
      </aside>

      {/* Main Content Area */}
      <main className="main-content">
        <header className="topbar">
          <div>
            <h1 style={{ fontSize: '1.5rem', marginBottom: '4px' }}>Trading Dashboard</h1>
            <div className="text-muted" style={{ fontSize: '0.875rem' }}>
              Provider: {appState.provider.toUpperCase()} | Pair: {appState.symbol}
            </div>
          </div>
          <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
            <div className={`status-indicator`}>
              <div className={`pulse-dot ${!appState.is_running ? 'stopped' : ''}`}></div>
              {appState.is_running ? 'System Active' : 'System Halted'}
            </div>
            {appState.is_running ? (
              <button className="btn btn-danger" onClick={handleStop}><Square size={16} /> Stop Bot</button>
            ) : (
              <button className="btn btn-primary" onClick={handleStart}><Play size={16} /> Start Bot</button>
            )}
          </div>
        </header>

        <div className="dashboard-grid">
          {/* Top Stats */}
          <div className="glass-panel col-span-4 stat-card">
            <div className="stat-header">
              <span>Latest Price</span>
              <span className="stat-badge badge-gray">{appState.symbol}</span>
            </div>
            <div className="stat-value text-main">
              {features?.price ? `$${features.price.toLocaleString(undefined, {minimumFractionDigits: 2})}` : '---'}
            </div>
          </div>

          <div className="glass-panel col-span-4 stat-card">
            <div className="stat-header">
              <span>AI Market Regime</span>
              <span className="stat-badge badge-purple" style={{background: 'var(--accent-purple)', color: 'white', border: 'none'}}><ShieldCheck size={12} style={{display:'inline', marginBottom:'-2px'}}/> Model Active</span>
            </div>
            <div className="stat-value text-purple" style={{fontSize: '1.5rem', marginTop: '4px'}}>
              {regime?.regime ? regime.regime.toUpperCase() : 'ANALYZING...'}
            </div>
            {regime && <div className="text-muted" style={{fontSize: '0.75rem'}}>Confidence: {(regime.confidence * 100).toFixed(1)}%</div>}
          </div>

          <div className="glass-panel col-span-4 stat-card">
            <div className="stat-header">
              <span>Graph Iteration</span>
              <span className="stat-badge badge-green">Running</span>
            </div>
            <div className="stat-value text-green">
              {appState.current_iteration}
            </div>
          </div>

          {/* Center Area: Technicals & Chart Placeholder */}
          <div className="glass-panel col-span-8">
            <h2 className="glass-title"><Activity size={18} /> Signal Indicators</h2>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Indicator</th>
                  <th>Value</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>EMA (9)</td>
                  <td className="font-mono">{features?.ema_9?.toFixed(2) || '---'}</td>
                  <td>{features ? (features.price > (features.ema_9 || 0) ? <span className="text-green">Bullish</span> : <span className="text-red">Bearish</span>) : '---'}</td>
                </tr>
                <tr>
                  <td>EMA (50)</td>
                  <td className="font-mono">{features?.ema_50?.toFixed(2) || '---'}</td>
                  <td>{features ? (features.price > (features.ema_50 || 0) ? <span className="text-green">Bullish</span> : <span className="text-red">Bearish</span>) : '---'}</td>
                </tr>
                <tr>
                  <td>Volatility (Realized)</td>
                  <td className="font-mono">{features?.volatility ? (features.volatility * 100).toFixed(2) + '%' : '---'}</td>
                  <td>---</td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Right Area: Execution Log */}
          <div className="glass-panel col-span-4" style={{ paddingRight: '12px' }}>
            <h2 className="glass-title"><Terminal size={18} /> System Log</h2>
            <div className="log-list">
              {logs.length === 0 ? (
                <div className="text-muted" style={{textAlign: 'center', padding: '40px 0'}}>Waiting for system events...</div>
              ) : (
                logs.map(log => (
                  <div key={log.id} className="log-item">
                    <div className={`log-icon ${log.type}`}>
                      {log.type === 'info' && <Activity size={16} />}
                      {log.type === 'ai' && <Cpu size={16} />}
                      {log.type === 'trade' && <TrendingUp size={16} />}
                      {log.type === 'error' && <AlertTriangle size={16} />}
                    </div>
                    <div className="log-content">
                      <div className="log-title">
                        {log.title}
                        <span className="log-time">{log.time}</span>
                      </div>
                      <div className="log-desc">{log.message}</div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

// Quick helper to avoid another import for Terminal
function Terminal(props: any) {
  return <svg xmlns="http://www.w3.org/2000/svg" width={props.size||24} height={props.size||24} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line></svg>;
}

export default App;
