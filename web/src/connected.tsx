import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import './connected.css'

type Farmer = { farmer_id: string; name: string; village: string; district: string; state: string; language: string; lat: number; lon: number; crops: {crop: string; sowing_date: string; area_acres: number | null}[] }
type Tool = { source: string; fetched_at: string; is_cached: boolean; confidence: string; error: string | null; value: Record<string, any> }
type Risk = { risk_type: string; level: string; reasons: string[]; rule_source: string }
type Snapshot = { farmer: Farmer; as_of: string; weather: Tool; plots: {crop: string; tool_results: Record<string, Tool>; risk_results: Risk[]; data_gaps: string[]}[] }
type Advice = { answer_text: string; risk_level: string; recommendation: string; sources: {name: string; fetched_at: string; is_cached: boolean}[]; uncertainty_note: string; data_gaps: string[]; refer_to_expert: boolean }
type Entry = { farmer: string; question: string; answer: Advice }
type Meta = {data_mode: string; mock_llm: boolean}
const base = import.meta.env.VITE_API_BASE_URL || '/api'
async function request<T>(path: string, body?: object, signal?: AbortSignal): Promise<T> {
  const controller = new AbortController()
  const abort = () => controller.abort()
  signal?.addEventListener('abort', abort)
  const timeout = setTimeout(abort, 90000)
  try {
    const response = await fetch(base + path, {signal: controller.signal, method: body ? 'POST' : 'GET', headers: body ? {'Content-Type': 'application/json'} : {}, body: body ? JSON.stringify(body) : undefined})
    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      throw new Error(response.status === 429 ? 'Please wait a minute before trying again.' : typeof data.detail === 'string' ? data.detail : `Request failed (${response.status}). Please retry.`)
    }
    return await response.json()
  } finally { clearTimeout(timeout); signal?.removeEventListener('abort', abort) }
}
type State = {farmers: Farmer[]; id: string; setId: (s: string) => void; meta: Meta | null; error: string; reload: () => void; version: number; scenario: string; setScenario: (s: string) => void; history: Entry[]; addEntry: (e: Entry) => void}
const Context = createContext<State>(null!)
const useData = () => useContext(Context)
export function DataProvider({children}: {children: ReactNode}) {
  const [farmers, setFarmers] = useState<Farmer[]>([]), [id, setId] = useState('')
  const [meta, setMeta] = useState<Meta | null>(null), [error, setError] = useState(''), [version, setVersion] = useState(0)
  const [scenario, setScenario] = useState('rain'), [history, setHistory] = useState<Entry[]>([])
  useEffect(() => {
    let active = true
    setError('')
    Promise.all([request<Farmer[]>('/farmers'), request<Meta>('/meta')]).then(([f, m]) => {
      if (!active) return
      setFarmers(f); setMeta(m); setId(old => f.some(x => x.farmer_id === old) ? old : f[0]?.farmer_id || '')
    }).catch(e => { if (active) setError(e.message) })
    return () => { active = false }
  }, [version])
  return <Context.Provider value={{farmers,id,setId,meta,error,version,reload:()=>setVersion(v=>v+1),scenario,setScenario,history,addEntry:e=>setHistory(h=>[...h,e])}}>{children}</Context.Provider>
}
export function ConnectionBar() {
  const d = useData()
  return <section className="connection-banner connected-banner" aria-live="polite"><div>
    <strong>{d.error ? 'Connection unavailable' : d.meta ? 'Backend connected' : 'Connecting…'}</strong>
    <p>{d.error || `Fictional profiles · ${d.meta?.data_mode === 'live' ? 'Live data requested; check each source' : 'Simulated weather and sample prices'} · Demo agronomic rules`}</p>
    <small>{d.meta?.mock_llm ? 'Template-based demo replies' : 'Language model enabled with guarded fallback'} · Public read-only profiles · Role selection is not sign-in</small>
  </div><div className="context-controls">
    <label>Farmer<select value={d.id} onChange={e=>d.setId(e.target.value)} disabled={!d.farmers.length}>{d.farmers.map(f=><option key={f.farmer_id} value={f.farmer_id}>{f.name}</option>)}</select></label>
    {d.meta?.data_mode === 'demo' && <label>Scenario<select value={d.scenario} onChange={e=>d.setScenario(e.target.value)}>{['rain','dry','heatwave','api_failure','stale_mandi','no_mandi'].map(s=><option key={s} value={s}>{s.replaceAll('_',' ')}</option>)}</select></label>}
    <button className="secondary-button" onClick={d.reload}>Refresh</button>
  </div></section>
}
function useResource<T>(path: string | null) {
  const d = useData(), [data,setData] = useState<T | null>(null), [error,setError]=useState(''), [loading,setLoading]=useState(false)
  useEffect(()=> {
    setData(null); setError(''); if (!path) return
    let active = true; const controller = new AbortController(); setLoading(true)
    const url = path + (d.meta?.data_mode === 'demo' ? `?demo_scenario=${d.scenario}` : '')
    request<T>(url,undefined,controller.signal).then(result=>{if(active)setData(result)}).catch(e=>{if(active)setError(e.message)}).finally(()=>{if(active)setLoading(false)})
    return ()=>{active=false; controller.abort()}
  },[path,d.version,d.scenario,d.meta?.data_mode])
  return {data,error,loading}
}
function Empty({children}: {children: ReactNode}) {return <div className="empty-state compact"><p>{children}</p></div>}
function Panel({title,children}: {title:string; children: ReactNode}) {return <section className="panel connected-panel"><div className="panel-header"><h2>{title}</h2></div>{children}</section>}
function Badge({level}: {level:string}) {return <span className={`risk-badge ${level.toLowerCase()}`}>{level}</span>}
function Source({tool}: {tool:Tool}) {return <div className="source-note"><strong>{tool.source}</strong><p>{tool.error || `${tool.confidence} confidence · ${tool.is_cached ? 'cached' : 'fetched'} ${new Date(tool.fetched_at).toLocaleString()}`}</p>{tool.value.stale && <Badge level="STALE"/>}{tool.value.simulated && <Badge level="DEMO"/>}{tool.value.sample && <Badge level="SAMPLE"/>}</div>}
function Answer({answer}: {answer:Advice}) {return <article className="answer-card"><div className="answer-status"><Badge level={answer.risk_level}/><span>{answer.recommendation.replaceAll('_',' ')}</span><span>DEMO rules</span></div><p className="answer-text">{answer.answer_text}</p><p>{answer.uncertainty_note}</p>{answer.refer_to_expert && <p><strong>Consult a local KVK or agricultural officer.</strong></p>}{answer.data_gaps.length>0 && <details><summary>Data limitations ({answer.data_gaps.length})</summary><ul>{answer.data_gaps.map((g,i)=><li key={i}>{g}</li>)}</ul></details>}<details><summary>Sources ({answer.sources.length})</summary>{answer.sources.map((s,i)=><p key={i}>{s.name} · {new Date(s.fetched_at).toLocaleString()}{s.is_cached ? ' · cached' : ''}</p>)}</details></article>}
function Chat() {
  const d=useData(), [question,setQuestion]=useState(''), [busy,setBusy]=useState(false), [error,setError]=useState('')
  async function send() {
    if (!question.trim() || !d.id || busy) return
    const farmer=d.id, submitted=question.trim(); setBusy(true); setError('')
    try { const answer=await request<Advice>('/advise',{farmer_id:farmer,question:submitted,...(d.meta?.data_mode==='demo'?{demo_scenario:d.scenario}:{})}); d.addEntry({farmer,question:submitted,answer}); setQuestion('') } catch(e){setError((e as Error).message)} finally {setBusy(false)}
  }
  return <><section className="farmer-chat-card"><div className="chat-intro"><h2>मैं आपकी क्या मदद कर सकता हूँ?</h2><p>Ask in English, Hindi or Hinglish. Mention your crop when you have more than one.</p></div><div className="suggestion-list">{['Soybean mein spray karun kya?','अगले 2 दिनों में बारिश होगी क्या?','Soybean ka mandi bhav kya hai?','Should I irrigate soybean?'].map(q=><button key={q} disabled={busy} onClick={()=>setQuestion(q)}>{q}</button>)}</div><form onSubmit={e=>{e.preventDefault();void send()}}><label className="question-label" htmlFor="question">Your question · अपना सवाल लिखें</label><textarea id="question" value={question} onChange={e=>setQuestion(e.target.value)} maxLength={500} rows={4} disabled={busy} required/><div className="chat-submit-row"><span>{question.length}/500</span><button className="primary-button" disabled={busy || !d.id || !question.trim()}>{busy?'Preparing advice…':'Ask Kisan Saathi'}</button></div></form>{error && <p role="alert" className="api-error">{error}</p>}</section><History/></>
}
function History(){const d=useData();const entries=d.history.filter(h=>h.farmer===d.id);return <Panel title="Advice from this visit"><p className="source-note">Conversation stays in memory for this browser visit; it resets on reload.</p>{!entries.length?<Empty>No questions yet. Ask Kisan Saathi to get started.</Empty>:entries.map((h,i)=><div key={i}><h3 className="question-text">{h.question}</h3><Answer answer={h.answer}/></div>)}</Panel>}
function Alerts(){
  const d=useData(), [alerts,setAlerts]=useState<Advice[]|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('')
  useEffect(()=>{setAlerts(null);setError('')},[d.id,d.scenario,d.version])
  useEffect(()=>{let active=true;setBusy(true);if(!d.id){setBusy(false);return} request<{alerts:Advice[]}>('/alerts/generate',{farmer_id:d.id,...(d.meta?.data_mode==='demo'?{demo_scenario:d.scenario}:{})}).then(r=>{if(active)setAlerts(r.alerts)}).catch(e=>{if(active)setError(e.message)}).finally(()=>{if(active)setBusy(false)});return()=>{active=false}},[d.id,d.scenario,d.version,d.meta?.data_mode])
  return <Panel title="Crop risk alerts">{busy?<Empty>Checking crop risks…</Empty>:error?<p role="alert" className="api-error">{error}</p>:alerts?.length?alerts.map((a,i)=><Answer key={i} answer={a}/>):<Empty>No medium/high alerts returned. Missing evidence can still produce UNKNOWN risk.</Empty>}</Panel>
}
function Weather({tool}:{tool:Tool}){return <Panel title="Weather outlook"><Source tool={tool}/>{!tool.error && <><div className="metric-grid">{[['Next 48h rain',tool.value.rain_next_48h_mm,'mm'],['Maximum temperature',tool.value.temperature_max_c,'°C'],['Rain probability',tool.value.rain_probability_pct,'%']].map(([label,value,unit])=><article key={String(label)}><span>{label}</span><strong>{value===undefined?'—':`${value} ${unit}`}</strong></article>)}</div><div className="table-scroll"><table><thead><tr><th>Date</th><th>Rain (mm)</th><th>Low (°C)</th><th>High (°C)</th></tr></thead><tbody>{(tool.value.daily||[]).map((v:any)=><tr key={v.date}><td>{v.date}</td><td>{v.rain_mm}</td><td>{v.temp_min_c}</td><td>{v.temp_max_c}</td></tr>)}</tbody></table></div></>}</Panel>}
function Crops({snapshot}:{snapshot:Snapshot}){return <>{!snapshot.plots.length && <Panel title="Crops"><Empty>No crop or sowing date saved for this demo profile.</Empty></Panel>}{snapshot.plots.map((plot,i)=><Panel key={i} title={plot.crop}><Source tool={plot.tool_results.crop_stage}/><div className="metric-grid"><article><span>Estimated stage</span><strong>{plot.tool_results.crop_stage.value.stage || 'Unknown'}</strong></article><article><span>Sowing date</span><strong>{snapshot.farmer.crops[i]?.sowing_date || 'Unknown'}</strong></article><article><span>Area (acres)</span><strong>{snapshot.farmer.crops[i]?.area_acres ?? 'Unknown'}</strong></article></div><div className="risk-list">{plot.risk_results.map(r=><div key={r.risk_type}><strong>{r.risk_type}</strong><Badge level={r.level}/><p>{r.reasons.join(' ')}</p><small>{r.rule_source}</small></div>)}</div>{plot.data_gaps.length>0&&<details><summary>Data gaps</summary><ul>{plot.data_gaps.map((g,j)=><li key={j}>{g}</li>)}</ul></details>}</Panel>)}</>}
function Markets({snapshot}:{snapshot:Snapshot}){return <>{!snapshot.plots.length&&<Panel title="Mandi prices"><Empty>A crop is needed to look up a commodity.</Empty></Panel>}{snapshot.plots.map((p,i)=><Panel key={i} title={`${p.crop} · Mandi prices`}><Source tool={p.tool_results.mandi}/><p className="source-note">Prices are in INR/quintal. Check arrival date, variety and grade before comparing markets.</p><div className="table-scroll"><table><thead><tr><th>Market</th><th>Variety</th><th>Arrival date</th><th>Min</th><th>Modal</th><th>Max</th></tr></thead><tbody>{(p.tool_results.mandi.value.prices||[]).map((r:any,j:number)=><tr key={j}><td>{r.market}</td><td>{r.variety || 'Unknown'}</td><td>{r.arrival_date}</td><td>{r.min_price}</td><td>{r.modal_price}</td><td>{r.max_price}</td></tr>)}</tbody></table></div>{!(p.tool_results.mandi.value.prices||[]).length&&<Empty>No usable prices returned.</Empty>}</Panel>)}</>}
function Fpo(){
  const d=useData(), {data,error,loading}=useResource<{as_of:string;rows:{farmer_id:string;farmer:string;village:string;crop:string;stage:string;risks:Record<string,string>;data_gaps:string[]}[]}>('/fpo')
  if(loading)return <Empty>Loading farm overview…</Empty>;if(error)return <p className="api-error" role="alert">{error}</p>;if(!data)return null
  const high=data.rows.filter(r=>Object.values(r.risks).includes('HIGH')).length
  return <><section className="stats-grid">{[['Demo farmers',d.farmers.length],['Crop plots',d.farmers.reduce((n,f)=>n+f.crops.length,0)],['Villages',new Set(d.farmers.map(f=>f.village)).size],['High-risk rows',high]].map(([label,value])=><article className="stat-card" key={label}><div><p>{label}</p><strong>{value}</strong><span>From backend · DEMO</span></div></article>)}</section><Panel title="Farmers & crop risks"><p className="source-note">Updated {new Date(data.as_of).toLocaleString()} · All agronomic thresholds are demo rules.</p><div className="table-scroll"><table><thead><tr><th>Farmer</th><th>Crop & stage</th><th>Risk</th><th>Data gaps</th></tr></thead><tbody>{data.rows.map((r,i)=><tr key={i}><td><strong>{r.farmer}</strong><br/>{r.village}</td><td>{r.crop}<br/>{r.stage}</td><td>{Object.entries(r.risks).map(([k,v])=><div className="risk-cell" key={k}>{k} <Badge level={v}/></div>)}</td><td><details><summary>{r.data_gaps.length} limitations</summary><ul>{r.data_gaps.map((g,j)=><li key={j}>{g}</li>)}</ul></details></td></tr>)}</tbody></table></div></Panel></>
}
function Farmers(){const d=useData(),[search,setSearch]=useState('');return <Panel title="Farmer profiles"><label>Search farmers<input className="connected-input" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Name, village or crop"/></label><div className="profile-grid">{d.farmers.filter(f=>JSON.stringify(f).toLowerCase().includes(search.toLowerCase())).map(f=><article className="answer-card" key={f.farmer_id}><h3>{f.name}</h3><p>{f.village}, {f.district}</p><p>{f.crops.map(c=>c.crop).join(', ') || 'No crops saved'}</p><button className="secondary-button" onClick={()=>d.setId(f.farmer_id)}>{d.id===f.farmer_id?'Selected':'Select farmer'}</button></article>)}</div><p>Public demo profiles are read-only. No personal records are uploaded.</p></Panel>}
function Farm({page,onAsk}:{page:string;onAsk?:()=>void}){
  const d=useData(), {data,error,loading}=useResource<Snapshot>(d.id?`/dashboard/${encodeURIComponent(d.id)}`:null)
  if(loading)return <Empty>Loading farm conditions…</Empty>;if(error)return <p className="api-error" role="alert">{error}</p>;if(!data)return <Empty>Select a farmer to view the farm.</Empty>
  if(page==='My Profile')return <Panel title={data.farmer.name}><div className="metric-grid">{Object.entries(data.farmer).filter(([k])=>k!=='crops').map(([k,v])=><article key={k}><span>{k.replaceAll('_',' ')}</span><strong>{String(v)}</strong></article>)}</div></Panel>
  return <>{page==='Home'&&<><section className="farmer-welcome-card"><div><span className="farmer-overline">आपके खेत की जानकारी · DEMO</span><h2>Namaste, {data.farmer.name}</h2><p>{data.farmer.village}, {data.farmer.district}, {data.farmer.state}</p></div></section><button className="farmer-ask-card" onClick={onAsk}><strong>किसान साथी से सवाल पूछें →</strong></button></>}{!['My Crops','Crop Monitoring'].includes(page)&&<Weather tool={data.weather}/>}<Crops snapshot={data}/>{['Weather & Mandi','Agricultural Data'].includes(page)&&<Markets snapshot={data}/>}</>
}
export function ConnectedPage({page,onAsk}:{page:string;onAsk?:()=>void}){
  const d=useData()
  const titles:Record<string,string>={'Ask Kisan Saathi':'सवाल पूछें','Home':'नमस्ते','Weather & Mandi':'मौसम और मंडी','My Crops':'मेरी फसलें'}
  let content:ReactNode
  if(['Overview','Reports'].includes(page))content=<Fpo/>
  else if(page==='Farmers')content=<Farmers/>
  else if(['Ask Kisan Saathi','Farmer Queries','AI Advisories'].includes(page))content=<Chat/>
  else if(page==='My Advisories')content=<History/>
  else if(['Alerts','Alerts & Notifications'].includes(page))content=<Alerts/>
  else if(page==='Soil Records')content=<Panel title="Soil records"><Empty>No measured soil data is available. Soil tests and uploads are not supported yet.</Empty></Panel>
  else if(page==='Staff Management')content=<Panel title="Staff access"><Empty>This is a public hackathon demo. Staff accounts and access control have not been implemented.</Empty></Panel>
  else if(page==='Settings')content=<Panel title="Connection settings"><p>Data mode: {d.meta?.data_mode || 'Connecting'}</p><p>Reply mode: {d.meta?.mock_llm?'Demo templates':'Language model with fallback'}</p><p>Profiles: read-only fictional records. Choose a scenario and profile above.</p><p>API keys stay on the server. Live mandi data still requires a configured data.gov.in key and resource.</p></Panel>
  else content=<Farm page={page} onAsk={onAsk}/>
  return <><header className="page-header"><div><div className="eyebrow">KisanSaathi · {titles[page] || 'Farmer advisory'}</div><h1>{page}</h1><p>Crop-level advice with visible sources, uncertainty and demo-rule labels.</p></div></header>{content}</>
}
