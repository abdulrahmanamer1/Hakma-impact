
(function(){
  const html=document.documentElement;
  function theme(){
    let t='light';
    try{t=localStorage.getItem('hikma-theme')||'light'}catch(e){}
    html.dataset.theme=t;
    document.body.classList.toggle('dark-mode',t==='dark');
  }
  window.toggleHikmaTheme=function(){
    const next=document.body.classList.contains('dark-mode')?'light':'dark';
    try{localStorage.setItem('hikma-theme',next)}catch(e){}
    html.dataset.theme=next; document.body.classList.toggle('dark-mode',next);
  };
  window.openHikmaMenu=function(){
    const d=document.getElementById('h10Drawer'); if(d)d.classList.add('open');
  };
  window.closeHikmaMenu=function(){
    const d=document.getElementById('h10Drawer'); if(d)d.classList.remove('open');
  };
  document.addEventListener('keydown',e=>{if(e.key==='Escape')window.closeHikmaMenu()});
  document.addEventListener('DOMContentLoaded',theme);
})();
