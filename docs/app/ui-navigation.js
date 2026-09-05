(function () {
  if (document.querySelector('.page-nav') || new URLSearchParams(window.location.search).get('embed') === '1') return;
  const pages = {
    '/app-shell.html': 'داشبورد',
    '/index.html': 'Case Review',
    '/scenarios.html': 'اجرای سناریوها',
    '/scenario-management.html': 'مدیریت سناریوها',
    '/scenario-management.htm': 'مدیریت سناریوها',
    '/scenario-checklist.html': 'اجرای چک‌لیست سناریو'
  };
  const nav = document.createElement('nav');
  nav.className = 'page-nav';
  nav.innerHTML = '<a href="app-shell.html">⌂ صفحه اصلی</a><button type="button" id="pageBack">← بازگشت به صفحه قبل</button><span>صفحه فعلی: ' + (pages[window.location.pathname] || 'Pargar Support Copilot') + '</span>';
  const style = document.createElement('style');
  style.textContent = '.page-nav{position:sticky;top:0;z-index:20;display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:9px 5vw;background:rgba(255,255,255,.88);backdrop-filter:blur(12px);border-bottom:1px solid #cbdcf2;box-shadow:0 5px 18px rgba(15,23,42,.09);font:14px Vazirmatn,Tahoma,Arial,sans-serif;direction:rtl}.page-nav a,.page-nav button{border:1px solid #b9cbea;border-radius:10px;padding:6px 11px;background:linear-gradient(135deg,#fff,#eff6ff);color:#1e40af;text-decoration:none;cursor:pointer;font:inherit;transition:.2s}.page-nav a:hover,.page-nav button:hover{transform:translateY(-1px);border-color:#60a5fa;background:#dbeafe;box-shadow:0 5px 12px rgba(37,99,235,.15)}.page-nav span{color:#475569;font-size:12px;margin-right:auto}@media(max-width:600px){.page-nav span{width:100%;margin-right:0}}
  body{background:radial-gradient(circle at 8% 8%,rgba(96,165,250,.16),transparent 28%),radial-gradient(circle at 92% 14%,rgba(45,212,191,.14),transparent 24%),linear-gradient(135deg,#eef5ff 0%,#f8fafc 52%,#ecfdf5 100%)!important;min-height:100vh}body:before,body:after{content:"";position:fixed;z-index:-1;border-radius:50%;filter:blur(2px);pointer-events:none}body:before{width:220px;height:220px;left:-90px;bottom:8%;background:rgba(59,130,246,.10)}body:after{width:180px;height:180px;right:-70px;top:28%;background:rgba(20,184,166,.09)}.topbar{position:relative;overflow:hidden}.topbar:after{content:"✦";position:absolute;left:5vw;bottom:-24px;color:rgba(255,255,255,.16);font-size:8rem;line-height:1}.card,.hero,.notice,.module,.scenario{box-shadow:0 12px 28px rgba(30,64,175,.10)!important}.card,.hero,.module,.scenario{position:relative;overflow:hidden}.card:before,.hero:before,.module:before,.scenario:before{content:"";position:absolute;right:0;top:0;width:5px;height:100%;background:linear-gradient(#2563eb,#14b8a6);opacity:.8}.module:hover,.scenario:hover{transform:translateY(-3px);border-color:#93c5fd!important;box-shadow:0 16px 30px rgba(37,99,235,.16)!important;transition:.22s}.btn,.primary,button{transition:.2s}.btn:hover,.primary:hover,button:hover{transform:translateY(-1px)}input:focus,textarea:focus,select:focus{outline:3px solid rgba(59,130,246,.18);border-color:#60a5fa!important}.section-head h2,.section-head h3{color:#1e3a8a}';
  document.head.appendChild(style);
  document.body.insertBefore(nav, document.body.firstChild);
  document.getElementById('pageBack').onclick = function () {
    if (history.length > 1) history.back();
    else window.location.href = 'app-shell.html';
  };
}());
fetch('/api/version-history').then(function (response) { return response.ok ? response.json() : Promise.reject(); }).then(function (data) {
  if (!data.current_version) return;
  document.querySelectorAll('#versionButton').forEach(function (button) {
    button.textContent = data.current_version.replace(/\d/g, function (digit) { return '۰۱۲۳۴۵۶۷۸۹'[digit]; });
  });
}).catch(function () {});
