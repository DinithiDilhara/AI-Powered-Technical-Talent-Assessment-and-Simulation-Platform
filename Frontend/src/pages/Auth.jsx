import {useState} from 'react';
import {ArrowLeft,CheckCircle2,Eye,EyeOff,LockKeyhole} from 'lucide-react';
import {Link,useNavigate} from 'react-router-dom';
import {Button,Field,Logo} from '../components/UI.jsx';
import {apiRequest} from '../api.js';
import {workspacePathFor} from '../authFlow.js';
import {useStore} from '../context/useStore.js';

export default function Auth({signup=false}){
 const nav=useNavigate();
 const {assessments,setAuth,setToast}=useStore();
 const [show,setShow]=useState(false);
 const [name,setName]=useState('');
 const [email,setEmail]=useState('');
 const [pass,setPass]=useState('');
 const [role,setRole]=useState('candidate');
 const [error,setError]=useState('');
 const [submitting,setSubmitting]=useState(false);

 const handleSubmit=async event=>{
  event.preventDefault();
  setError('');
  if(!/^\S+@\S+\.\S+$/.test(email.trim())){setError('Please enter a valid email address.');return;}
  if(pass.length<8){setError('Password must contain at least 8 characters.');return;}
  if(signup&&name.trim().length<2){setError('Please enter your full name.');return;}
  setSubmitting(true);
  try{
   if(signup){
    await apiRequest('/register',{
     method:'POST',
     body:{full_name:name.trim(),email:email.trim(),password:pass,role}
    });
    setToast('Account created. Sign in with your new credentials.');
    nav('/login',{replace:true});
    return;
   }

   const result=await apiRequest('/auth/login',{
    method:'POST',
    body:{email:email.trim(),password:pass}
   });
   if(!result?.access_token||!result?.user||!['employer','candidate'].includes(result.user.role)){
    throw new Error('The server returned an invalid authentication response.');
   }
   setAuth(result.access_token,result.user);
   nav(workspacePathFor(result.user.role,assessments),{replace:true});
  }catch(requestError){
   setError(requestError.message||'Unable to complete the request. Please try again.');
  }finally{
   setSubmitting(false);
  }
 };

 return <div className="auth-page"><div className="auth-formside"><Link className="auth-back" to="/"><ArrowLeft size={16}/> Back to home</Link><div className="auth-box"><Logo/><div className="auth-title"><span className="eyebrow">{signup?'CREATE AN ACCOUNT':'WELCOME BACK'}</span><h1>{signup?'Make room for real ability.':'Good to have you back.'}</h1><p>{signup?'Set up your workspace and create your first meaningful assessment.':'Sign in to continue your TalentForge journey.'}</p></div><form onSubmit={handleSubmit} noValidate>{signup&&<Field label="Full name" required><input autoComplete="name" placeholder="e.g. Alex Morgan" maxLength={100} value={name} onChange={event=>setName(event.target.value)}/></Field>}<Field label="Work email" required><input type="email" autoComplete="email" placeholder="you@company.com" value={email} onChange={event=>setEmail(event.target.value)}/></Field><Field label="Password" required><div className="password-wrap"><input type={show?'text':'password'} minLength={8} maxLength={128} autoComplete={signup?'new-password':'current-password'} placeholder="At least 8 characters" value={pass} onChange={event=>setPass(event.target.value)}/><button type="button" className="password-toggle" onClick={()=>setShow(!show)} aria-label={show?'Hide password':'Show password'}>{show?<EyeOff size={18}/>:<Eye size={18}/>}</button></div></Field>{signup&&<div className="field"><span className="field-label">I am here as a</span><div className="role-toggle"><button type="button" className={role==='employer'?'selected':''} onClick={()=>{setRole('employer');setError('');}}>Hiring team</button><button type="button" className={role==='candidate'?'selected':''} onClick={()=>{setRole('candidate');setError('');}}>Candidate</button></div></div>}{error&&<p className="error banner-error" role="alert">{error}</p>}<Button type="submit" className="full" icon disabled={submitting}>{submitting?'Please wait…':signup?'Create account':'Sign in'}</Button></form><p className="auth-switch">{signup?'Already have an account?':'New to TalentForge?'} <Link to={signup?'/login':'/signup'}>{signup?'Sign in':'Create an account'}</Link></p><p className="auth-disclaimer"><LockKeyhole size={13}/> TalentForge verifies your account before starting a session.</p></div></div><div className="auth-art"><span className="eyebrow">YOUR WORK. YOUR POTENTIAL.</span><div className="auth-art-content"><span className="art-symbol">F</span><h2>Great talent deserves<br/><em>great questions.</em></h2><p>See the thinking behind the work. Build a more meaningful technical hiring experience.</p><div className="auth-proof"><CheckCircle2 size={18}/> Practical challenges, clear expectations, human decisions.</div></div><div className="auth-art-foot">TALENTFORGE / THE BETTER WAY TO ASSESS</div></div></div>;
}
