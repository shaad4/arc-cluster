import type { ReactNode } from 'react'
import { AlertCircle, ArrowUpRight, Database } from 'lucide-react'
import { Link } from 'react-router'
import { Button } from './ui/button'
import { cn } from '../lib/utils'
export function Status({ value }: { value: string }) { return <span className={cn('status', `status-${value.toLowerCase().replaceAll(' ', '-')}`)}><span/>{value.replaceAll('_', ' ')}</span> }
export function PageHeading({ title, description, children }: { title: string; description: string; children?: ReactNode }) { return <div className="page-heading"><div><h1>{title}</h1><p>{description}</p></div><div className="actions">{children}</div></div> }
export function Panel({ title, subtitle, children, action, className }: { title: string; subtitle?: string; children: ReactNode; action?: ReactNode; className?: string }) { return <section className={cn('panel', className)}><div className="panel-heading"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>{action}</div>{children}</section> }
export function Metric({ label, value, detail }: { label: string; value: ReactNode; detail?: string }) { return <div className="metric"><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</div> }
export function Empty({ title = 'No observations yet', detail = 'Collected samples will appear here automatically.' }: { title?: string; detail?: string }) { return <div className="empty"><Database size={22}/><h3>{title}</h3><p>{detail}</p></div> }
export function Loading() { return <div className="loading" role="status" aria-label="Loading"><div className="skeleton"/><div className="skeleton"/><div className="skeleton"/></div> }
export function ErrorState({ error, retry }: { error: Error; retry?: () => void }) { return <div className="error" role="alert"><AlertCircle size={18}/><div><strong>Unable to load observations</strong><p>{error.message}</p></div>{retry && <Button onClick={retry}>Retry</Button>}</div> }
export function ViewLink({ to, children }: { to: string; children: ReactNode }) { return <Link className="text-link" to={to}>{children}<ArrowUpRight size={14}/></Link> }
