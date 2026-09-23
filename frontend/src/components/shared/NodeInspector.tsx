import {Link} from 'react-router-dom';
import {ArrowDownLeft,ArrowUpRight,ExternalLink,Network,ReceiptText,Layers} from 'lucide-react';
import type {Client} from '../../types';
import {boundaryWarning,money,number} from '../../lib/data';
import {GidLabel,PriorityScore,RoleBadge,Warning,EmptyState} from './index';
const contributionLabels:Record<string,string>={role:'Роль',seed_flow:'Поток от seed',volume:'Объём',betweenness:'Посредничество'};
function PriorityDetails({node}:{node:Client}){
  let components:Record<string,unknown>={};
  try{const parsed=JSON.parse(node.priority_components??'{}');if(parsed&&typeof parsed==='object'&&!Array.isArray(parsed))components=parsed}catch{/* Explanation remains available if optional detail is absent. */}
  return <><section><h3>Причины приоритета</h3><p className="evidence">{node.why??'Обоснование приоритета появится после анализа.'}</p>{Object.keys(components).length>0&&<><p className="muted small">Вклады до поправки на новизну</p><dl className="features">{Object.entries(contributionLabels).map(([key,label])=>{const value=components[key];return typeof value==='number'&&Number.isFinite(value)?<div key={key}><dt>{label}</dt><dd>{value.toFixed(3).replace('.',',')}</dd></div>:null})}</dl></>}</section>{node.recommended_action&&<section><h3>Рекомендуемое действие</h3><p className="evidence">{node.recommended_action}</p></section>}</>;
}
export function NodeInspector({node}:{node?:Client}){if(!node)return <EmptyState title="Узел не выбран"><p>Выберите GID в списке или на графе.</p></EmptyState>;const features:[string,number|undefined][]=[['Доступных seed',node.seed_reach],['Входящих ветвей',node.feeder_branches],['Прирост схождения',node.convergence_gain],['Плательщиков seed',node.seed_payers]];return <div className="inspector-content">
  <div className="section-label">Выбранный клиент</div><h2 className="inspector-gid"><GidLabel gid={node.gid} full/></h2><div className="node-tags">{node.is_seed&&<span className="tag blue">Seed</span>}<span className="tag">Глубина {node.depth}</span>{node.cluster_id!=null&&<Link className="tag" to={'/clusters/'+node.cluster_id}>Кластер {node.cluster_id}</Link>}</div>
  <div className="inspector-priority"><span>Приоритет проверки</span><PriorityScore value={node.priority_score}/></div>
  <section><h3>Предполагаемая роль</h3><RoleBadge role={node.role}/><p className="muted small">Оценка роли: {number(node.role_score)}{node.role_score!=null?' из 1':''}. Не вероятность виновности.</p></section>
  <section><h3>Наблюдаемые потоки</h3><div className="flow-grid"><div><ArrowDownLeft size={19} color="#168477"/><span>Поступления</span><strong>{money(node.in_sum,true)}</strong><small>{number(node.in_deg)} отправителей</small></div><div><ArrowUpRight size={19} color="#356DF3"/><span>Отправления</span><strong>{money(node.out_sum,true)}</strong><small>{number(node.out_deg)} получателей</small></div></div><p className="muted small">Входящих операций: {number(node.in_tx)} · исходящих: {number(node.out_tx)}</p></section>
  <section><h3>Почему этот узел</h3><p className="evidence">{node.evidence??'Анализ не выполнен. Роль и приоритет не определены.'}</p><dl className="features">{features.filter(([,v])=>v!=null).map(([k,v])=><div key={k}><dt>{k}</dt><dd>{number(v)}</dd></div>)}</dl></section>
  <PriorityDetails node={node}/>
  <section><h3>Ограничения</h3>{node.depth===4&&<Warning>{boundaryWarning}</Warning>}{node.inflow_incomplete&&<p className="limitation">Есть входящие вне выборки: поступления наблюдаются не полностью.</p>}<p className="muted small">Наблюдаемые суммы не являются остатком на счёте. Результаты относятся ко всему периоду набора.</p></section>
  <div className="inspector-actions"><Link to={'/clients/'+node.gid}><ExternalLink size={15}/>Открыть карточку</Link><Link to={'/graph?gid='+node.gid+'&view=1'}><Network size={15}/>Показать связи</Link><Link to={'/transactions?gid='+node.gid}><ReceiptText size={15}/>Открыть транзакции</Link>{node.cluster_id!=null&&<Link to={'/clusters/'+node.cluster_id}><Layers size={15}/>Открыть кластер</Link>}</div>
  </div>}
