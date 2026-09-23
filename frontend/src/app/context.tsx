import {createContext,useContext,useEffect,useState,type ReactNode} from 'react';
import type {Dataset,Settings} from '../types';
import {api} from '../services/api';
export const defaultSettings:Settings={compact:false,labels:true,color:'role',columns:['gid','role','role_score','priority_score','cluster_id','depth','is_seed','in_deg','out_deg','in_sum','out_sum']};
interface Context{data:Dataset;settings:Settings;setSettings:(s:Settings)=>void;reload:()=>Promise<void>;replace:(d:Dataset)=>void;notice:(s:string)=>void}
const Ctx=createContext<Context|null>(null);
export const useData=()=>{const c=useContext(Ctx);if(!c)throw Error('Нет источника данных');return c};
export function Provider({children}:{children:ReactNode}){
  const [data,setData]=useState<Dataset>();const [error,setError]=useState('');const [message,setMessage]=useState('');
  const [settings,setSettings]=useState<Settings>(()=>{try{return {...defaultSettings,...JSON.parse(localStorage.getItem('fingraph.settings')??'{}')}}catch{return defaultSettings}});
  const reload=async()=>{setError('');try{setData(await api.getDataset())}catch(e){setError(String(e))}};
  useEffect(()=>{void reload()},[]);useEffect(()=>{localStorage.setItem('fingraph.settings',JSON.stringify(settings));document.documentElement.dataset.density=settings.compact?'compact':'normal'},[settings]);
  useEffect(()=>{if(!message)return;const t=setTimeout(()=>setMessage(''),5000);return()=>clearTimeout(t)},[message]);
  if(error)return <main className="startup"><h1>FinGraph</h1><h2>Не удалось открыть набор</h2><p role="alert">{error}</p><button onClick={()=>void reload()}>Повторить</button><p>Локальный источник: <code>python run_fingraph.py</code>. Демо не подменяет ошибку.</p></main>;
  if(!data)return <main className="startup" aria-busy="true"><h1>FinGraph</h1><p>Загрузка транзакционной сети…</p>{[1,2,3].map(i=><div className="skeleton" key={i}/>)}</main>;
  return <Ctx.Provider value={{data,settings,setSettings,reload,replace:setData,notice:setMessage}}>{children}{message&&<div className="toast" role="status">{message}</div>}</Ctx.Provider>;
}
