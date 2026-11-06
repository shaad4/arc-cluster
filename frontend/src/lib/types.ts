export interface Metrics { timestamp: number; hostname: string; cpu_percent: number; cpu_count: number; memory_total: number; memory_used: number; memory_percent: number; disk_total: number; disk_used: number; disk_percent: number; net_sent: number; net_recv: number; net_sent_rate: number | null; net_recv_rate: number | null; uptime: number }
export interface Node { id: string; name: string; role: string; ip: string; machine_status: string; ray_status: string; status: string; ray_id: string | null; resources: Record<string, number>; metrics: Metrics | null; last_seen: number | null; stale: boolean; source: string | null; agent_status: string; ray_process: boolean | null; control_reason: string }
export interface StateItem { items: Record<string, unknown>[]; error: string | null }
export interface Ray { available: boolean; version: string | null; sampled_at: number | null; error: string | null; total: Record<string, number>; free: Record<string, number>; nodes: { id: string; ip: string; alive: boolean; resources: Record<string, number> }[]; tasks: StateItem; actors: StateItem }
export interface Aggregate { timestamp: number; cpu_percent: number | null; memory_percent: number | null; memory_used: number | null; memory_total: number | null; disk_percent: number | null; net_sent_rate: number | null; net_recv_rate: number | null; reporting_nodes: number; active_nodes: number | null; ray_cpu_total: number | null; ray_cpu_available: number | null }
export interface ClusterEvent { timestamp: number; node: string | null; message: string; severity: string }
export interface Overview { status: string; configured_nodes: number; active_nodes: number | null; updated_at: number | null; collector_error: string | null; aggregate: Aggregate; nodes: Node[]; ray: Ray; events: ClusterEvent[] }
export interface History { samples: { aggregate: Aggregate; nodes: Record<string, Metrics> }[] }
export interface Job { id: string; name: string; status: string; submission_id: string | null; start_time: number | null; end_time: number | null; entrypoint: string; message: string | null; type: string }
export interface JobList { items: Job[]; error: string | null }
export interface LogData { text: string; source: string; truncated: boolean }
export interface Settings { name: string; version: string; head_address: string; ray_version: string | null; poll_interval: number; collector_status: string; application_health: string; nodes: Node[]; approved_workload: boolean }
export interface Preflight { allowed: boolean; reason: string; member: boolean | null; ray_process: boolean | null }
