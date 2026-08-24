(function(){
 const root=document.documentElement;
 function setTheme(t){document.body.classList.toggle('dark',t==='dark');localStorage.setItem('hikma-theme',t)}
 window.toggleTheme=function(){setTheme(document.body.classList.contains('dark')?'light':'dark')};
 const saved=localStorage.getItem('hikma-theme'); if(saved) setTheme(saved);
 const levels=[...document.querySelectorAll('.cinema-section[data-level]')]; const dots=[...document.querySelectorAll('.level-nav a')];
 if(levels.length&&'IntersectionObserver' in window){const io=new IntersectionObserver(es=>{es.forEach(e=>{if(e.isIntersecting){dots.forEach(d=>d.classList.toggle('active',d.dataset.level===e.target.dataset.level))}})},{threshold:.55});levels.forEach(x=>io.observe(x))}
 let startY=0; document.addEventListener('touchstart',e=>{startY=e.changedTouches[0].screenY},{passive:true}); document.addEventListener('touchend',e=>{if(!levels.length)return;const dy=startY-e.changedTouches[0].screenY;if(Math.abs(dy)<80)return;let cur=levels.findIndex(x=>x.getBoundingClientRect().top>=-50&&x.getBoundingClientRect().top<window.innerHeight*.55); if(cur<0)cur=0;let next=Math.min(levels.length-1,Math.max(0,cur+(dy>0?1:-1)));levels[next].scrollIntoView({behavior:'smooth'})},{passive:true});
 const menu=document.getElementById('publicMenuBtn'), nav=document.getElementById('publicNav'); if(menu&&nav) menu.addEventListener('click',()=>nav.classList.toggle('open'));
})();
(function(){
 document.querySelectorAll('form').forEach(form=>{
   const rows=[...form.querySelectorAll('.drag-row')]; if(rows.length<2)return;
   let dragged=null;
   rows.forEach(row=>{row.draggable=true; row.addEventListener('dragstart',()=>{dragged=row;row.style.opacity='.45'});row.addEventListener('dragend',()=>{row.style.opacity='1';dragged=null});row.addEventListener('dragover',e=>{e.preventDefault();if(dragged&&dragged!==row){const r=row.getBoundingClientRect();const after=e.clientY>r.top+r.height/2;row.parentNode.insertBefore(dragged,after?row.nextSibling:row)}})});
   form.addEventListener('submit',()=>{const hidden=form.querySelectorAll('input[type="hidden"][name$="_id"]'); hidden.forEach((x,i)=>{x.dataset.order=i})});
 });
})();
