
// HIKMA IMPACT v9 — simple, reliable navigation/theme
(function(){
  const root=document.documentElement;
  const key="hikma-theme";
  function apply(t){
    root.dataset.theme=t;
    document.body.classList.toggle("dark-mode",t==="dark");
    try{localStorage.setItem(key,t)}catch(e){}
  }
  let saved="light";
  try{saved=localStorage.getItem(key)||"light"}catch(e){}
  apply(saved);

  document.addEventListener("click",function(e){
    const t=e.target.closest("[data-hikma-theme]");
    if(t){ apply(root.dataset.theme==="dark"?"light":"dark"); }
    const menu=e.target.closest("[data-hikma-menu]");
    if(menu){
      const panel=document.querySelector(menu.getAttribute("data-hikma-menu"));
      if(panel) panel.classList.toggle("is-open");
    }
  });
})();
