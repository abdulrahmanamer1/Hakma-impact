(function(){
  window.openHikmaMenu=function(){
    const d=document.getElementById('h10Drawer'); if(d)d.classList.add('open');
  };
  window.closeHikmaMenu=function(){
    const d=document.getElementById('h10Drawer'); if(d)d.classList.remove('open');
  };
  document.addEventListener('keydown',e=>{if(e.key==='Escape')window.closeHikmaMenu()});
})();
