import {useCallback,useEffect,useMemo,useState} from 'react';
import {StoreContext} from './StoreContext.js';
import {apiRequest} from '../api.js';
import {readAuthSession,writeAuthSession} from '../authSession.js';
const initialAssessments = [
  {id:'TF-1042',title:'Senior Frontend Engineer',role:'Frontend Engineering',seniority:'Senior',status:'Published',duration:75,created:'2026-10-24',description:'Build thoughtful interfaces, reason about tradeoffs, and communicate decisions.',skills:['React','JavaScript','System design'],challenges:[{id:'c1',title:'Component architecture',type:'Written response',points:40,prompt:'How would you design an accessible, reusable data table?'},{id:'c2',title:'Debug an async flow',type:'Technical challenge',points:60,prompt:'Explain how you would diagnose a race condition in a React application.'}],aiEnabled:false,scoreWeights:{technical:60,reasoning:25,communication:15},passingScore:70,instructions:'Read each question carefully. You can save drafts before submitting.'},
  {id:'TF-1041',title:'Backend API Developer',role:'Backend Engineering',seniority:'Mid-level',status:'Published',duration:60,created:'2026-10-22',description:'Explore API design, reliability, and engineering judgment.',skills:['Node.js','SQL','APIs'],challenges:[{id:'c3',title:'Design a resilient API',type:'Written response',points:100,prompt:'Outline a secure REST API design for managing task assignments.'}],aiEnabled:false,scoreWeights:{technical:60,reasoning:25,communication:15},passingScore:70,instructions:'Explain your thinking and assumptions.'},
  {id:'TF-1040',title:'Product Design Engineer',role:'Product Engineering',seniority:'Junior',status:'Draft',duration:45,created:'2026-10-20',description:'Assess product intuition and collaborative engineering skills.',skills:['HTML','CSS','UX'],challenges:[{id:'c4',title:'Improve a user flow',type:'Written response',points:100,prompt:'Describe how you would improve a confusing sign-up process.'}],aiEnabled:false,scoreWeights:{technical:60,reasoning:25,communication:15},passingScore:65,instructions:'Provide your rationale for each decision.'}
];
const initialCandidates = [
  {id:'CAN-001',name:'Jamie Park',email:'jamie.park@example.com',role:'Frontend Engineer',status:'Completed',assessmentId:'TF-1042',score:88,invited:'2026-10-24'},
  {id:'CAN-002',name:'Morgan Ellis',email:'morgan.ellis@example.com',role:'Frontend Engineer',status:'In progress',assessmentId:'TF-1042',score:null,invited:'2026-10-25'},
  {id:'CAN-003',name:'Taylor Reed',email:'taylor.reed@example.com',role:'Backend Developer',status:'Invited',assessmentId:'TF-1041',score:null,invited:'2026-10-26'},
  {id:'CAN-004',name:'Alex Chen',email:'alex.chen@example.com',role:'Backend Developer',status:'Completed',assessmentId:'TF-1041',score:91,invited:'2026-10-23'},
];
function stored(key,fallback) {try {const value=localStorage.getItem('tf_'+key);return value?JSON.parse(value):fallback;}catch{return fallback;}}
export function StoreProvider({children}) {
 const [assessments,setAssessments]=useState(()=>stored('assessments',initialAssessments));
 const [candidates,setCandidates]=useState(()=>stored('candidates',initialCandidates));
 const [submissions,setSubmissions]=useState(()=>stored('submissions',[]));
 const [session,setSession]=useState(readAuthSession);
 const [authLoading,setAuthLoading]=useState(Boolean(session));
 const user=session?.user||null;
 const token=session?.token||null;
 const [toast,setToast]=useState('');
 useEffect(()=>localStorage.setItem('tf_assessments',JSON.stringify(assessments)),[assessments]);
 useEffect(()=>localStorage.setItem('tf_candidates',JSON.stringify(candidates)),[candidates]);
 useEffect(()=>localStorage.setItem('tf_submissions',JSON.stringify(submissions)),[submissions]);
 useEffect(()=>writeAuthSession(session),[session]);
 useEffect(()=>{
  const restored=readAuthSession();
  if(!restored)return undefined;
  let active=true;
  apiRequest('/auth/me',{token:restored.token})
   .then(identity=>{
    if(!active)return;
    if(!Number.isInteger(identity?.id)||!['candidate','employer'].includes(identity?.role)){
     throw new Error('The session response was invalid.');
    }
    setSession(current=>current?.token===restored.token?{
     ...current,user:{...current.user,id:identity.id,role:identity.role}
    }:current);
   })
   .catch(()=>{if(active)setSession(null);})
   .finally(()=>{if(active)setAuthLoading(false);});
  return ()=>{active=false;};
 },[]);
 const setAuth=useCallback((accessToken,backendUser)=>{
  const next={token:accessToken,user:{id:backendUser.id,name:backendUser.full_name,email:backendUser.email,role:backendUser.role}};
  setSession(next);
  setAuthLoading(false);
 },[]);
 const setUser=useCallback(nextUser=>{
  if(nextUser==null){
   setSession(null);
   setAuthLoading(false);
   return;
  }
  setSession(current=>{
   if(!current)return current;
   const updated=typeof nextUser==='function'?nextUser(current.user):nextUser;
   return {...current,user:{...updated,id:current.user.id,role:current.user.role}};
  });
 },[]);
 useEffect(()=>{if(!toast)return;const timer=setTimeout(()=>setToast(''),4000);return ()=>clearTimeout(timer);},[toast]);
 const value=useMemo(()=>({assessments,setAssessments,candidates,setCandidates,submissions,setSubmissions,user,token,setUser,setAuth,authLoading,toast,setToast}),[assessments,candidates,submissions,user,token,setUser,setAuth,authLoading,toast]);
 return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}
