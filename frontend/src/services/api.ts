import type {Dataset} from '../types';
import {assertDataset,activity,saveBlob} from '../lib/data';
async function request<T>(url:string,options?:RequestInit):Promise<T>{const r=await fetch(url,options);const body=await r.json();if(!r.ok)throw Error(body.error??'Ошибка источника данных');return body}
export const api={
  getDataset:async()=>assertDataset(await request<Dataset>('/api/dataset')),
  getGraph:(d:Dataset)=>({nodes:d.nodes,edges:d.edges}),getNodes:(d:Dataset)=>d.nodes,getNode:(d:Dataset,gid:string)=>d.nodes.find(n=>n.gid===gid),
  getTransactions:(d:Dataset)=>d.transactions,getClusters:(d:Dataset)=>d.clusters,getCluster:(d:Dataset,id:string)=>d.clusters.find(c=>String(c.cluster_id)===id),
  getAnalytics:(d:Dataset)=>activity(d.transactions),getExports:(d:Dataset)=>d.exports,
  async download(name:string){const r=await fetch('/api/exports/'+encodeURIComponent(name));if(!r.ok)throw Error('Выгрузка недоступна');saveBlob(await r.blob(),name)},
  status:()=>request<{state:string;message:string}>('/api/status'),
  analyze:()=>request('/api/analyze',{method:'POST',headers:{'X-FinGraph':'local'}}),
  async upload(files:File[]){const body:Record<string,string>={};for(const file of files){body[file.name]=await new Promise<string>((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(String(r.result).split(',')[1]);r.onerror=()=>reject(Error('Не удалось прочитать '+file.name));r.readAsDataURL(file)})}return assertDataset(await request<Dataset>('/api/upload',{method:'POST',headers:{'Content-Type':'application/json','X-FinGraph':'local'},body:JSON.stringify(body)}))},
};
