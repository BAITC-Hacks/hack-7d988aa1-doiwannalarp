export type Role = 'coordinator'|'consolidator'|'distributor'|'transit'|'terminal'|'boundary'|'peripheral';
export interface Client {
  gid:string; depth:number; is_seed:boolean; role?:Role; role_score?:number|null; priority_score?:number|null; cluster_id?:number|null; evidence?:string; why?:string;
  in_sum:number; out_sum:number; in_deg:number; out_deg:number; in_tx:number; out_tx:number;
  censored?:boolean; inflow_incomplete?:boolean; seed_reach?:number; seed_payers?:number; feeder_branches?:number; convergence_gain?:number; pass_ratio?:number|null;
  betweenness?:number; seed_flow_in?:number; in_cycle?:boolean; in_2cycle?:boolean; late_inflow_share?:number; fast_through_share?:number;
  x?:number; y?:number; rule_trace?:string; secondary_roles?:string; priority_components?:string; recommended_action?:string;
}
export interface Edge {src:string;dst:string;sum_kzt:number;n_tx:number;depth:number}
export interface Transaction {src:string;dst:string;date:string;sum_kzt:number}
export interface Cluster {cluster_id:number;n_nodes:number;n_seed:number;sum_kzt_internal:number;top_gids:string;hypothesis:string}
export interface Dataset {
  meta:{id:string;name:string;mode:'real'|'demo';period:[string,string];has_time:boolean;analyzed:boolean;total_sum:number;files:{name:string;rows:number}[];validation:string[];computed_at:string|null;methodology_version:string|null};
  nodes:Client[];edges:Edge[];transactions:Transaction[];clusters:Cluster[];exports:string[];
  methodology:{text:string|null;thresholds:Record<string,number|Record<string,number>>};
}
export interface Settings {compact:boolean;labels:boolean;color:'role'|'cluster';columns:string[]}
export interface NodeFilter {q?:string;role?:string;cluster?:string;depth?:string;seed?:string;boundary?:string;min?:string;max?:string}
