import type {Client,Dataset,Edge,NodeFilter,Transaction} from '../types';
export const roles = {
  coordinator:{label:'Признаки координации',color:'#D95A65'},consolidator:{label:'Консолидация',color:'#C77D12'},distributor:{label:'Распределение',color:'#8054CF'},
  transit:{label:'Транзит',color:'#356DF3'},terminal:{label:'Конечный в выборке',color:'#168477'},boundary:{label:'Граница выгрузки',color:'#64748B'},peripheral:{label:'Периферия',color:'#7B879B'},
} as const;
export const boundaryWarning='Граница выгрузки: исходящие связи за четвёртым коленом не наблюдаются. Отсутствие исходящих переводов не доказывает конечное получение.';
export const number=(value:number|null|undefined)=>value==null?'Нет данных':new Intl.NumberFormat('ru-RU',{maximumFractionDigits:2}).format(value);
export const money=(value:number|null|undefined,compact=false)=>value==null?'Нет данных':new Intl.NumberFormat('ru-RU',{maximumFractionDigits:compact?1:2,notation:compact?'compact':'standard'}).format(value)+' KZT';
export const shortGid=(gid:string)=>gid.length>14?gid.slice(0,6)+'…'+gid.slice(-5):gid;
export const dateLabel=(value:string)=>new Intl.DateTimeFormat('ru-RU',{day:'2-digit',month:'short',year:'numeric',...(value.includes('T')?{hour:'2-digit',minute:'2-digit'} as const:{})}).format(new Date(value));
export const clusterColor=(id:number)=>['#356DF3','#168477','#8054CF','#C77D12','#D95A65','#467F9D','#8C6C58','#688842'][Math.abs(id)%8];
export function compareGid(a:string,b:string){return a.length-b.length||a.localeCompare(b)}
export const ranked=(nodes:Client[])=>[...nodes].sort((a,b)=>(b.priority_score??-1)-(a.priority_score??-1)||compareGid(a.gid,b.gid));
export function filterNodes(nodes:Client[],f:NodeFilter){return ranked(nodes.filter(n=>(!f.q||n.gid.includes(f.q))&&(!f.role||n.role===f.role)&&(!f.cluster||String(n.cluster_id)===f.cluster)&&(!f.depth||String(n.depth)===f.depth)&&(!f.seed||n.is_seed)&&(!f.boundary||n.depth===4)&&(!f.min||(n.priority_score!=null&&n.priority_score>=+f.min))&&(!f.max||(n.priority_score!=null&&n.priority_score<=+f.max))))}
export function assertDataset(value:Dataset):Dataset {
  const id=(v:unknown)=>{if(typeof v!=='string'||!/^\d+$/.test(v))throw Error('Небезопасный GID: API должен передавать полные цифровые идентификаторы строками до JSON-разбора.')};
  if(!value?.meta||!Array.isArray(value.nodes)||!Array.isArray(value.edges)||!Array.isArray(value.transactions))throw Error('Неверный контракт набора данных');
  const ids=new Set<string>();
  value.nodes.forEach(n=>{id(n.gid);if(ids.has(n.gid))throw Error('Дубликат GID');ids.add(n.gid);if(n.role&&!(n.role in roles))throw Error('Недокументированная роль: '+n.role);for(const s of [n.role_score,n.priority_score])if(s!=null&&(!Number.isFinite(s)||s<0||s>1))throw Error('Оценка вне диапазона 0–1')});
  [...value.edges,...value.transactions].forEach(e=>{id(e.src);id(e.dst);if(!ids.has(e.src)||!ids.has(e.dst))throw Error('Участник перевода отсутствует в nodes')});
  return value;
}
export function neighborhood(gid:string,edges:Edge[],steps:number,direction:string){const ids=new Set([gid]);for(let i=0;i<steps;i++){const next=new Set(ids);for(const e of edges){if(direction!=='in'&&ids.has(e.src))next.add(e.dst);if(direction!=='out'&&ids.has(e.dst))next.add(e.src)}next.forEach(x=>ids.add(x))}return ids}
export function activity(tx:Transaction[],gid?:string){const days=new Map<string,{date:string;inflow:number;outflow:number;total:number}>();for(const t of tx){if(gid&&t.src!==gid&&t.dst!==gid)continue;const day=t.date.slice(0,10);const r=days.get(day)??{date:day,inflow:0,outflow:0,total:0};r.total+=t.sum_kzt;if(t.dst===gid)r.inflow+=t.sum_kzt;if(t.src===gid)r.outflow+=t.sum_kzt;days.set(day,r)}return [...days.values()].sort((a,b)=>a.date.localeCompare(b.date))}
export function csv(rows:Record<string,unknown>[],columns:string[]){const cell=(v:unknown)=>'"'+String(v??'').replaceAll('"','""')+'"';return '\ufeff'+columns.map(cell).join(',')+'\r\n'+rows.map(r=>columns.map(k=>cell(r[k])).join(',')).join('\r\n')}
export function saveBlob(blob:Blob,name:string){const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000)}
export function exportCsv(rows:object[],columns:string[],name:string){saveBlob(new Blob([csv(rows as Record<string,unknown>[],columns)],{type:'text/csv;charset=utf-8'}),name)}
