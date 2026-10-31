
import {ArrowRight,ArrowUpRight,CheckCircle2,ChevronRight,Search} from 'lucide-react';
import {Link} from 'react-router-dom';
export function Logo({small=false}){return <Link to="/" className={`logo ${small?'logo-sm':''}`} aria-label="TalentForge homepage"><span className="logo-mark">F</span><span>Talent<span className="logo-soft">Forge</span></span></Link>}
export function Button({children,to,variant='primary',icon=false,className='',...props}){const cls=`btn btn-${variant} ${className}`;return to?<Link className={cls} to={to} {...props}>{children}{icon&&<ArrowUpRight size={15}/>}</Link>:<button className={cls} {...props}>{children}{icon&&<ArrowRight size={15}/>}</button>}
export function Pill({children,tone='default'}){return <span className={`pill pill-${tone}`}>{children}</span>}
export function Status({status}){const tones={'Published':'green','Completed':'green','Draft':'muted','Invited':'orange','In progress':'blue','Archived':'muted'};return <Pill tone={tones[status]||'muted'}><span className="status-dot"/>{status}</Pill>}
export function Empty({icon:Icon=Search,title='Nothing here yet',description,action}){return <div className="empty-state"><span className="empty-icon"><Icon size={26}/></span><h3>{title}</h3><p>{description}</p>{action}</div>}
export function PageHeading({eyebrow,title,description,actions}){return <div className="page-heading"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1>{description&&<p className="muted intro">{description}</p>}</div>{actions&&<div className="page-actions">{actions}</div>}</div>}
export function Field({label,hint,error,children,required}){return <label className="field"><span className="field-label">{label}{required&&<span className="required"> *</span>}</span>{children}{hint&&<small>{hint}</small>}{error&&<small className="error">{error}</small>}</label>}
export function Stat({icon:Icon,label,value,detail}){return <div className="stat-card"><div className="stat-top"><span>{label}</span><span className="stat-icon"><Icon size={18}/></span></div><div className="stat-number">{value}</div><div className="stat-detail">{detail}</div></div>}
export function SectionTitle({title,subtitle,action}){return <div className="section-title"><div><h2>{title}</h2>{subtitle&&<p className="muted">{subtitle}</p>}</div>{action}</div>}
export function FormActions({onBack,backLabel='Back',onNext,nextLabel='Continue',nextDisabled=false}){return <div className="form-actions"><Button variant="outline" type="button" onClick={onBack}>{backLabel}</Button><Button type="button" onClick={onNext} disabled={nextDisabled}>{nextLabel}<ChevronRight size={15}/></Button></div>}
export function Checkline({children}){return <div className="checkline"><CheckCircle2 size={18} color="#90c8a4"/>{children}</div>}
